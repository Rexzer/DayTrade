"""Live-execution authorization (pure Python, safety-critical).

Live order execution is authorized ONLY when ALL of these hold:
    1. The operator enabled it at the backend/config layer (LIVE_EXECUTION_ENABLED).
    2. The user checked every required confirmation.
    3. The user explicitly ARMED live trading ("ENABLE LIVE TRADING").
    4. The kill switch is not engaged.

The object is in-memory only, so an application restart resets it to DISABLED
(post-restart safety). The frontend alone can NEVER authorize execution: the
config flag is a backend precondition the UI cannot set.
"""

from __future__ import annotations

# The six confirmations the user must tick before live trading can be armed.
REQUIRED_CONFIRMATIONS: tuple[str, ...] = (
    "understand_losses",
    "configured_risk_limits",
    "verified_mt5_account",
    "verified_xauusd_symbol",
    "verified_position_sizing",
    "understand_automation_can_fail",
)

CONFIRMATION_LABELS: dict[str, str] = {
    "understand_losses": "I understand trading can result in losses.",
    "configured_risk_limits": "I configured my risk limits.",
    "verified_mt5_account": "I verified my MetaTrader 5 account.",
    "verified_xauusd_symbol": "I verified the XAUUSD symbol.",
    "verified_position_sizing": "I verified position sizing.",
    "understand_automation_can_fail": "I understand automated trading can fail.",
}


class AuthorizationError(RuntimeError):
    """Raised when arming live trading is attempted without meeting requirements."""


class LiveAuthorization:
    def __init__(self, config_enabled: bool = False) -> None:
        self._config_enabled = bool(config_enabled)
        self._confirmations: dict[str, bool] = dict.fromkeys(REQUIRED_CONFIRMATIONS, False)
        self._armed = False
        self._killed = False

    # --- config precondition (backend only) ---------------------------------
    def set_config_enabled(self, value: bool) -> None:
        self._config_enabled = bool(value)
        if not self._config_enabled:
            self._armed = False

    @property
    def config_enabled(self) -> bool:
        return self._config_enabled

    # --- confirmations -------------------------------------------------------
    def confirm(self, key: str, value: bool = True) -> None:
        if key not in self._confirmations:
            raise AuthorizationError(f"Unknown confirmation '{key}'.")
        self._confirmations[key] = bool(value)
        if not value:
            self._armed = False  # un-ticking a box disarms

    def set_confirmations(self, confirmations: dict[str, bool]) -> None:
        for k, v in (confirmations or {}).items():
            if k in self._confirmations:
                self._confirmations[k] = bool(v)

    def all_confirmed(self) -> bool:
        return all(self._confirmations.values())

    def missing_confirmations(self) -> list[str]:
        return [k for k, v in self._confirmations.items() if not v]

    # --- arming / disabling --------------------------------------------------
    def arm(self) -> None:
        """Explicitly enable live trading. Raises if requirements unmet."""
        if not self._config_enabled:
            raise AuthorizationError(
                "LIVE_EXECUTION_ENABLED is false. A backend operator must enable "
                "it before live trading can be armed."
            )
        if not self.all_confirmed():
            raise AuthorizationError(
                f"Missing confirmations: {', '.join(self.missing_confirmations())}."
            )
        if self._killed:
            raise AuthorizationError("Kill switch is engaged. Clear it before arming.")
        self._armed = True

    def disable(self) -> None:
        self._armed = False

    # --- kill switch ---------------------------------------------------------
    def kill(self) -> None:
        self._killed = True
        self._armed = False

    def clear_kill(self) -> None:
        self._killed = False

    @property
    def killed(self) -> bool:
        return self._killed

    @property
    def armed(self) -> bool:
        return self._armed

    # --- the single authorization gate --------------------------------------
    def is_authorized(self) -> bool:
        return self._config_enabled and self.all_confirmed() and self._armed and not self._killed

    def status(self) -> dict:
        return {
            "config_enabled": self._config_enabled,
            "confirmations": dict(self._confirmations),
            "confirmation_labels": CONFIRMATION_LABELS,
            "all_confirmed": self.all_confirmed(),
            "missing_confirmations": self.missing_confirmations(),
            "armed": self._armed,
            "killed": self._killed,
            "authorized": self.is_authorized(),
        }
