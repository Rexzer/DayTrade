"""NotificationService — config + dispatch (Phase 8).

Holds the user's notification preferences and a dispatcher. Server-side channel
adapters (email/Telegram/Discord) can be registered here; their secrets come
from the environment and are never returned by the API.
"""

from __future__ import annotations

from notifications import NotificationConfig, NotificationDispatcher


class NotificationService:
    def __init__(self) -> None:
        self.config = NotificationConfig()
        self.dispatcher = NotificationDispatcher(self.config)

    def get_config(self) -> dict:
        return self.config.to_dict()

    def update_config(self, *, channels: dict | None = None, events: dict | None = None) -> dict:
        self.config.update(channels=channels, events=events)
        return self.config.to_dict()

    def recent(self, limit: int = 50) -> dict:
        return {"notifications": self.dispatcher.recent(limit)}

    def test(self) -> dict:
        rec = self.dispatcher.notify(
            "system_failure",  # always-on safety event, good for a test
            "Test notification",
            "This is a test notification from the XAUUSD platform.",
        )
        return {"sent": rec.to_dict() if rec else None}

    def notify(self, event_type: str, title: str, body: str):
        return self.dispatcher.notify(event_type, title, body)


_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
