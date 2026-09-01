"""StrategyLabService — champion/challenger promotion funnel (backend wiring).

Thin orchestration over the pure ``strategy_lab.CandidatePipeline``. This first
slice manages the candidate lifecycle and the hard promotion gates and exposes
them via the API; the automated shadow-paper *runner* (executing challengers in
the paper engine on the live feed and feeding their metrics into
``record_shadow``) is the next increment that plugs into this same lifecycle.
"""

from __future__ import annotations

from backend.app.core.logging_config import get_logger
from strategy_lab import CandidatePipeline, PromotionGates

logger = get_logger("strategy_lab")


class StrategyLabService:
    def __init__(self) -> None:
        self.pipeline = CandidatePipeline(PromotionGates())

    def funnel(self) -> dict:
        return {"gates": self.pipeline.gates.to_dict(), **self.pipeline.funnel()}

    def register(self, key: str, name: str, source: str = "human") -> dict:
        try:
            cand = self.pipeline.register(key, name, source=source)
            logger.info("Candidate registered", extra={"context": {"key": key, "source": source}})
            return {"candidate": cand.to_dict()}
        except ValueError as exc:
            return {"error": str(exc)}

    def record_backtest(self, key: str, metrics: dict) -> dict:
        return self._record(lambda: self.pipeline.record_backtest(key, metrics), key)

    def record_walk_forward(self, key: str, metrics: dict) -> dict:
        return self._record(lambda: self.pipeline.record_walk_forward(key, metrics), key)

    def record_shadow(self, key: str, metrics: dict, champion_metrics: dict | None = None) -> dict:
        return self._record(
            lambda: self.pipeline.record_shadow(key, metrics, champion_metrics), key
        )

    def promote(self, key: str) -> dict:
        try:
            cand = self.pipeline.promote(key)
            logger.info("Candidate promoted to LIVE", extra={"context": {"key": key}})
            return {"candidate": cand.to_dict()}
        except (KeyError, ValueError) as exc:
            return {"error": str(exc)}

    def retire(self, key: str, reason: str = "Retired by operator.") -> dict:
        try:
            return {"candidate": self.pipeline.retire(key, reason).to_dict()}
        except KeyError as exc:
            return {"error": str(exc)}

    def _record(self, action, key: str) -> dict:
        try:
            result = action()
        except (KeyError, ValueError) as exc:
            return {"error": str(exc)}
        cand = self.pipeline.get(key)
        return {
            "gate": result.to_dict(),
            "candidate": cand.to_dict() if cand else None,
        }


_service: StrategyLabService | None = None


def get_lab_service() -> StrategyLabService:
    global _service
    if _service is None:
        _service = StrategyLabService()
    return _service
