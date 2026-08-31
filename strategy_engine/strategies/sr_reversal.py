"""Support/Resistance Reversal strategy (pure Python).

Looks for price reaching a significant support/resistance zone and rejecting it
with a wick/rejection candle and a momentum shift. Not every touch is a trade —
confirmation is required. Not guaranteed profitable.
"""

from __future__ import annotations

from strategy_engine.indicators import atr, last_defined, rsi
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
from strategy_engine.structure import nearest_level, support_resistance

PRIMARY_TF = "15m"


def _bullish_rejection(candle) -> bool:
    body = abs(candle.close - candle.open)
    lower_wick = min(candle.open, candle.close) - candle.low
    return lower_wick >= max(body, 1e-9)


def _bearish_rejection(candle) -> bool:
    body = abs(candle.close - candle.open)
    upper_wick = candle.high - max(candle.open, candle.close)
    return upper_wick >= max(body, 1e-9)


class SupportResistanceReversalStrategy(Strategy):
    metadata = StrategyMetadata(
        key="sr_reversal",
        name="Support/Resistance Reversal",
        description=(
            "Signals a reversal when price reaches a significant S/R zone and "
            "rejects it with a wick and a momentum shift."
        ),
        suitable_timeframes=("15m", "1h"),
        suitable_regimes=(MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY),
        indicators=("Support/Resistance", "RSI", "ATR"),
        entry_conditions=("Price at a significant S/R zone", "Rejection candle (wick) at the zone"),
        confirmation_conditions=("RSI momentum shift", "Multiple touches on the zone"),
        exit_conditions=("Take-profit hit", "Close through the zone"),
        stop_loss_logic="Just beyond the S/R zone (buffered by 0.4*ATR).",
        take_profit_logic="1.5R and 2.5R toward the opposite zone.",
        invalidation_logic="Decisive close through the S/R zone.",
    )

    def evaluate(self, context: MarketContext) -> Signal:
        candles = C.get_candles(context, PRIMARY_TF)
        if len(candles) < 40:
            return C.no_setup(self.key, PRIMARY_TF, "Insufficient 15M history for S/R analysis.")

        d = C.extract(candles)
        price = d.closes[-1]
        last = candles[-1]
        atr_val = last_defined(atr(d.highs, d.lows, d.closes, 14)) or (price * 0.003)
        rsi_val = last_defined(rsi(d.closes, 14)) or 50.0
        regime = RegimeDetector().detect(candles)
        levels = support_resistance(d.highs, d.lows)

        support = nearest_level(levels, price, "support")
        resistance = nearest_level(levels, price, "resistance")
        near = 0.5 * atr_val

        at_support = support is not None and abs(price - support.price) <= near
        at_resistance = resistance is not None and abs(price - resistance.price) <= near

        if at_support and (
            not at_resistance or (price - support.price) <= (resistance.price - price)
        ):
            direction = "long"
            core = [
                (f"Price at support (~{support.price:.2f})", True),
                ("Bullish rejection candle", _bullish_rejection(last)),
            ]
            confirmations = [
                ("RSI oversold turning up (<45)", rsi_val < 45),
                (f"Support tested {support.touches}x", support.touches >= 2),
            ]
            stop = support.price - 0.4 * atr_val
            entry_zone = (support.price, price)
            targets = C.build_targets(price, stop, "long")
            inval = f"15M close below support (~{support.price:.2f}) invalidates the long."
        elif at_resistance:
            direction = "short"
            core = [
                (f"Price at resistance (~{resistance.price:.2f})", True),
                ("Bearish rejection candle", _bearish_rejection(last)),
            ]
            confirmations = [
                ("RSI overbought turning down (>55)", rsi_val > 55),
                (f"Resistance tested {resistance.touches}x", resistance.touches >= 2),
            ]
            stop = resistance.price + 0.4 * atr_val
            entry_zone = (price, resistance.price)
            targets = C.build_targets(price, stop, "short")
            inval = f"15M close above resistance (~{resistance.price:.2f}) invalidates the short."
        else:
            return C.no_setup(self.key, PRIMARY_TF, "Price not at a significant S/R zone.")

        score = ScoreCard()
        score.award("support_resistance", 1.0, "at a significant S/R zone")
        score.award(
            "entry_trigger",
            1.0 if core[1][1] else 0.0,
            "rejection candle present" if core[1][1] else "awaiting rejection",
        )
        score.award("momentum", 1.0 if confirmations[0][1] else 0.4, f"RSI={rsi_val:.1f}")
        score.award("structure", 0.7, f"regime={regime.regime.value}")
        rr = (
            C.risk_reward((entry_zone[0] + entry_zone[1]) / 2, stop, targets[0])
            if targets
            else None
        )
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
