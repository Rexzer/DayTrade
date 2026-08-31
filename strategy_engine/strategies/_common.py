"""Shared helpers for built-in strategies (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass

from strategy_engine.scoring import ScoreCard
from strategy_engine.strategy import MarketContext, Signal, SignalLevel


@dataclass(frozen=True)
class OHLCV:
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float | None]

    def __len__(self) -> int:
        return len(self.closes)


def extract(candles: list) -> OHLCV:
    """Pull OHLCV arrays from a list of Candle objects."""
    return OHLCV(
        opens=[c.open for c in candles],
        highs=[c.high for c in candles],
        lows=[c.low for c in candles],
        closes=[c.close for c in candles],
        volumes=[getattr(c, "volume", None) for c in candles],
    )


def get_candles(context: MarketContext, timeframe: str) -> list:
    return context.candles.get(timeframe, []) or []


def level_from_conditions(
    core_met: int, core_total: int, confirm_met: int, confirm_total: int
) -> SignalLevel:
    """Map met/total conditions to a signal level.

    * No directional core met            -> NO_SETUP
    * Some core met                       -> WATCH
    * All core met, confirmation missing  -> POTENTIAL_SETUP
    * All core + all confirmation met     -> CONFIRMED_SETUP
    """
    if core_total == 0 or core_met == 0:
        return SignalLevel.NO_SETUP
    if core_met < core_total:
        return SignalLevel.WATCH
    # All core satisfied.
    if confirm_total == 0:
        return SignalLevel.CONFIRMED_SETUP
    if confirm_met >= confirm_total:
        return SignalLevel.CONFIRMED_SETUP
    if confirm_met == 0:
        return SignalLevel.WATCH
    return SignalLevel.POTENTIAL_SETUP


def no_setup(strategy_key: str, timeframe: str, note: str) -> Signal:
    return Signal(
        strategy_key=strategy_key,
        level=SignalLevel.NO_SETUP,
        timeframe=timeframe,
        notes=note,
    )


def risk_reward(entry: float, stop: float, target: float) -> float | None:
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    return round(abs(target - entry) / risk, 2)


def build_targets(
    entry: float, stop: float, direction: str, r_multiples: tuple[float, ...] = (1.5, 2.5)
) -> tuple[float, ...]:
    """Derive take-profit levels as R multiples of the entry-to-stop risk."""
    risk = abs(entry - stop)
    if risk <= 0:
        return ()
    if direction == "long":
        return tuple(round(entry + m * risk, 3) for m in r_multiples)
    return tuple(round(entry - m * risk, 3) for m in r_multiples)


def summarize(conditions: list[tuple[str, bool]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split labelled conditions into (met, missing) tuples."""
    met = tuple(label for label, ok in conditions if ok)
    missing = tuple(label for label, ok in conditions if not ok)
    return met, missing


def finalize(
    *,
    strategy_key: str,
    timeframe: str,
    direction: str,
    regime,
    core: list[tuple[str, bool]],
    confirmations: list[tuple[str, bool]],
    entry_zone: tuple[float, float],
    stop_loss: float,
    take_profits: tuple[float, ...],
    invalidation: str,
    score: ScoreCard,
    notes: str | None = None,
) -> Signal:
    """Assemble a fully-explained Signal from evaluated conditions."""
    core_met = sum(1 for _, ok in core if ok)
    confirm_met = sum(1 for _, ok in confirmations if ok)
    level = level_from_conditions(core_met, len(core), confirm_met, len(confirmations))

    met_labels, missing_labels = summarize(core + confirmations)
    entry_mid = sum(entry_zone) / 2.0
    rr = risk_reward(entry_mid, stop_loss, take_profits[0]) if take_profits else None

    # If there is no tradable structure yet, keep prices out of the signal.
    if level in (SignalLevel.NO_SETUP,):
        return Signal(
            strategy_key=strategy_key,
            level=level,
            regime=regime,
            timeframe=timeframe,
            direction=direction,
            confirmations=met_labels,
            missing_confirmations=missing_labels,
            confidence_score=score.total,
            notes=notes,
        )

    return Signal(
        strategy_key=strategy_key,
        level=level,
        regime=regime,
        timeframe=timeframe,
        direction=direction,
        entry_zone=(round(entry_zone[0], 3), round(entry_zone[1], 3)),
        stop_loss=round(stop_loss, 3),
        take_profits=take_profits,
        risk_reward=rr,
        confirmations=met_labels,
        missing_confirmations=missing_labels,
        invalidation=invalidation,
        confidence_score=score.total,
        notes=notes,
    )
