"""Simulated market-data provider (pure Python) — CLEARLY LABELLED.

This provider generates a deterministic random-walk price series so the full
pipeline (ticks -> candles -> storage -> WebSocket -> chart), reconnection and
stale-detection can be exercised WITHOUT a live broker or network access.

IMPORTANT / HONESTY:
    * ``name == "simulated"`` and every snapshot/tick carries ``source =
      "simulated"``. The UI must display this prominently.
    * This is NOT real market data and must never be presented as such. It is
      a development/demo/testing aid only. Do not use its output for any real
      trading decision.

A real provider (see ``market_data.providers``) is used when network access
and credentials are available; it plugs into the identical interface.
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from market_data.provider import (
    Candle,
    MarketDataProvider,
    PriceSnapshot,
    SymbolSpec,
    Timeframe,
)
from market_data.tick import Tick
from market_data.timeframes import duration_seconds, floor_to_bucket


class SimulatedMarketDataProvider(MarketDataProvider):
    """Deterministic synthetic XAUUSD feed for offline development."""

    name = "simulated"

    def __init__(
        self,
        *,
        start_price: float = 2400.0,
        spread: float = 0.30,
        volatility: float = 0.15,
        seed: int = 1234,
        broker_symbol: str = "XAUUSD",
    ) -> None:
        self._price = start_price
        self._spread = spread
        self._volatility = volatility
        self._rng = random.Random(seed)
        self._connected = False
        self._broker_symbol = broker_symbol
        self._last_tick: Tick | None = None

    # ------------------------------------------------------------- lifecycle
    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def supported_timeframes(self) -> list[Timeframe]:
        return Timeframe.ordered()

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        return SymbolSpec(canonical="XAUUSD", broker_symbol=self._broker_symbol)

    # ------------------------------------------------------------- generation
    def _step_price(self) -> float:
        # Gaussian random walk with a soft mean-reversion pull toward start.
        drift = self._rng.gauss(0.0, self._volatility)
        self._price = round(self._price + drift, 3)
        return self._price

    def generate_tick(self, timestamp_epoch: float) -> Tick:
        """Produce the next synthetic tick at ``timestamp_epoch`` (UTC seconds)."""
        mid = self._step_price()
        half = self._spread / 2.0
        tick = Tick(
            symbol="XAUUSD",
            timestamp_epoch=float(timestamp_epoch),
            bid=round(mid - half, 3),
            ask=round(mid + half, 3),
            last=round(mid, 3),
            volume=float(self._rng.randint(1, 5)),
            source=self.name,
        )
        self._last_tick = tick
        return tick

    def get_tick(self, symbol: str) -> Tick | None:
        return self._last_tick

    def get_snapshot(self, symbol: str) -> PriceSnapshot:
        if not self._connected or self._last_tick is None:
            return PriceSnapshot(symbol=symbol, connected=self._connected, source=self.name)
        t = self._last_tick
        return PriceSnapshot(
            symbol=symbol,
            connected=True,
            bid=t.bid,
            ask=t.ask,
            last=t.last,
            timestamp_epoch=t.timestamp_epoch,
            source=self.name,
        )

    def subscribe_ticks(self, symbol: str) -> Iterator[Tick]:
        """Infinite generator of ticks spaced ~1s apart (caller controls time)."""
        ts = 0.0
        while True:
            ts += 1.0
            yield self.generate_tick(ts)

    # ------------------------------------------------------------- history
    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        return self.get_historical_candles(symbol, timeframe, limit=limit)

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        end_epoch: float | None = None,
    ) -> list[Candle]:
        """Generate ``limit`` synthetic candles ending at the given bucket.

        Uses a private RNG so history generation does not disturb the live
        walk. Prices are contiguous (each candle opens at the prior close).
        """
        if not self._connected:
            return []
        dur = duration_seconds(timeframe)
        anchor = floor_to_bucket(end_epoch if end_epoch is not None else 0.0, timeframe)
        # If no anchor time given, base history off a fixed synthetic clock.
        if end_epoch is None:
            anchor = dur * limit
        rng = random.Random(hash((timeframe.value, limit, anchor)) & 0xFFFFFFFF)
        price = self._price
        candles: list[Candle] = []
        first_open = anchor - dur * (limit - 1)
        for i in range(limit):
            open_time = first_open + i * dur
            o = price
            highs = [o]
            lows = [o]
            steps = 4
            for _ in range(steps):
                price = round(price + rng.gauss(0.0, self._volatility), 3)
                highs.append(price)
                lows.append(price)
            c = price
            candles.append(
                Candle(
                    timeframe=timeframe,
                    open_time_epoch=float(open_time),
                    open=round(o, 3),
                    high=round(max(highs), 3),
                    low=round(min(lows), 3),
                    close=round(c, 3),
                    volume=float(rng.randint(50, 500)),
                )
            )
        return candles
