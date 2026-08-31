"""Risk configuration (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSettings:
    """User-configurable risk limits.

    These are validated but not enforced against real orders in Phase 1.
    Sensible, conservative defaults are used; there are no defaults that would
    permit unlimited risk.
    """

    risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0
    max_open_positions: int = 1
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 4
    max_lot_size: float = 1.0
    max_spread_points: float = 50.0

    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors (empty if valid)."""
        errors: list[str] = []
        if not (0 < self.risk_per_trade_pct <= 100):
            errors.append("risk_per_trade_pct must be in (0, 100].")
        if not (0 < self.max_daily_loss_pct <= 100):
            errors.append("max_daily_loss_pct must be in (0, 100].")
        if self.max_weekly_loss_pct < self.max_daily_loss_pct:
            errors.append("max_weekly_loss_pct must be >= max_daily_loss_pct.")
        if self.max_open_positions < 1:
            errors.append("max_open_positions must be >= 1.")
        if self.max_trades_per_day < 1:
            errors.append("max_trades_per_day must be >= 1.")
        if self.max_lot_size <= 0:
            errors.append("max_lot_size must be > 0.")
        if self.max_spread_points <= 0:
            errors.append("max_spread_points must be > 0.")
        return errors

    @property
    def is_valid(self) -> bool:
        return not self.validate()
