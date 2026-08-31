"""Multi-timeframe analysis (pure Python).

Summarizes trend / structure / momentum / signal-state for the standard stack
(4H, 1H, 15M, 5M) so the dashboard can show top-down context. Populated from
the same indicator/structure/regime engines used by strategies.
"""

from __future__ import annotations

from strategy_engine.indicators import ema, last_defined, rsi
from strategy_engine.regime import RegimeDetector
from strategy_engine.strategy import MarketContext
from strategy_engine.structure import analyze_structure

MTF_TIMEFRAMES = ("4h", "1h", "15m", "5m")


def _trend(closes: list[float]) -> str:
    if len(closes) < 55:
        return "unknown"
    e20 = last_defined(ema(closes, 20))
    e50 = last_defined(ema(closes, 50))
    if e20 is None or e50 is None:
        return "unknown"
    if e20 > e50 and closes[-1] > e50:
        return "bullish"
    if e20 < e50 and closes[-1] < e50:
        return "bearish"
    return "neutral"


def _momentum(closes: list[float]) -> str:
    r = last_defined(rsi(closes, 14))
    if r is None:
        return "unknown"
    if r >= 60:
        return "strong_up"
    if r >= 50:
        return "up"
    if r <= 40:
        return "strong_down"
    return "down"


class MultiTimeframeAnalyzer:
    def __init__(self) -> None:
        self.detector = RegimeDetector()

    def analyze(self, context: MarketContext) -> dict:
        rows = []
        for tf in MTF_TIMEFRAMES:
            candles = context.candles.get(tf) or []
            if len(candles) < 30:
                rows.append(
                    {
                        "timeframe": tf.upper(),
                        "trend": "unknown",
                        "structure": "unknown",
                        "momentum": "unknown",
                        "signal_state": "no_data",
                    }
                )
                continue
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]
            trend = _trend(closes)
            structure = analyze_structure(highs, lows).trend
            momentum = _momentum(closes)
            # Simple aligned/mixed signal-state summary.
            if trend in ("bullish", "bearish") and structure == trend:
                state = "aligned"
            elif trend == "unknown":
                state = "unknown"
            else:
                state = "mixed"
            rows.append(
                {
                    "timeframe": tf.upper(),
                    "trend": trend,
                    "structure": structure,
                    "momentum": momentum,
                    "signal_state": state,
                }
            )
        return {"timeframes": rows}
