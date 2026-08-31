"""Feed health monitoring + signal gating (pure Python).

Wraps the freshness classifier from ``backend.app.core.status`` and adds the
Phase 2 failsafe rule: when a feed is STALE or DISCONNECTED, downstream signal
generation MUST stop. This module is the single place that decides whether the
platform may act on the data.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.status import DataStatus, classify_data_freshness


@dataclass
class FeedHealth:
    """Serializable health snapshot for the UI / status endpoints."""

    status: DataStatus
    last_update_epoch: float | None
    age_seconds: float | None
    signals_allowed: bool
    source: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "last_update_epoch": self.last_update_epoch,
            "age_seconds": self.age_seconds,
            "signals_allowed": self.signals_allowed,
            "source": self.source,
        }


class FeedHealthMonitor:
    """Tracks the freshness of a single data feed.

    Call :meth:`mark_update` whenever a tick/candle arrives. Query
    :meth:`health` / :meth:`signals_allowed` to gate downstream work.
    """

    def __init__(
        self,
        *,
        source: str | None = None,
        delayed_after_seconds: float = 2.0,
        stale_after_seconds: float = 10.0,
    ) -> None:
        self.source = source
        self.delayed_after_seconds = delayed_after_seconds
        self.stale_after_seconds = stale_after_seconds
        self._last_update_epoch: float | None = None

    def mark_update(self, epoch: float) -> None:
        """Record that fresh data arrived at ``epoch`` (UTC seconds)."""
        # Keep the most recent timestamp only; out-of-order arrivals do not
        # make the feed look fresher than its newest data.
        if self._last_update_epoch is None or epoch > self._last_update_epoch:
            self._last_update_epoch = epoch

    def reset(self) -> None:
        """Forget the last update (e.g. after a disconnect)."""
        self._last_update_epoch = None

    def status(self, now_epoch: float | None = None) -> DataStatus:
        return classify_data_freshness(
            self._last_update_epoch,
            now_epoch,
            stale_after_seconds=self.stale_after_seconds,
            delayed_after_seconds=self.delayed_after_seconds,
        )

    def signals_allowed(self, now_epoch: float | None = None) -> bool:
        """Return True only when data is LIVE or DELAYED (never STALE/DISCONNECTED)."""
        return self.status(now_epoch) in (DataStatus.LIVE, DataStatus.DELAYED)

    def age_seconds(self, now_epoch: float | None = None) -> float | None:
        if self._last_update_epoch is None:
            return None
        import time

        now = time.time() if now_epoch is None else now_epoch
        return max(0.0, now - self._last_update_epoch)

    def health(self, now_epoch: float | None = None) -> FeedHealth:
        return FeedHealth(
            status=self.status(now_epoch),
            last_update_epoch=self._last_update_epoch,
            age_seconds=self.age_seconds(now_epoch),
            signals_allowed=self.signals_allowed(now_epoch),
            source=self.source,
        )
