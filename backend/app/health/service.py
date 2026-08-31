"""HealthService — aggregates per-component health (Phase 8).

Reports HEALTHY / WARNING / FAILURE for each subsystem. Read-only and
defensive: a component that cannot be inspected is reported as WARNING rather
than crashing the endpoint.
"""

from __future__ import annotations

from analytics import HealthStatus, SystemHealth
from backend.app.core.logging_config import get_logger

logger = get_logger("health")


class HealthService:
    def snapshot(self) -> dict:
        h = SystemHealth()
        self._market(h)
        self._mt5(h)
        self._database(h)
        self._websocket(h)
        self._strategy(h)
        self._risk(h)
        self._execution(h)
        self._notifications(h)
        return h.to_dict()

    def _market(self, h: SystemHealth) -> None:
        try:
            from backend.app.market_data import get_market_service

            st = get_market_service().status()
            data_status = (st.get("health") or {}).get("status", "disconnected")
            if data_status in ("live", "delayed"):
                h.add("Market Data", HealthStatus.HEALTHY, f"data {data_status}")
            elif st.get("provider_kind") == "none":
                h.add("Market Data", HealthStatus.WARNING, "no provider configured")
            else:
                h.add("Market Data", HealthStatus.WARNING, f"data {data_status}")
        except Exception as exc:  # noqa: BLE001
            h.add("Market Data", HealthStatus.FAILURE, str(exc))

    def _mt5(self, h: SystemHealth) -> None:
        try:
            from backend.app.mt5 import get_mt5_service

            connected = get_mt5_service().provider.is_connected()
            h.add(
                "MetaTrader 5",
                HealthStatus.HEALTHY if connected else HealthStatus.WARNING,
                "connected" if connected else "not connected (optional)",
            )
        except Exception as exc:  # noqa: BLE001
            h.add("MetaTrader 5", HealthStatus.WARNING, str(exc))

    def _database(self, h: SystemHealth) -> None:
        try:
            from sqlalchemy import text

            from backend.app.db.session import engine

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            h.add("Database", HealthStatus.HEALTHY, "reachable")
        except Exception:  # noqa: BLE001
            h.add("Database", HealthStatus.WARNING, "not reachable (optional for analysis)")

    def _websocket(self, h: SystemHealth) -> None:
        try:
            from backend.app.websocket.manager import manager

            h.add("WebSocket", HealthStatus.HEALTHY, f"{manager.count} client(s)")
        except Exception as exc:  # noqa: BLE001
            h.add("WebSocket", HealthStatus.WARNING, str(exc))

    def _strategy(self, h: SystemHealth) -> None:
        try:
            from backend.app.strategy import get_strategy_service

            n = len(get_strategy_service().engine.strategies)
            h.add("Strategy Engine", HealthStatus.HEALTHY, f"{n} strategies loaded")
        except Exception as exc:  # noqa: BLE001
            h.add("Strategy Engine", HealthStatus.FAILURE, str(exc))

    def _risk(self, h: SystemHealth) -> None:
        try:
            from backend.app.live import get_live_service

            state = get_live_service().risk.state
            if state.drawdown_halt or state.daily_loss_halt or state.weekly_loss_halt:
                h.add("Risk Engine", HealthStatus.WARNING, "a risk halt is active (manual reset)")
            else:
                h.add("Risk Engine", HealthStatus.HEALTHY, "no halts active")
        except Exception as exc:  # noqa: BLE001
            h.add("Risk Engine", HealthStatus.FAILURE, str(exc))

    def _execution(self, h: SystemHealth) -> None:
        try:
            from backend.app.live import get_live_service

            authorized = get_live_service().authorization.is_authorized()
            # Disabled/safe is HEALTHY; armed live is WARNING (attention state).
            h.add(
                "Execution Engine",
                HealthStatus.WARNING if authorized else HealthStatus.HEALTHY,
                "LIVE ARMED" if authorized else "execution disabled (safe)",
            )
        except Exception as exc:  # noqa: BLE001
            h.add("Execution Engine", HealthStatus.WARNING, str(exc))

    def _notifications(self, h: SystemHealth) -> None:
        try:
            from backend.app.notifications import get_notification_service

            channels = get_notification_service().config.enabled_channels()
            h.add(
                "Notifications",
                HealthStatus.HEALTHY if channels else HealthStatus.WARNING,
                f"{len(channels)} channel(s) enabled",
            )
        except Exception as exc:  # noqa: BLE001
            h.add("Notifications", HealthStatus.WARNING, str(exc))


_service: HealthService | None = None


def get_health_service() -> HealthService:
    global _service
    if _service is None:
        _service = HealthService()
    return _service
