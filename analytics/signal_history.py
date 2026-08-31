"""Signal-transition history (pure Python).

Ingests successive signal snapshots and records every level transition per
strategy with the reason, so the user can review why each signal was
generated / confirmed / rejected / invalidated / executed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

_LEVEL_NAME = {0: "NO_SETUP", 1: "WATCH", 2: "POTENTIAL_SETUP", 3: "CONFIRMED_SETUP", 4: "EXECUTED"}


@dataclass
class SignalEvent:
    epoch: float
    strategy_key: str
    strategy_name: str
    from_level: int
    to_level: int
    transition: str  # generated | upgraded | confirmed | executed | invalidated | downgraded
    reason: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "epoch": self.epoch,
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "from_level": self.from_level,
            "to_level": self.to_level,
            "from_level_name": _LEVEL_NAME.get(self.from_level, "?"),
            "to_level_name": _LEVEL_NAME.get(self.to_level, "?"),
            "transition": self.transition,
            "reason": self.reason,
            "payload": self.payload,
        }


def _transition_label(prev: int, cur: int) -> str:
    if prev == 0 and cur >= 1:
        return "generated"
    if cur == 4:
        return "executed"
    if cur == 3 and prev < 3:
        return "confirmed"
    if cur > prev:
        return "upgraded"
    if prev >= 2 and cur < prev:
        return "invalidated"
    return "downgraded"


def _reason_for(signal: dict, transition: str) -> str:
    if transition in ("generated", "upgraded", "confirmed"):
        met = signal.get("confirmations") or []
        missing = signal.get("missing_confirmations") or []
        return f"{len(met)}/{len(met) + len(missing)} conditions satisfied."
    if transition in ("invalidated", "downgraded"):
        return signal.get("invalidation") or "conditions no longer satisfied."
    if transition == "executed":
        return "order executed."
    return ""


class SignalHistory:
    def __init__(self, max_events: int = 1000) -> None:
        self._events: list[SignalEvent] = []
        self._last_level: dict[str, int] = {}
        self._max = max_events

    def record_snapshot(
        self, signals: list[dict], *, now_epoch: float | None = None
    ) -> list[SignalEvent]:
        now = time.time() if now_epoch is None else now_epoch
        new_events: list[SignalEvent] = []
        for s in signals or []:
            key = s.get("strategy_key")
            if key is None:
                continue
            cur = int(s.get("level", 0))
            prev = self._last_level.get(key, 0)
            self._last_level[key] = cur
            if cur == prev:
                continue
            transition = _transition_label(prev, cur)
            event = SignalEvent(
                epoch=now,
                strategy_key=key,
                strategy_name=s.get("strategy_name", key),
                from_level=prev,
                to_level=cur,
                transition=transition,
                reason=_reason_for(s, transition),
                payload={"direction": s.get("direction"), "score": s.get("confidence_score")},
            )
            self._events.append(event)
            new_events.append(event)
        if len(self._events) > self._max:
            self._events = self._events[-self._max :]
        return new_events

    def recent(self, limit: int = 100, transition: str | None = None) -> list[dict]:
        items = self._events
        if transition:
            items = [e for e in items if e.transition == transition]
        return [e.to_dict() for e in items[-limit:][::-1]]
