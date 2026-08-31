"""Candle aggregation engine (pure Python).

Turns a stream of ticks into OHLC(V) candles for a single timeframe. Designed
to survive real-world feed problems:

* Duplicate ticks       -> ignored (identical timestamp + price).
* Out-of-order ticks    -> routed to the correct (possibly already-closed)
                           bucket and update its candle; counted.
* Missing ticks         -> no candle is fabricated; gaps are detectable via
                           :meth:`missing_buckets` for backfill.
* Timezone              -> all bucketing is UTC-aligned (see ``timeframes``).
* Session boundaries    -> a new UTC bucket always starts a new candle.

The engine never invents prices. A tick with no usable price is skipped.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from market_data.provider import Candle, Timeframe
from market_data.tick import Tick
from market_data.timeframes import (
    duration_seconds,
    expected_bucket_starts,
    floor_to_bucket,
)


@dataclass(frozen=True)
class AggregationResult:
    """Outcome of feeding one tick to the aggregator."""

    accepted: bool
    #: The candle that was created or updated by this tick (if any).
    updated_candle: Candle | None = None
    #: A candle that was closed as a result of this tick advancing time.
    closed_candle: Candle | None = None
    #: True if this tick opened a brand-new bucket.
    opened_new_bucket: bool = False
    #: Why a tick was rejected ("duplicate", "no_price"), else None.
    reason: str | None = None


class CandleAggregator:
    """Aggregates ticks into candles for one timeframe.

    Keeps a bounded history of recent candles so late/out-of-order ticks can
    still be applied to the correct bucket.
    """

    def __init__(self, timeframe: Timeframe, *, max_candles: int = 5000) -> None:
        self.timeframe = timeframe
        self._duration = duration_seconds(timeframe)
        self._candles: OrderedDict[int, Candle] = OrderedDict()
        self._current_bucket: int | None = None
        self._max_candles = max_candles
        self._last_tick_key: tuple | None = None

        # Diagnostics.
        self.duplicate_count = 0
        self.out_of_order_count = 0
        self.no_price_count = 0
        self.tick_count = 0

    # ------------------------------------------------------------------ seed
    def seed(self, candles: list[Candle]) -> None:
        """Load pre-existing candles (e.g. from storage/backfill).

        Candles must be for this aggregator's timeframe. The most recent one
        becomes the current (forming) bucket.
        """
        for c in candles:
            if c.timeframe is not self.timeframe:
                raise ValueError(f"Candle timeframe {c.timeframe} != aggregator {self.timeframe}")
            self._candles[int(c.open_time_epoch)] = c
        self._candles = OrderedDict(sorted(self._candles.items()))
        self._trim()
        if self._candles:
            self._current_bucket = next(reversed(self._candles))

    # ------------------------------------------------------------------ feed
    def add_tick(self, tick: Tick) -> AggregationResult:
        """Feed a single tick; returns what changed."""
        price = tick.price
        if price is None:
            self.no_price_count += 1
            return AggregationResult(accepted=False, reason="no_price")

        # Exact-duplicate rejection: same timestamp + price + volume as the
        # immediately preceding tick.
        key = (round(float(tick.timestamp_epoch), 6), price, tick.volume)
        if key == self._last_tick_key:
            self.duplicate_count += 1
            return AggregationResult(accepted=False, reason="duplicate")
        self._last_tick_key = key

        self.tick_count += 1
        return self._apply(price, float(tick.timestamp_epoch), tick.volume)

    def add_price(
        self, price: float, timestamp_epoch: float, volume: float | None = None
    ) -> AggregationResult:
        """Lower-level entry point (used by tests and non-tick sources)."""
        self.tick_count += 1
        return self._apply(price, float(timestamp_epoch), volume)

    def _apply(self, price: float, ts_epoch: float, volume: float | None) -> AggregationResult:
        bucket = floor_to_bucket(ts_epoch, self.timeframe)
        closed: Candle | None = None
        opened_new = False

        # Out-of-order: tick belongs to an older bucket than the current one.
        if self._current_bucket is not None and bucket < self._current_bucket:
            self.out_of_order_count += 1
            updated = self._update_existing(bucket, price, volume)
            return AggregationResult(accepted=True, updated_candle=updated, reason="out_of_order")

        # Advancing to a new bucket closes the previous forming candle.
        if self._current_bucket is not None and bucket > self._current_bucket:
            closed = self._candles.get(self._current_bucket)

        if bucket not in self._candles:
            opened_new = bucket != self._current_bucket or self._current_bucket is None
            self._candles[bucket] = Candle(
                timeframe=self.timeframe,
                open_time_epoch=bucket,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )
        else:
            self._candles[bucket] = self._merge(self._candles[bucket], price, volume)

        self._current_bucket = max(self._current_bucket or bucket, bucket)
        self._trim()
        return AggregationResult(
            accepted=True,
            updated_candle=self._candles[bucket],
            closed_candle=closed,
            opened_new_bucket=opened_new,
        )

    def _update_existing(self, bucket: int, price: float, volume: float | None) -> Candle | None:
        """Apply a late tick to an existing bucket (does not move OHLC open)."""
        existing = self._candles.get(bucket)
        if existing is None:
            # The bucket was trimmed / never seen; do not fabricate a candle
            # out of a single late tick that has no neighbours. Skip safely.
            return None
        # A late tick can only widen high/low and (arguably) update volume; it
        # must NOT change the historical open or the already-recorded close.
        new_high = max(existing.high, price)
        new_low = min(existing.low, price)
        new_volume = self._add_volume(existing.volume, volume)
        updated = Candle(
            timeframe=existing.timeframe,
            open_time_epoch=existing.open_time_epoch,
            open=existing.open,
            high=new_high,
            low=new_low,
            close=existing.close,
            volume=new_volume,
        )
        self._candles[bucket] = updated
        return updated

    def _merge(self, existing: Candle, price: float, volume: float | None) -> Candle:
        return Candle(
            timeframe=existing.timeframe,
            open_time_epoch=existing.open_time_epoch,
            open=existing.open,
            high=max(existing.high, price),
            low=min(existing.low, price),
            close=price,
            volume=self._add_volume(existing.volume, volume),
        )

    @staticmethod
    def _add_volume(existing: float | None, incoming: float | None) -> float | None:
        if incoming is None:
            return existing
        return (existing or 0.0) + incoming

    def _trim(self) -> None:
        while len(self._candles) > self._max_candles:
            self._candles.popitem(last=False)

    # --------------------------------------------------------------- queries
    def candles(self) -> list[Candle]:
        """Return all candles (oldest first), including the forming one."""
        return list(self._candles.values())

    def closed_candles(self) -> list[Candle]:
        """Return all candles except the current forming bucket."""
        result = list(self._candles.values())
        if result and self._current_bucket is not None:
            if int(result[-1].open_time_epoch) == self._current_bucket:
                return result[:-1]
        return result

    def current(self) -> Candle | None:
        if self._current_bucket is None:
            return None
        return self._candles.get(self._current_bucket)

    def latest(self, limit: int = 500) -> list[Candle]:
        return self.candles()[-limit:]

    def missing_buckets(self, start_epoch: float, end_epoch: float) -> list[int]:
        """Return UTC-aligned bucket starts missing in ``[start, end]``.

        Used to drive backfill after a reconnection: any expected bucket with
        no candle is a gap that must be fetched rather than invented.
        """
        expected = expected_bucket_starts(start_epoch, end_epoch, self.timeframe)
        return [b for b in expected if b not in self._candles]
