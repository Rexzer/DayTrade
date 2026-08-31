"""AssistantService — gathers live system data and answers questions (Phase 8).

Builds an AssistantContext from the running services and delegates to the pure,
data-grounded TradingAssistant. If a service is unavailable, its slice is left
empty so the assistant honestly reports insufficient data instead of guessing.
"""

from __future__ import annotations

import time

from assistant import AssistantContext, TradingAssistant
from backend.app.core.logging_config import get_logger

logger = get_logger("assistant")


class AssistantService:
    def __init__(self) -> None:
        self.assistant = TradingAssistant()

    def _context(self) -> AssistantContext:
        ctx = AssistantContext(now_epoch=time.time())
        # Market + strategy signals + regime + MTF.
        try:
            from backend.app.market_data import get_market_service

            ms = get_market_service()
            ctx.market = ms.snapshot()
        except Exception as exc:  # noqa: BLE001
            logger.debug("assistant: market unavailable", extra={"context": {"error": str(exc)}})
        try:
            from backend.app.strategy import get_strategy_service

            ss = get_strategy_service()
            sig = ss.signals()
            ctx.signals = sig.get("signals")
            ctx.signals_allowed = sig.get("signals_allowed", False)
            ctx.signals_reason = sig.get("reason")
            ctx.regime = sig.get("regime")
            ctx.mtf = ss.analyze_mtf().get("timeframes")
            ctx.alerts = ss.recent_alerts()
        except Exception as exc:  # noqa: BLE001
            logger.debug("assistant: strategy unavailable", extra={"context": {"error": str(exc)}})
        try:
            from backend.app.paper_trading import get_paper_service

            ps = get_paper_service()
            ctx.trades = ps.trades().get("trades")
            ctx.performance = ps.performance()
        except Exception as exc:  # noqa: BLE001
            logger.debug("assistant: paper unavailable", extra={"context": {"error": str(exc)}})
        try:
            from backend.app.live import get_live_service

            ls = get_live_service()
            st = ls.status()
            ctx.risk_state = st.get("risk_state")
            ctx.risk_settings = st.get("risk_settings")
            ctx.execution_log = ls.execution_log().get("log")
        except Exception as exc:  # noqa: BLE001
            logger.debug("assistant: live unavailable", extra={"context": {"error": str(exc)}})
        try:
            from backend.app.health import get_health_service

            ctx.health = get_health_service().snapshot()
        except Exception as exc:  # noqa: BLE001
            logger.debug("assistant: health unavailable", extra={"context": {"error": str(exc)}})
        ctx.news = {"connected": False}
        return ctx

    def ask(self, question: str) -> dict:
        answer = self.assistant.ask(question, self._context())
        return answer.to_dict()

    def examples(self) -> dict:
        return {"examples": list(self.assistant.EXAMPLES)}


_service: AssistantService | None = None


def get_assistant_service() -> AssistantService:
    global _service
    if _service is None:
        _service = AssistantService()
    return _service
