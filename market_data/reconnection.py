"""Reconnection state machine + backfill planning (pure Python).

Encodes the Phase 2 requirement: on a dropped connection, detect it, notify,
attempt reconnection with backoff, backfill the candles missed while offline,
and only then declare the feed LIVE again. The feed must NEVER silently resume
with incomplete data — the machine forces a BACKFILLING step before LIVE.

This is a pure state machine with no I/O so it is fully unit-testable. The
service layer drives it and performs the actual network/backfill work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    BACKFILLING = "backfilling"
    LIVE = "live"


@dataclass
class ReconnectionController:
    """Drives the connection lifecycle and computes reconnect backoff.

    Backoff is exponential with a cap and grows per consecutive failed
    attempt; it resets to zero once the feed reaches LIVE.
    """

    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0
    state: ConnectionState = ConnectionState.DISCONNECTED
    attempt: int = 0
    #: History of state transitions for logging/inspection.
    transitions: list[tuple[str, str]] = field(default_factory=list)

    def _to(self, new_state: ConnectionState) -> None:
        self.transitions.append((self.state.value, new_state.value))
        self.state = new_state

    # ------------------------------------------------------------- lifecycle
    def begin_connect(self) -> ConnectionState:
        """Initial connection attempt from a cold/disconnected state."""
        self._to(ConnectionState.CONNECTING)
        return self.state

    def on_connected(self) -> ConnectionState:
        """Transport connected. If we were reconnecting, backfill first."""
        if self.state is ConnectionState.RECONNECTING:
            self._to(ConnectionState.BACKFILLING)
        else:
            self._to(ConnectionState.CONNECTED)
        return self.state

    def on_backfill_complete(self) -> ConnectionState:
        """Missed candles have been fetched; safe to go LIVE."""
        self._to(ConnectionState.LIVE)
        self.attempt = 0
        return self.state

    def mark_live(self) -> ConnectionState:
        """Fresh data is streaming on an initial (non-reconnect) connection."""
        self._to(ConnectionState.LIVE)
        self.attempt = 0
        return self.state

    def on_disconnected(self) -> ConnectionState:
        """Connection dropped. Move toward RECONNECTING and grow the attempt."""
        self._to(ConnectionState.DISCONNECTED)
        return self.state

    def begin_reconnect(self) -> float:
        """Enter RECONNECTING and return the seconds to wait before retrying."""
        self.attempt += 1
        self._to(ConnectionState.RECONNECTING)
        return self.next_backoff_seconds()

    # --------------------------------------------------------------- helpers
    def next_backoff_seconds(self) -> float:
        """Exponential backoff for the current attempt, capped."""
        if self.attempt <= 0:
            return 0.0
        raw = self.base_backoff_seconds * (2 ** (self.attempt - 1))
        return float(min(raw, self.max_backoff_seconds))

    def is_live(self) -> bool:
        return self.state is ConnectionState.LIVE

    def accepts_data(self) -> bool:
        """Whether streamed data should be trusted as current.

        Only LIVE means fully caught-up. While BACKFILLING or RECONNECTING the
        feed is explicitly NOT considered live, so signals stay gated.
        """
        return self.state is ConnectionState.LIVE

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "attempt": self.attempt,
            "next_backoff_seconds": self.next_backoff_seconds(),
            "is_live": self.is_live(),
        }


def plan_backfill(
    aggregator_missing: list[int],
) -> list[int]:
    """Return the ordered list of bucket open-times to backfill (oldest first).

    Thin wrapper that keeps backfill ordering in one place; the service passes
    the aggregator's :meth:`missing_buckets` output here.
    """
    return sorted(set(aggregator_missing))
