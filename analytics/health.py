"""System-health aggregation (pure Python).

Combines per-component statuses into an overall status. Components:
market data, MT5, database, WebSocket, strategy engine, risk engine, execution
engine, notifications. Statuses: HEALTHY / WARNING / FAILURE.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    FAILURE = "failure"


_EMOJI = {HealthStatus.HEALTHY: "🟢", HealthStatus.WARNING: "🟡", HealthStatus.FAILURE: "🔴"}
_SEVERITY = {HealthStatus.HEALTHY: 0, HealthStatus.WARNING: 1, HealthStatus.FAILURE: 2}


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "emoji": _EMOJI[self.status],
            "detail": self.detail,
        }


class SystemHealth:
    def __init__(self) -> None:
        self._components: list[ComponentHealth] = []

    def add(self, name: str, status: HealthStatus, detail: str = "") -> None:
        self._components.append(ComponentHealth(name, status, detail))

    def overall(self) -> HealthStatus:
        if not self._components:
            return HealthStatus.WARNING
        worst = max(self._components, key=lambda c: _SEVERITY[c.status])
        return worst.status

    def to_dict(self) -> dict:
        overall = self.overall()
        return {
            "overall": overall.value,
            "overall_emoji": _EMOJI[overall],
            "components": [c.to_dict() for c in self._components],
        }
