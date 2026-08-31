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
