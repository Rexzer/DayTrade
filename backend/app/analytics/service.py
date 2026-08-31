"""AnalyticsService — performance, journal intelligence, comparison, history.

Sources closed trades from the paper-trading engine (the platform's realized
trade record) and current signals from the strategy engine. All outputs are
historical/simulated measurements — never guarantees of future performance.
"""

from __future__ import annotations

from analytics import (
    JournalAnalyzer,
    SignalHistory,
    build_strategy_comparison,
    standard_breakdowns,
)
from backend.app.core.logging_config import get_logger

logger = get_logger("analytics")


class AnalyticsService:
    def __init__(self) -> None:
        self.signal_history = SignalHistory()

    def _trades(self) -> list[dict]:
        try:
            from backend.app.paper_trading import get_paper_service

            return get_paper_service().trades(limit=1000).get("trades", [])
        except Exception as exc:  # noqa: BLE001
            logger.debug("analytics: trades unavailable", extra={"context": {"error": str(exc)}})
            return []

    def performance(self) -> dict:
        return standard_breakdowns(self._trades())

    def journal(self) -> dict:
        settings = {}
        try:
            from backend.app.live import get_live_service

            rs = get_live_service().risk.settings
            settings = {
                "max_trades_per_day": rs.max_trades_per_day,
                "consecutive_loss_threshold": rs.max_consecutive_losses,
            }
        except Exception:  # noqa: BLE001
            pass
        analyzer = JournalAnalyzer(
            max_trades_per_day=settings.get("max_trades_per_day", 5),
            consecutive_loss_threshold=settings.get("consecutive_loss_threshold", 3),
        )
        return {"observations": [o.to_dict() for o in analyzer.analyze(self._trades())]}

    def comparison(self) -> dict:
        strategies: list[dict] = []
        paper_by_key: dict[str, dict] = {}
        try:
            from backend.app.strategy import get_strategy_service

            strategies = [
                {"key": s["key"], "name": s["name"]}
                for s in get_strategy_service().list_strategies().get("strategies", [])
            ]
        except Exception:  # noqa: BLE001
            pass
        try:
            from backend.app.paper_trading import get_paper_service

            for row in get_paper_service().performance().get("by_strategy", []):
                paper_by_key[row.get("strategy_key")] = row
        except Exception:  # noqa: BLE001
            pass
        return {
            "rows": build_strategy_comparison(strategies, paper_by_key=paper_by_key),
            "note": "Backtest out-of-sample and live columns populate as those runs are recorded.",
        }

    def refresh_signal_history(self) -> dict:
        try:
            from backend.app.strategy import get_strategy_service

            signals = get_strategy_service().signals().get("signals", [])
            self.signal_history.record_snapshot(signals)
        except Exception as exc:  # noqa: BLE001
            logger.debug("analytics: signal refresh failed", extra={"context": {"error": str(exc)}})
        return {"events": self.signal_history.recent(limit=100)}

    def signal_history_recent(self, limit: int = 100, transition: str | None = None) -> dict:
        # Refresh opportunistically so the history reflects the latest snapshot.
        self.refresh_signal_history()
        return {"events": self.signal_history.recent(limit=limit, transition=transition)}


_service: AnalyticsService | None = None


def get_analytics_service() -> AnalyticsService:
    global _service
    if _service is None:
        _service = AnalyticsService()
    return _service
