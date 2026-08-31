"""Notification configuration + dispatcher (Phase 8, pure Python).

Users choose which CHANNELS (browser/desktop/sound/email/telegram/discord) and
which EVENT TYPES (watch/potential/confirmed/executed/stopped/take_profit/
risk_shutdown/system_failure) they want. The dispatcher records what it WOULD
send per enabled channel; concrete channel adapters (email/Telegram/Discord)
plug in later and read secrets from the environment — never from source.
"""

from notifications.config import (
    CHANNELS,
    EVENT_TYPES,
    NotificationConfig,
)
from notifications.dispatcher import NotificationDispatcher, NotificationRecord

__all__ = [
    "CHANNELS",
    "EVENT_TYPES",
    "NotificationConfig",
    "NotificationDispatcher",
    "NotificationRecord",
]
