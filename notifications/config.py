"""Notification configuration (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field

CHANNELS: tuple[str, ...] = ("browser", "desktop", "sound", "email", "telegram", "discord")
EVENT_TYPES: tuple[str, ...] = (
    "watch",
    "potential",
    "confirmed",
    "executed",
    "stopped",
    "take_profit",
    "risk_shutdown",
    "system_failure",
)


@dataclass
class NotificationConfig:
    # Browser + sound on by default; external channels off until configured.
    channels: dict[str, bool] = field(
        default_factory=lambda: {c: c in ("browser", "sound") for c in CHANNELS}
    )
    # Safety-critical events on by default.
    events: dict[str, bool] = field(
        default_factory=lambda: {
            e: e in ("confirmed", "executed", "stopped", "risk_shutdown", "system_failure")
            for e in EVENT_TYPES
        }
    )

    def enabled_channels(self) -> list[str]:
        return [c for c in CHANNELS if self.channels.get(c)]

    def is_event_enabled(self, event_type: str) -> bool:
        return bool(self.events.get(event_type, False))

    def set_channel(self, channel: str, enabled: bool) -> None:
        if channel in CHANNELS:
            self.channels[channel] = bool(enabled)

    def set_event(self, event_type: str, enabled: bool) -> None:
        if event_type in EVENT_TYPES:
            self.events[event_type] = bool(enabled)

    def update(self, *, channels: dict | None = None, events: dict | None = None) -> None:
        for c, v in (channels or {}).items():
            self.set_channel(c, v)
        for e, v in (events or {}).items():
            self.set_event(e, v)

    def to_dict(self) -> dict:
        return {
            "channels": dict(self.channels),
            "events": dict(self.events),
            "available_channels": list(CHANNELS),
            "available_events": list(EVENT_TYPES),
        }
