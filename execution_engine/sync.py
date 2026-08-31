"""Position / order synchronization (pure Python).

Diffs successive broker snapshots (keyed by ticket) into opened / closed /
modified sets so the platform can react to changes made in MT5 or elsewhere.
Stateful but I/O-free; the service feeds it fresh snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from execution_engine.provider import BrokerPosition


@dataclass
class SyncDiff:
    opened: list[BrokerPosition] = field(default_factory=list)
    closed: list[BrokerPosition] = field(default_factory=list)
    modified: list[BrokerPosition] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.opened or self.closed or self.modified)

    def to_dict(self) -> dict:
        return {
            "opened": [p.to_dict() for p in self.opened],
            "closed": [p.to_dict() for p in self.closed],
            "modified": [p.to_dict() for p in self.modified],
            "has_changes": self.has_changes,
        }


def _changed(a: BrokerPosition, b: BrokerPosition) -> bool:
    return (
        a.stop_loss != b.stop_loss
        or a.take_profit != b.take_profit
        or abs((a.volume or 0) - (b.volume or 0)) > 1e-9
    )


class PositionSynchronizer:
    def __init__(self) -> None:
        self._last: dict[int, BrokerPosition] = {}

    def reset(self) -> None:
        self._last = {}

    def diff(self, current: list[BrokerPosition]) -> SyncDiff:
        current_map = {p.ticket: p for p in current}
        diff = SyncDiff()
        for ticket, pos in current_map.items():
            prev = self._last.get(ticket)
            if prev is None:
                diff.opened.append(pos)
            elif _changed(prev, pos):
                diff.modified.append(pos)
        for ticket, prev in self._last.items():
            if ticket not in current_map:
                diff.closed.append(prev)
        self._last = current_map
        return diff
