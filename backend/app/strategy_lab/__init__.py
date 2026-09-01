"""Backend service wrapper around the pure strategy_lab pipeline."""

from backend.app.strategy_lab.service import StrategyLabService, get_lab_service

__all__ = ["StrategyLabService", "get_lab_service"]
