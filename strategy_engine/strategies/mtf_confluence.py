"""Multi-Timeframe Confluence strategy (pure Python).

Requires agreement across timeframes: 4H and 1H define the trend, 15M provides
a pullback, and 5M provides the entry trigger. Only a full stack of agreement
yields a high-quality (CONFIRMED) setup. Not guaranteed profitable.
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


def _trend(closes: list[float]) -> str:
    if len(closes) < 55:
        return "neutral"
    e20 = last_defined(ema(closes, 20))
    e50 = last_defined(ema(closes, 50))
    if e20 is None or e50 is None:
        return "neutral"
    if e20 > e50 and closes[-1] > e50:
        return "bullish"
    if e20 < e50 and closes[-1] < e50:
        return "bearish"
    return "neutral"


class MultiTimeframeConfluenceStrategy(Strategy):
    metadata = StrategyMetadata(
        key="mtf_confluence",
        name="Multi-Timeframe Confluence",
        description=(
            "Aligns 4H and 1H trend with a 15M pullback and a 5M entry trigger. "
            "Only full confluence produces a confirmed setup."
        ),
        suitable_timeframes=("4h", "1h", "15m", "5m"),
        suitable_regimes=(MarketRegime.STRONG_BULLISH, MarketRegime.STRONG_BEARISH),
        indicators=("EMA20", "EMA50", "RSI", "ATR"),
        entry_conditions=("4H trend direction", "1H trend agrees with 4H"),
        confirmation_conditions=("15M pullback into value", "5M trigger candle in trend direction"),
        exit_conditions=("Take-profit hit", "1H trend flips"),
        stop_loss_logic="Beyond the 5M swing / 15M pullback extreme (buffered by ATR).",
        take_profit_logic="1.5R and 2.5R from entry.",
        invalidation_logic="1H close that flips the 1H trend against the trade.",
    )

    def evaluate(self, context: MarketContext) -> Signal:
        c4 = C.get_candles(context, "4h")
        c1 = C.get_candles(context, "1h")
        c15 = C.get_candles(context, "15m")
        c5 = C.get_candles(context, "5m")
        if min(len(c4), len(c1), len(c15), len(c5)) < 55:
            return C.no_setup(
                self.key, "5m", "Multi-timeframe data incomplete (need 4H/1H/15M/5M history)."
            )

        t4 = _trend([c.close for c in c4])
        t1 = _trend([c.close for c in c1])
        d15 = C.extract(c15)
        d5 = C.extract(c5)
        price = d5.closes[-1]
        atr5 = last_defined(atr(d5.highs, d5.lows, d5.closes, 14)) or (price * 0.002)
        ema50_15 = last_defined(ema(d15.closes, 50))
        rsi5 = last_defined(rsi(d5.closes, 14)) or 50.0
        regime = RegimeDetector().detect(c1)

        aligned = t4 == t1 and t4 in ("bullish", "bearish")
        if not aligned:
            # Still emit a WATCH-level explanation of what's missing.
            direction = t4 if t4 in ("bullish", "bearish") else "long"
            core = [
                (f"4H trend {t4}", t4 in ("bullish", "bearish")),
                ("1H trend agrees with 4H", t4 == t1 and t4 != "neutral"),
            ]
            confirmations = [("15M pullback", False), ("5M trigger", False)]
            score = ScoreCard()
            score.award("trend", 0.5 if t4 in ("bullish", "bearish") else 0.0, f"4H={t4}, 1H={t1}")
            return C.finalize(
                strategy_key=self.key,
                timeframe="5m",
                direction=direction,
                regime=regime.regime,
                core=core,
                confirmations=confirmations,
                entry_zone=(price, price),
                stop_loss=price,
                take_profits=(),
                invalidation="Awaiting 4H/1H trend agreement.",
                score=score,
                notes="Timeframes not yet aligned.",
            )

        direction = "long" if t4 == "bullish" else "short"
        if direction == "long":
            pullback_15 = ema50_15 is not None and c15[-1].low <= ema50_15 + 0.5 * atr5 * 3
            trigger_5 = d5.closes[-1] >= d5.opens[-1] and rsi5 >= 45
            stop = min(d5.lows[-6:]) - 0.5 * atr5
            targets = C.build_targets(price, stop, "long")
            inval = "1H close that turns the 1H trend bearish invalidates the long."
        else:
            pullback_15 = ema50_15 is not None and c15[-1].high >= ema50_15 - 0.5 * atr5 * 3
            trigger_5 = d5.closes[-1] <= d5.opens[-1] and rsi5 <= 55
            stop = max(d5.highs[-6:]) + 0.5 * atr5
            targets = C.build_targets(price, stop, "short")
            inval = "1H close that turns the 1H trend bullish invalidates the short."

        core = [
            (f"4H trend {t4}", True),
            (f"1H trend {t1} (agrees with 4H)", True),
        ]
        confirmations = [
            ("15M pullback into value", bool(pullback_15)),
            ("5M trigger candle in trend direction", bool(trigger_5)),
        ]

        score = ScoreCard()
        score.award("trend", 1.0, f"4H={t4}, 1H={t1} aligned")
        score.award(
            "structure",
            1.0 if pullback_15 else 0.3,
            "15M pullback" if pullback_15 else "no pullback yet",
        )
        score.award("momentum", min(abs(rsi5 - 50) / 20.0, 1.0), f"5M RSI={rsi5:.1f}")
        score.award(
            "entry_trigger",
            1.0 if trigger_5 else 0.0,
            "5M trigger" if trigger_5 else "awaiting 5M trigger",
        )
        rr = C.risk_reward(price, stop, targets[0]) if targets else None
        score.award("risk_reward", 1.0 if (rr and rr >= 1.5) else 0.4, f"R:R={rr}")

        return C.finalize(
            strategy_key=self.key,
            timeframe="5m",
            direction=direction,
            regime=regime.regime,
            core=core,
            confirmations=confirmations,
            entry_zone=(
                (price - 0.3 * atr5, price) if direction == "long" else (price, price + 0.3 * atr5)
            ),
            stop_loss=stop,
            take_profits=targets,
            invalidation=inval,
            score=score,
        )
