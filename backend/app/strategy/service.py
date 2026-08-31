"""StrategyService — wires the strategy engine to live market data (Phase 3).

Builds a MarketContext from the MarketDataService's candles, runs the signal
engine (with safety gating via the feed's data status), performs multi-timeframe
analysis, and manages alerts and user-created strategies.

Strictly analysis: this service can only classify setups and raise alerts. It
never executes trades.
"""

from __future__ import annotations

from backend.app.core.logging_config import get_logger
from backend.app.market_data import get_market_service
from strategy_engine import (
    AlertManager,
    MultiTimeframeAnalyzer,
    SignalEngine,
    build_builtin_strategies,
)
from strategy_engine.rules import RuleStrategy, validate_rule_dict
from strategy_engine.strategy import MarketContext

logger = get_logger("strategy")


class StrategyService:
    def __init__(self) -> None:
        self._builtins = build_builtin_strategies()
        self._custom: dict[str, RuleStrategy] = {}
        self.engine = SignalEngine(self._all_strategies())
        self.mtf = MultiTimeframeAnalyzer()
        self.alerts = AlertManager()

    def _all_strategies(self) -> list:
        return list(self._builtins) + list(self._custom.values())

    def _rebuild_engine(self) -> None:
        self.engine = SignalEngine(self._all_strategies())

    # ------------------------------------------------------------- context
    def _context(self, limit: int = 300) -> MarketContext:
        market = get_market_service()
        return MarketContext(
            symbol="XAUUSD",
            candles=market.candles_by_timeframe(limit),
            now_epoch=None,
        )

    def _data_status(self) -> str:
        return get_market_service().data_status_str()

    # ------------------------------------------------------------- queries
    def list_strategies(self) -> dict:
        signals = self._safe_signals()
        by_key = {s["strategy_key"]: s for s in signals.get("signals", [])}
        items = []
        for strat in self._all_strategies():
            md = strat.metadata.to_dict()
            sig = by_key.get(strat.key)
            md["current_signal"] = (
                {
                    "level": sig["level"],
                    "level_name": sig["level_name"],
                    "direction": sig.get("direction"),
                    "confidence_score": sig.get("confidence_score"),
                }
                if sig
                else None
            )
            md["historical_performance"] = None  # placeholder (Phase 4 backtesting)
            items.append(md)
        return {
            "connected": True,
            "signals_allowed": signals.get("signals_allowed", False),
            "strategies": items,
        }

    def detail(self, key: str) -> dict | None:
        strat = next((s for s in self._all_strategies() if s.key == key), None)
        if strat is None:
            return None
        md = strat.metadata.to_dict()
        signals = self._safe_signals()
        sig = next((s for s in signals.get("signals", []) if s["strategy_key"] == key), None)
        md["current_signal"] = sig
        md["signals_allowed"] = signals.get("signals_allowed", False)
        return md

    def _safe_signals(self) -> dict:
        try:
            result = self.engine.evaluate_all(
                self._context(), data_status=self._data_status(), primary_timeframe="1h"
            )
            payload = result.to_dict()
            # Feed transitions to the alert manager.
            if payload.get("signals_allowed"):
                self.alerts.process_many(payload.get("signals", []))
            return payload
        except Exception as exc:  # noqa: BLE001
            logger.error("Signal evaluation failed", extra={"context": {"error": str(exc)}})
            return {"signals_allowed": False, "reason": f"error: {exc}", "signals": []}

    def signals(self) -> dict:
        return self._safe_signals()

    def analyze_mtf(self) -> dict:
        try:
            return self.mtf.analyze(self._context())
        except Exception as exc:  # noqa: BLE001
            logger.error("MTF analysis failed", extra={"context": {"error": str(exc)}})
            return {"timeframes": []}

    def recent_alerts(self, limit: int = 20) -> list[dict]:
        return self.alerts.recent(limit)

    # -------------------------------------------------------- custom mgmt
    def custom_definitions(self) -> list[dict]:
        return [s.to_dict() for s in self._custom.values()]

    def add_custom(self, definition: dict) -> list[str]:
        """Validate + register a custom strategy in memory. Returns errors."""
        errors = validate_rule_dict(definition)
        if errors:
            return errors
        strat = RuleStrategy.from_dict(definition)
        self._custom[strat.key] = strat
        self._rebuild_engine()
        return []

    def remove_custom(self, key: str) -> bool:
        existed = key in self._custom
        self._custom.pop(key, None)
        self._rebuild_engine()
        return existed

    def load_custom(self, definitions: list[dict]) -> None:
        """Replace the custom set from persisted definitions (best-effort)."""
        loaded: dict[str, RuleStrategy] = {}
        for d in definitions:
            try:
                strat = RuleStrategy.from_dict(d)
                loaded[strat.key] = strat
            except Exception as exc:  # noqa: BLE001
                logger.error("Skipping bad custom strategy", extra={"context": {"error": str(exc)}})
        self._custom = loaded
        self._rebuild_engine()


_service: StrategyService | None = None


def get_strategy_service() -> StrategyService:
    global _service
    if _service is None:
        _service = StrategyService()
    return _service
