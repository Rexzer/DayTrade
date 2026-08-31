"""Strategy registry — the plug-in point for built-in and user strategies.

Phase 1 ships an empty registry so the platform truthfully reports that no
strategies are connected yet. Phase 2 registers the built-in strategy
families (Trend Following, EMA Pullback, Breakout+Retest, etc.).
"""

from __future__ import annotations

from strategy_engine.strategy import Strategy


class StrategyRegistry:
    """A simple keyed registry of strategy instances."""

    def __init__(self) -> None:
        self._strategies: dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> None:
        key = strategy.key
        if key in self._strategies:
            raise ValueError(f"Strategy '{key}' is already registered.")
        self._strategies[key] = strategy

    def unregister(self, key: str) -> None:
        self._strategies.pop(key, None)

    def get(self, key: str) -> Strategy | None:
        return self._strategies.get(key)

    def all(self) -> list[Strategy]:
        return list(self._strategies.values())

    def keys(self) -> list[str]:
        return list(self._strategies.keys())

    def is_empty(self) -> bool:
        return not self._strategies


# Module-level default registry (empty in Phase 1).
registry = StrategyRegistry()
