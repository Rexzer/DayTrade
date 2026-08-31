"""Market-regime detection (pure Python).

Classifies the current market into one of nine regimes using a transparent,
inspectable combination of trend (EMA alignment + slope), trend strength
(ADX), volatility (ATR% and Bollinger bandwidth) and structure. Every
classification returns the metrics that produced it so the UI can explain it.

Precedence: BREAKOUT > (strong/weak) TREND > RANGING > HIGH/LOW volatility >
UNCERTAIN. This keeps the primary label actionable while still surfacing
volatility via the details payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from strategy_engine.indicators import adx as adx_ind
from strategy_engine.indicators import atr as atr_ind
from strategy_engine.indicators import bollinger_bands, ema, last_defined
from strategy_engine.strategy import MarketRegime
from strategy_engine.structure import analyze_structure


@dataclass(frozen=True)
class RegimeResult:
    regime: MarketRegime
    trend: str  # bullish | bearish | neutral
    strength: float | None  # ADX
    volatility: str  # high | normal | low
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "trend": self.trend,
            "strength": self.strength,
            "volatility": self.volatility,
            "details": self.details,
        }


@dataclass
class RegimeThresholds:
    adx_strong: float = 25.0
    adx_weak: float = 18.0
    atr_pct_high: float = 0.010  # 1.0% of price per bar => high volatility
    atr_pct_low: float = 0.0025  # 0.25% => low volatility
    breakout_lookback: int = 20


class RegimeDetector:
    """Detects the market regime from OHLC candles."""

    def __init__(self, thresholds: RegimeThresholds | None = None) -> None:
        self.t = thresholds or RegimeThresholds()

    def detect(self, candles: list) -> RegimeResult:
        """Classify ``candles`` (list of objects with open/high/low/close)."""
        if not candles or len(candles) < 30:
            return RegimeResult(
                MarketRegime.UNKNOWN,
                "neutral",
                None,
                "normal",
                {"reason": "insufficient_data", "bars": len(candles or [])},
            )

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        price = closes[-1]

        ema20 = last_defined(ema(closes, 20))
        ema50 = last_defined(ema(closes, 50)) if len(closes) >= 50 else None
        ema200 = last_defined(ema(closes, 200)) if len(closes) >= 200 else None
        adx_res = adx_ind(highs, lows, closes, 14)
        adx_val = last_defined(adx_res.adx)
        atr_val = last_defined(atr_ind(highs, lows, closes, 14))
        bb = bollinger_bands(closes, 20, 2.0)
        atr_pct = (atr_val / price) if (atr_val and price) else None

        # Volatility classification.
        volatility = "normal"
        if atr_pct is not None:
            if atr_pct >= self.t.atr_pct_high:
                volatility = "high"
            elif atr_pct <= self.t.atr_pct_low:
                volatility = "low"

        # EMA-based trend direction.
        trend = "neutral"
        if ema20 is not None and ema50 is not None:
            if ema20 > ema50 and price > ema50:
                trend = "bullish"
            elif ema20 < ema50 and price < ema50:
                trend = "bearish"
        if ema200 is not None:
            # 200-EMA acts as a tie-breaker / strengthener.
            if trend == "bullish" and price < ema200:
                trend = "neutral" if adx_val and adx_val < self.t.adx_strong else trend
            if trend == "bearish" and price > ema200:
                trend = "neutral" if adx_val and adx_val < self.t.adx_strong else trend

        structure = analyze_structure(highs, lows)

        # Breakout detection: price closing beyond the prior-range extreme with
        # an expansion in volatility.
        breakout = self._is_breakout(highs, lows, closes, atr_pct)

        details = {
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "adx": adx_val,
            "atr": atr_val,
            "atr_pct": atr_pct,
            "bb_upper": last_defined(bb.upper),
            "bb_lower": last_defined(bb.lower),
            "structure_trend": structure.trend,
            "breakout": breakout,
        }

        regime = self._classify(trend, adx_val, volatility, breakout)
        return RegimeResult(regime, trend, adx_val, volatility, details)

    def _is_breakout(
        self, highs: list[float], lows: list[float], closes: list[float], atr_pct: float | None
    ) -> bool:
        lb = self.t.breakout_lookback
        if len(closes) < lb + 2:
            return False
        prior_high = max(highs[-lb - 1 : -1])
        prior_low = min(lows[-lb - 1 : -1])
        broke_up = closes[-1] > prior_high
        broke_down = closes[-1] < prior_low
        expanding = atr_pct is not None and atr_pct >= self.t.atr_pct_high * 0.8
        return (broke_up or broke_down) and expanding

    def _classify(
        self, trend: str, adx_val: float | None, volatility: str, breakout: bool
    ) -> MarketRegime:
        if breakout:
            return MarketRegime.BREAKOUT
        strong = adx_val is not None and adx_val >= self.t.adx_strong
        weak_trend = adx_val is not None and self.t.adx_weak <= adx_val < self.t.adx_strong
        if trend == "bullish":
            if strong:
                return MarketRegime.STRONG_BULLISH
            if weak_trend:
                return MarketRegime.WEAK_BULLISH
        if trend == "bearish":
            if strong:
                return MarketRegime.STRONG_BEARISH
            if weak_trend:
                return MarketRegime.WEAK_BEARISH
        # Not trending.
        if adx_val is not None and adx_val < self.t.adx_weak:
            if volatility == "high":
                return MarketRegime.HIGH_VOLATILITY
            if volatility == "low":
                return MarketRegime.LOW_VOLATILITY
            return MarketRegime.RANGING
        if volatility == "high":
            return MarketRegime.HIGH_VOLATILITY
        if volatility == "low":
            return MarketRegime.LOW_VOLATILITY
        return MarketRegime.UNCERTAIN
