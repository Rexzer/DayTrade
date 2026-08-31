"""Trend Following strategy (pure Python).

Trades in the direction of an established trend confirmed by EMA alignment,
market structure (higher highs/lows) and trend strength (ADX). Not guaranteed
profitable — a hypothesis to be backtested.
"""

from __future__ import annotations

from strategy_engine.indicators import adx, atr, ema, last_defined, rsi
from strategy_engine.regime import RegimeDetector
from strategy_engine.scoring import ScoreCard
from strategy_engine.strategies import _common as C
from strategy_engine.strategy import (
    MarketContext,
    MarketRegime,
    Signal,
    Strategy,
    StrategyMetadata,
)

PRIMARY_TF = "1h"


class TrendFollowingStrategy(Strategy):
    metadata = StrategyMetadata(
        key="trend_following",
        name="Trend Following",
        description=(
            "Enters in the direction of an established trend when EMA "
            "alignment, market structure and ADX agree."
        ),
        suitable_timeframes=("1h", "4h"),
        suitable_regimes=(MarketRegime.STRONG_BULLISH, MarketRegime.STRONG_BEARISH),
        indicators=("EMA20", "EMA50", "EMA200", "ADX", "RSI", "ATR"),
        entry_conditions=(
            "EMA20 above/below EMA50 in trend direction",
            "Price on trend side of EMA50",
            "Market structure agrees (HH/HL or LH/LL)",
        ),
        confirmation_conditions=("ADX >= 25 (trend strength)", "RSI on trend side of 50"),
        exit_conditions=("Take-profit hit", "Trailing structure break"),
        stop_loss_logic="Beyond the most recent swing (buffered by 0.2*ATR).",
        take_profit_logic="1.5R and 2.5R from entry.",
        invalidation_logic="Close back through EMA50 against the trade.",
    )

    def evaluate(self, context: MarketContext) -> Signal:
        candles = C.get_candles(context, PRIMARY_TF)
        if len(candles) < 60:
            return C.no_setup(self.key, PRIMARY_TF, "Insufficient 1H history for trend analysis.")

        d = C.extract(candles)
        price = d.closes[-1]
        ema20 = last_defined(ema(d.closes, 20))
        ema50 = last_defined(ema(d.closes, 50))
        ema200 = last_defined(ema(d.closes, 200)) if len(d.closes) >= 200 else None
        adx_val = last_defined(adx(d.highs, d.lows, d.closes, 14).adx) or 0.0
        rsi_val = last_defined(rsi(d.closes, 14)) or 50.0
        atr_val = last_defined(atr(d.highs, d.lows, d.closes, 14)) or (price * 0.003)
        regime = RegimeDetector().detect(candles)

        bullish = ema20 is not None and ema50 is not None and ema20 > ema50 and price > ema50
        bearish = ema20 is not None and ema50 is not None and ema20 < ema50 and price < ema50
        direction = "long" if bullish else "short" if bearish else "long"

        if bullish:
            structure_ok = regime.details.get("structure_trend") == "bullish"
            core = [
                ("EMA20 > EMA50", ema20 > ema50),
                ("Price above EMA50", price > ema50),
                ("Bullish market structure (HH/HL)", structure_ok),
            ]
            confirmations = [
                ("ADX >= 25 (strong trend)", adx_val >= 25),
                ("RSI above 50 (momentum)", rsi_val >= 50),
            ]
            swing_low = regime.details.get("bb_lower") or min(d.lows[-10:])
            stop = min(min(d.lows[-10:]), swing_low) - 0.2 * atr_val
            entry_zone = (price - 0.15 * atr_val, price)
            targets = C.build_targets(price, stop, "long")
            inval = f"1H close below EMA50 (~{ema50:.2f}) invalidates the long."
        elif bearish:
            structure_ok = regime.details.get("structure_trend") == "bearish"
            core = [
                ("EMA20 < EMA50", ema20 < ema50),
                ("Price below EMA50", price < ema50),
                ("Bearish market structure (LH/LL)", structure_ok),
            ]
            confirmations = [
                ("ADX >= 25 (strong trend)", adx_val >= 25),
                ("RSI below 50 (momentum)", rsi_val <= 50),
            ]
            stop = max(d.highs[-10:]) + 0.2 * atr_val
            entry_zone = (price, price + 0.15 * atr_val)
            targets = C.build_targets(price, stop, "short")
            inval = f"1H close above EMA50 (~{ema50:.2f}) invalidates the short."
        else:
            return C.no_setup(self.key, PRIMARY_TF, "No clear EMA trend alignment.")

        score = ScoreCard()
        score.award("trend", 1.0 if adx_val >= 25 else 0.5, f"ADX={adx_val:.1f}")
        score.award(
            "structure",
            1.0 if regime.details.get("structure_trend") in ("bullish", "bearish") else 0.3,
            f"structure={regime.details.get('structure_trend')}",
        )
        score.award("momentum", min(abs(rsi_val - 50) / 20.0, 1.0), f"RSI={rsi_val:.1f}")
        score.award("entry_trigger", 1.0 if bullish or bearish else 0.0, "EMA-aligned entry")
        rr = C.risk_reward(price, stop, targets[0]) if targets else None
        score.award("risk_reward", 1.0 if (rr and rr >= 1.5) else 0.4, f"R:R={rr}")

        if ema200 is not None:
            core.append(
                (
                    f"Price on trend side of EMA200 (~{ema200:.2f})",
                    price > ema200 if direction == "long" else price < ema200,
                )
            )

        return C.finalize(
            strategy_key=self.key,
            timeframe=PRIMARY_TF,
            direction=direction,
            regime=regime.regime,
            core=core,
            confirmations=confirmations,
            entry_zone=entry_zone,
            stop_loss=stop,
            take_profits=targets,
            invalidation=inval,
            score=score,
        )
