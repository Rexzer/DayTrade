"""Deterministic candle factories for strategy/indicator tests (not collected)."""

from __future__ import annotations

from market_data.provider import Candle, Timeframe


def make_candles(
    closes: list[float],
    *,
    timeframe: Timeframe = Timeframe.M15,
    spread: float = 0.5,
    volume: float = 100.0,
    start_epoch: int = 0,
) -> list[Candle]:
    """Build candles from a close series.

    Each candle's open = previous close (contiguous). High/low straddle the
    open/close by ``spread``. Deterministic and dependency-free.
    """
    dur = {
        Timeframe.M1: 60,
        Timeframe.M5: 300,
        Timeframe.M15: 900,
        Timeframe.M30: 1800,
        Timeframe.H1: 3600,
        Timeframe.H4: 14400,
        Timeframe.D1: 86400,
    }[timeframe]
    out: list[Candle] = []
    prev = closes[0]
    for i, close in enumerate(closes):
        o = prev
        hi = max(o, close) + spread
        lo = min(o, close) - spread
        out.append(
            Candle(
                timeframe=timeframe,
                open_time_epoch=float(start_epoch + i * dur),
                open=o,
                high=hi,
                low=lo,
                close=close,
                volume=volume,
            )
        )
        prev = close
    return out


def uptrend(n: int = 120, start: float = 2000.0, step: float = 2.0, **kw) -> list[Candle]:
    return make_candles([start + i * step for i in range(n)], **kw)


def downtrend(n: int = 120, start: float = 2400.0, step: float = 2.0, **kw) -> list[Candle]:
    return make_candles([start - i * step for i in range(n)], **kw)


def flat(n: int = 120, level: float = 2000.0, wobble: float = 3.0, seed: int = 42, **kw):
    """A realistic mean-reverting range (deterministic).

    Uses a seeded random walk with a pull back toward ``level`` so the series
    stays banded and non-trending (unlike a pathological 2-bar oscillation,
    which would confuse ADX).
    """
    import random

    rng = random.Random(seed)
    closes = []
    price = level
    for _ in range(n):
        price += rng.uniform(-wobble, wobble) + (level - price) * 0.25
        closes.append(round(price, 3))
    return make_candles(closes, **kw)


# --- Phase 4 backtesting helpers -------------------------------------------

from strategy_engine.strategy import (  # noqa: E402
    MarketContext,
    Signal,
    SignalLevel,
    Strategy,
    StrategyMetadata,
)


def candle(t: float, o: float, h: float, low: float, c: float, tf=Timeframe.H1, vol=100.0):
    """Build one Candle with explicit OHLC (for precise backtest scenarios)."""
    return Candle(tf, float(t), o, h, low, c, vol)


class FixedSignalStrategy(Strategy):
    """Emits a fixed directional signal every bar once enough history exists.

    Deterministic and dependency-free — used to exercise backtester mechanics
    (entry/exit/sizing) without indicator noise.
    """

    def __init__(
        self,
        direction: str = "long",
        stop_offset: float = 10.0,
        tp_offset: float = 15.0,
        level: SignalLevel = SignalLevel.CONFIRMED_SETUP,
        timeframe: str = "1h",
        min_bars: int = 2,
    ) -> None:
        self._direction = direction
        self._stop_offset = stop_offset
        self._tp_offset = tp_offset
        self._level = level
        self._timeframe = timeframe
        self._min_bars = min_bars
        self.metadata = StrategyMetadata(key="fixed", name="Fixed", description="test")

    def evaluate(self, ctx: MarketContext) -> Signal:
        cs = ctx.candles.get(self._timeframe, [])
        if len(cs) < self._min_bars:
            return Signal("fixed", SignalLevel.NO_SETUP, timeframe=self._timeframe)
        last = cs[-1].close
        if self._direction == "long":
            stop = last - self._stop_offset
            tp = last + self._tp_offset
        else:
            stop = last + self._stop_offset
            tp = last - self._tp_offset
        return Signal(
            "fixed",
            self._level,
            timeframe=self._timeframe,
            direction=self._direction,
            entry_zone=(last, last),
            stop_loss=stop,
            take_profits=(tp,),
            invalidation="test",
        )
