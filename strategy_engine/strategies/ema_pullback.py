"""EMA Pullback strategy (pure Python).

In an established trend, waits for a pullback into the EMA zone and a rejection
candle before signalling a continuation entry. Not guaranteed profitable.
"""

from __future__ import annotations

from strategy_engine.indicators import atr, ema, last_defined, rsi
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

PRIMARY_TF = "15m"


def _bullish_rejection(candle) -> bool:
    body = abs(candle.close - candle.open)
    lower_wick = min(candle.open, candle.close) - candle.low
    return candle.close >= candle.open and lower_wick >= body * 0.8


def _bearish_rejection(candle) -> bool:
    body = abs(candle.close - candle.open)
    upper_wick = candle.high - max(candle.open, candle.close)
    return candle.close <= candle.open and upper_wick >= body * 0.8


class EmaPullbackStrategy(Strategy):
    metadata = StrategyMetadata(
        key="ema_pullback",
        name="EMA Pullback",
        description=(
            "Waits for price to pull back into the EMA20/50 zone within an "
            "established trend, then a rejection candle to continue."
        ),
        suitable_timeframes=("15m", "1h"),
        suitable_regimes=(
            MarketRegime.STRONG_BULLISH,
            MarketRegime.WEAK_BULLISH,
            MarketRegime.STRONG_BEARISH,
            MarketRegime.WEAK_BEARISH,
        ),
        indicators=("EMA20", "EMA50", "RSI", "ATR"),
        entry_conditions=(
            "Established trend (EMA20 vs EMA50)",
            "Pullback into the EMA20-EMA50 zone",
        ),
        confirmation_conditions=(
            "Rejection candle in trend direction",
            "RSI turning from pullback",
        ),
        exit_conditions=("Take-profit hit", "Close beyond EMA50 against trade"),
        stop_loss_logic="Beyond the pullback extreme (buffered by 0.3*ATR).",
        take_profit_logic="1.5R and 2.5R from entry.",
        invalidation_logic="Close beyond EMA50 against the intended direction.",
    )

    def evaluate(self, context: MarketContext) -> Signal:
        candles = C.get_candles(context, PRIMARY_TF)
        if len(candles) < 55:
            return C.no_setup(
                self.key, PRIMARY_TF, "Insufficient 15M history for pullback analysis."
            )

        d = C.extract(candles)
        price = d.closes[-1]
        last = candles[-1]
        ema20 = last_defined(ema(d.closes, 20))
        ema50 = last_defined(ema(d.closes, 50))
        rsi_val = last_defined(rsi(d.closes, 14)) or 50.0
        atr_val = last_defined(atr(d.highs, d.lows, d.closes, 14)) or (price * 0.003)
        regime = RegimeDetector().detect(candles)

        if ema20 is None or ema50 is None:
            return C.no_setup(self.key, PRIMARY_TF, "EMA data unavailable.")

        up_trend = ema20 > ema50
        zone_hi = max(ema20, ema50)
        zone_lo = min(ema20, ema50)

        if up_trend:
            direction = "long"
            pulled_back = last.low <= zone_hi + 0.25 * atr_val  # dipped into/near zone
            core = [
                ("Uptrend (EMA20 > EMA50)", True),
                (f"Pullback into EMA zone (~{zone_lo:.2f}-{zone_hi:.2f})", pulled_back),
            ]
            confirmations = [
                ("Bullish rejection candle", _bullish_rejection(last)),
                ("RSI recovering above 45", rsi_val >= 45),
            ]
            stop = min(last.low, zone_lo) - 0.3 * atr_val
            entry_zone = (zone_lo, price)
            targets = C.build_targets(price, stop, "long")
            inval = f"15M close below EMA50 (~{ema50:.2f}) invalidates the pullback long."
        else:
            direction = "short"
            pulled_back = last.high >= zone_lo - 0.25 * atr_val
            core = [
                ("Downtrend (EMA20 < EMA50)", True),
                (f"Pullback into EMA zone (~{zone_lo:.2f}-{zone_hi:.2f})", pulled_back),
            ]
            confirmations = [
                ("Bearish rejection candle", _bearish_rejection(last)),
                ("RSI fading below 55", rsi_val <= 55),
            ]
            stop = max(last.high, zone_hi) + 0.3 * atr_val
            entry_zone = (price, zone_hi)
            targets = C.build_targets(price, stop, "short")
            inval = f"15M close above EMA50 (~{ema50:.2f}) invalidates the pullback short."

        score = ScoreCard()
        score.award("trend", 1.0, f"EMA trend {'up' if up_trend else 'down'}")
        score.award("structure", 1.0 if core[1][1] else 0.2, "pullback into EMA zone")
        score.award("momentum", min(abs(rsi_val - 50) / 20.0, 1.0), f"RSI={rsi_val:.1f}")
        score.award(
            "entry_trigger",
            1.0 if confirmations[0][1] else 0.0,
            "rejection candle present" if confirmations[0][1] else "awaiting rejection candle",
        )
        rr = C.risk_reward(price, stop, targets[0]) if targets else None
        score.award("risk_reward", 1.0 if (rr and rr >= 1.5) else 0.4, f"R:R={rr}")

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
