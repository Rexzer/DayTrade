"""Signal engine + safety gating (pure Python).

Runs a set of strategies over a MarketContext and returns explainable signals.
Enforces the Phase 3 safety rule: signal generation STOPS when market data is
stale/disconnected or when required timeframe data is missing.

The engine never executes trades — it only classifies setups. Execution is a
separate concern handled (much later) by the risk + execution engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from strategy_engine.regime import RegimeDetector
from strategy_engine.strategies import build_builtin_strategies
from strategy_engine.strategy import MarketContext, SignalLevel, Strategy

# Data states in which live signals must not be generated.
_HALT_STATES = {"stale", "disconnected"}


@dataclass
class EvaluationResult:
    signals_allowed: bool
    reason: str
    signals: list[dict] = field(default_factory=list)
    regime: dict | None = None

    def to_dict(self) -> dict:
        return {
            "signals_allowed": self.signals_allowed,
            "reason": self.reason,
            "regime": self.regime,
            "signals": self.signals,
        }


class SignalEngine:
    """Evaluates strategies and applies safety gating."""

    def __init__(self, strategies: list[Strategy] | None = None) -> None:
        self.strategies: list[Strategy] = strategies or build_builtin_strategies()
        self.detector = RegimeDetector()

    def strategy_names(self) -> dict[str, str]:
        return {s.key: s.metadata.name for s in self.strategies}

    def evaluate_all(
        self,
        context: MarketContext,
        *,
        data_status: str | None = None,
        primary_timeframe: str = "1h",
    ) -> EvaluationResult:
        """Evaluate every strategy, halting entirely if data is unsafe."""
        status = (data_status or "disconnected").lower()
        if status in _HALT_STATES:
            return EvaluationResult(
                signals_allowed=False,
                reason=(
                    f"Signal generation halted: market data is {status.upper()}. "
                    "No signals are produced on stale/disconnected data."
                ),
            )
        if not context.candles:
            return EvaluationResult(
                signals_allowed=False,
                reason="No candle data available for any timeframe.",
            )

        # Regime from the primary timeframe (fallback: first available).
        regime_candles = context.candles.get(primary_timeframe)
        if not regime_candles:
            for _tf, cs in context.candles.items():
                if cs:
                    regime_candles = cs
                    break
        regime = self.detector.detect(regime_candles or [])

        names = self.strategy_names()
        signals: list[dict] = []
        for strat in self.strategies:
            try:
                sig = strat.evaluate(context)
            except Exception as exc:  # noqa: BLE001 - one bad strategy must not break others
                signals.append(
                    {
                        "strategy_key": strat.key,
                        "strategy_name": names.get(strat.key, strat.key),
                        "level": SignalLevel.NO_SETUP.value,
                        "level_name": SignalLevel.NO_SETUP.name,
                        "error": str(exc),
                    }
                )
                continue
            payload = sig.to_dict()
            payload["strategy_name"] = names.get(strat.key, strat.key)
            signals.append(payload)

        # Most actionable first.
        signals.sort(
            key=lambda s: (s.get("level", 0), s.get("confidence_score") or 0), reverse=True
        )
        return EvaluationResult(
            signals_allowed=True,
            reason="ok",
            signals=signals,
            regime=regime.to_dict(),
        )
