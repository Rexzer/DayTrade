"""Notification dispatcher (pure Python).

Decides whether an event should be delivered and to which channels, and keeps
a record. Actual delivery is delegated to channel adapters (registered
callables); by default there are none, so the dispatcher simply records intent
— useful for the UI (browser/sound handled client-side) and for tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from notifications.config import NotificationConfig


@dataclass
class NotificationRecord:
    epoch: float
    event_type: str
    title: str
    body: str
    channels: list[str] = field(default_factory=list)
    delivered: bool = False

    def to_dict(self) -> dict:
        return {
            "epoch": self.epoch,
            "event_type": self.event_type,
            "title": self.title,
            "body": self.body,
            "channels": self.channels,
            "delivered": self.delivered,
        }


class NotificationDispatcher:
    def __init__(self, config: NotificationConfig | None = None, max_history: int = 200) -> None:
        self.config = config or NotificationConfig()
        self._history: list[NotificationRecord] = []
        self._adapters: dict[str, Callable[[NotificationRecord], None]] = {}
        self._max = max_history

    def register_adapter(self, channel: str, adapter: Callable[[NotificationRecord], None]) -> None:
        """Register a concrete delivery adapter for a channel (e.g. email)."""
        self._adapters[channel] = adapter

    def notify(
        self, event_type: str, title: str, body: str, *, now_epoch: float | None = None
    ) -> NotificationRecord | None:
        """Record + (best-effort) deliver a notification if the event is enabled.

        Returns the record, or ``None`` if the event type is disabled.
        """
        if not self.config.is_event_enabled(event_type):
            return None
        channels = self.config.enabled_channels()
        rec = NotificationRecord(
            epoch=time.time() if now_epoch is None else now_epoch,
            event_type=event_type,
            title=title,
            body=body,
            channels=channels,
        )
        # Deliver through any registered server-side adapters (email/telegram/
        # discord). browser/sound are handled by the client from this record.
        delivered_any = False
        for ch in channels:
            adapter = self._adapters.get(ch)
            if adapter is not None:
                try:
                    adapter(rec)
                    delivered_any = True
                except Exception:  # noqa: BLE001 - a bad adapter must not break others
                    pass
        rec.delivered = delivered_any or bool(channels)
        self._history.append(rec)
        if len(self._history) > self._max:
            self._history = self._history[-self._max :]
        return rec

    def recent(self, limit: int = 50) -> list[dict]:
        return [r.to_dict() for r in self._history[-limit:][::-1]]
