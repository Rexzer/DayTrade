"""Paper-trading journal (pure Python).

Records every signal, executed trade, rejection and control event with a
timestamp so the trader can review WHAT happened and WHY.
"""

from __future__ import annotations

from paper_trading.models import JournalEntry


class PaperJournal:
    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[JournalEntry] = []
        self._max = max_entries

    def add(self, entry: JournalEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]

    def recent(self, limit: int = 50, kind: str | None = None) -> list[dict]:
        items = self._entries
        if kind is not None:
            items = [e for e in items if e.kind == kind]
        return [e.to_dict() for e in items[-limit:][::-1]]

    def clear(self) -> None:
        self._entries.clear()

    def all(self) -> list[JournalEntry]:
        return list(self._entries)
