"""Connection and data-freshness status (pure Python).

These enums drive the data-health indicators in the UI and the failsafe
logic in later phases. Phase 1 rule: never present stale or fabricated data
as if it were live. When no provider is connected the status is DISCONNECTED
and price fields are ``None`` (never a made-up number).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class ConnectionStatus(str, Enum):
    """Health of a connection (market data, broker, news, notifications)."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    STALE = "stale"
    ERROR = "error"


class DataStatus(str, Enum):
    """Freshness classification of a data feed."""

    LIVE = "live"
    DELAYED = "delayed"
    STALE = "stale"
    DISCONNECTED = "disconnected"


def classify_data_freshness(
    last_update_epoch: float | None,
    now_epoch: float | None = None,
    *,
    stale_after_seconds: float = 10.0,
    delayed_after_seconds: float = 2.0,
) -> DataStatus:
    """Classify how fresh a feed is based on the age of its last update.

    Args:
        last_update_epoch: Unix time of the last received update, or ``None``
            if nothing has ever been received.
        now_epoch: Current time (defaults to ``time.time()``); injectable for
            deterministic tests.
        stale_after_seconds: Age beyond which data is considered STALE.
        delayed_after_seconds: Age beyond which data is considered DELAYED.

    Returns:
        The appropriate :class:`DataStatus`. Never assumes freshness: with no
        update it returns ``DISCONNECTED``.
    """
    if last_update_epoch is None:
        return DataStatus.DISCONNECTED
    now = time.time() if now_epoch is None else now_epoch
    age = now - last_update_epoch
    if age < 0:
        # Clock skew / out-of-order timestamp — treat conservatively.
        return DataStatus.DELAYED
    if age <= delayed_after_seconds:
        return DataStatus.LIVE
    if age <= stale_after_seconds:
        return DataStatus.DELAYED
    return DataStatus.STALE


@dataclass(frozen=True)
class ConnectionHealth:
    """A named connection's current status, for the Connections UI."""

    name: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    detail: str | None = None
    last_checked_epoch: float | None = field(default=None)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "last_checked_epoch": self.last_checked_epoch,
        }
