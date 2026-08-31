"""Breakout + Retest strategy (pure Python).

Identifies a consolidation range, a break of its boundary, then a retest of the
broken level before signalling — avoiding blindly chasing the first breakout
candle. Not guaranteed profitable.
"""

from __future__ import annotations

from strategy_engine.indicators import atr, last_defined
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
RANGE_LOOKBACK = 20


class BreakoutRetestStrategy(Strategy):
    metadata = StrategyMetadata(
        key="breakout_retest",
        name="Breakout + Retest",
        description=(
            "Detects a range breakout and waits for a retest of the broken "
            "level with a confirmation candle before signalling."
        ),
        suitable_timeframes=("15m", "1h"),
        suitable_regimes=(MarketRegime.BREAKOUT, MarketRegime.LOW_VOLATILITY),
        indicators=("Range high/low", "ATR"),
        entry_conditions=("Prior consolidation range", "Break of range boundary"),
        confirmation_conditions=(
            "Retest of broken level",
            "Confirmation candle in break direction",
        ),
        exit_conditions=("Take-profit hit", "Close back inside the range"),
        stop_loss_logic="Just beyond the retested level (buffered by 0.3*ATR).",
        take_profit_logic="1.5R and 2.5R, or the measured-move range height.",
        invalidation_logic="Close back inside the prior range.",
    )

    def evaluate(self, context: MarketContext) -> Signal:
        candles = C.get_candles(context, PRIMARY_TF)
        if len(candles) < RANGE_LOOKBACK + 6:
            return C.no_setup(
                self.key, PRIMARY_TF, "Insufficient 15M history for breakout analysis."
            )

        d = C.extract(candles)
        price = d.closes[-1]
        atr_val = last_defined(atr(d.highs, d.lows, d.closes, 14)) or (price * 0.003)
        regime = RegimeDetector().detect(candles)

        # Range measured over the window BEFORE the last few (breakout) bars.
        window_h = d.highs[-RANGE_LOOKBACK - 4 : -4]
        window_l = d.lows[-RANGE_LOOKBACK - 4 : -4]
        range_high = max(window_h)
        range_low = min(window_l)
        range_height = range_high - range_low
        recent_max = max(d.highs[-4:])
        recent_min = min(d.lows[-4:])

        broke_up = recent_max > range_high
        broke_down = recent_min < range_low

        if broke_up:
            direction = "long"
            retest = abs(price - range_high) <= 0.4 * atr_val
            back_above = price >= range_high
            core = [
                (f"Broke above range high (~{range_high:.2f})", True),
                ("Retest of broken resistance", retest),
            ]
            confirmations = [
                ("Holding above broken level", back_above),
                ("Confirmation candle (close up)", d.closes[-1] >= d.opens[-1]),
            ]
            stop = range_high - 0.3 * atr_val
            entry_zone = (range_high, price if price > range_high else range_high + 0.1 * atr_val)
            targets = C.build_targets(max(price, range_high), stop, "long")
            inval = f"15M close back inside the range (below ~{range_high:.2f})."
        elif broke_down:
            direction = "short"
            retest = abs(price - range_low) <= 0.4 * atr_val
            back_below = price <= range_low
            core = [
                (f"Broke below range low (~{range_low:.2f})", True),
                ("Retest of broken support", retest),
            ]
            confirmations = [
                ("Holding below broken level", back_below),
                ("Confirmation candle (close down)", d.closes[-1] <= d.opens[-1]),
            ]
            stop = range_low + 0.3 * atr_val
            entry_zone = (price if price < range_low else range_low - 0.1 * atr_val, range_low)
            targets = C.build_targets(min(price, range_low), stop, "short")
            inval = f"15M close back inside the range (above ~{range_low:.2f})."
        else:
            return C.no_setup(self.key, PRIMARY_TF, "No range breakout detected.")

        score = ScoreCard()
        score.award("structure", 1.0, "range breakout identified")
        score.award(
            "entry_trigger",
            1.0 if core[1][1] else 0.3,
            "retest in progress" if core[1][1] else "awaiting retest",
        )
        score.award(
            "momentum",
            1.0 if regime.regime == MarketRegime.BREAKOUT else 0.5,
            f"regime={regime.regime.value}",
        )
        score.award("support_resistance", 1.0, f"range height={range_height:.2f}")
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
