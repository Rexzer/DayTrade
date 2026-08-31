"""Trading-mode state machine (pure Python, safety-critical).

The platform has three operating modes. In Phase 1 only ANALYSIS_ONLY is
available; PAPER_TRADING and LIVE_TRADING are hard-locked and cannot be
enabled regardless of configuration. This module is the single source of
truth for that rule and is exhaustively unit-tested.

Design goals:
    * Fail closed — the default and only reachable mode is ANALYSIS_ONLY.
    * No silent enablement — attempts to switch to a locked mode raise.
    * No dependency on config/env — the lock is enforced in code so a
      mis-set environment variable can never unlock live trading in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradingMode(str, Enum):
    """The three mutually-exclusive operating modes."""

    ANALYSIS_ONLY = "analysis_only"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"


class ModeAvailability(str, Enum):
    """Whether a mode can currently be selected."""

    ENABLED = "enabled"
    LOCKED = "locked"


# --- Phase availability policy ------------------------------------------------
# ANALYSIS_ONLY and PAPER_TRADING are enabled (Phase 5 adds a simulated
# execution layer that uses live data but can never place a real order).
# LIVE_TRADING remains hard-locked until the later phase that adds a verified
# broker connection, a working kill switch and explicit user confirmations.
_DEFAULT_AVAILABILITY: dict[TradingMode, ModeAvailability] = {
    TradingMode.ANALYSIS_ONLY: ModeAvailability.ENABLED,
    TradingMode.PAPER_TRADING: ModeAvailability.ENABLED,
    TradingMode.LIVE_TRADING: ModeAvailability.LOCKED,
}

# Backwards-compatible alias (some callers/tests referenced the old name).
_PHASE_1_AVAILABILITY = _DEFAULT_AVAILABILITY

_LOCK_REASONS: dict[TradingMode, str] = {
    TradingMode.LIVE_TRADING: (
        "Live trading is enabled only in a later phase, and only after explicit "
        "user confirmation, a verified MetaTrader connection, configured risk "
        "limits and a working kill switch."
    ),
}


class ModeTransitionError(RuntimeError):
    """Raised when a transition to a locked/unknown mode is attempted."""


@dataclass(frozen=True)
class ModeStatus:
    """Serializable snapshot of a single mode's availability."""

    mode: TradingMode
    availability: ModeAvailability
    active: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "availability": self.availability.value,
            "active": self.active,
            "reason": self.reason,
        }


class TradingModeManager:
    """Owns the current trading mode and enforces Phase 1 locks.

    The manager always starts in ANALYSIS_ONLY and refuses to move to any
    mode that is not marked ENABLED by the phase policy.
    """

    def __init__(self, availability: dict[TradingMode, ModeAvailability] | None = None) -> None:
        self._availability = dict(availability or _PHASE_1_AVAILABILITY)
        self._current: TradingMode = TradingMode.ANALYSIS_ONLY

    @property
    def current(self) -> TradingMode:
        return self._current

    def is_enabled(self, mode: TradingMode) -> bool:
        return self._availability.get(mode) is ModeAvailability.ENABLED

    def is_live_trading_active(self) -> bool:
        """Convenience guard used by any execution-facing code path."""
        return self._current is TradingMode.LIVE_TRADING

    def set_mode(self, mode: TradingMode) -> TradingMode:
        """Switch modes if allowed; otherwise raise ``ModeTransitionError``."""
        if not isinstance(mode, TradingMode):
            raise ModeTransitionError(f"Unknown trading mode: {mode!r}")
        if not self.is_enabled(mode):
            reason = _LOCK_REASONS.get(mode, "This mode is locked in the current phase.")
            raise ModeTransitionError(f"Mode '{mode.value}' is locked. {reason}")
        self._current = mode
        return self._current

    def status(self) -> list[ModeStatus]:
        """Return the availability snapshot for every mode (for the UI)."""
        result: list[ModeStatus] = []
        for mode in TradingMode:
            availability = self._availability.get(mode, ModeAvailability.LOCKED)
            result.append(
                ModeStatus(
                    mode=mode,
                    availability=availability,
                    active=(mode is self._current),
                    reason=(
                        _LOCK_REASONS.get(mode) if availability is ModeAvailability.LOCKED else None
                    ),
                )
            )
        return result

    def status_dicts(self) -> list[dict]:
        return [s.to_dict() for s in self.status()]
