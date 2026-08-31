"""Risk configuration (pure Python).

The risk engine is INDEPENDENT and authoritative: these limits are enforced
against every prospective live order and the strategy engine cannot bypass
them. Defaults are conservative; there is no configuration that permits
unlimited risk.
"""

from __future__ import annotations

from dataclasses import dataclass

# Common risk-per-trade presets exposed in the UI (custom values allowed).
RISK_PER_TRADE_PRESETS: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0)


@dataclass(frozen=True)
class RiskSettings:
    """User-configurable hard risk limits."""

    risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0
    max_drawdown_pct: float = 10.0
    max_open_positions: int = 1
    max_xauusd_positions: int = 1
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 4
    max_lot_size: float = 1.0
    max_spread_points: float = 50.0
    # News blackout window (minutes before/after a high-impact event).
    news_blackout_before_min: float = 10.0
    news_blackout_after_min: float = 15.0

    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors (empty if valid)."""
        errors: list[str] = []
        if not (0 < self.risk_per_trade_pct <= 100):
            errors.append("risk_per_trade_pct must be in (0, 100].")
        if not (0 < self.max_daily_loss_pct <= 100):
            errors.append("max_daily_loss_pct must be in (0, 100].")
        if self.max_weekly_loss_pct < self.max_daily_loss_pct:
            errors.append("max_weekly_loss_pct must be >= max_daily_loss_pct.")
        if not (0 < self.max_drawdown_pct <= 100):
            errors.append("max_drawdown_pct must be in (0, 100].")
        if self.max_open_positions < 1:
            errors.append("max_open_positions must be >= 1.")
        if self.max_xauusd_positions < 1:
            errors.append("max_xauusd_positions must be >= 1.")
        if self.max_trades_per_day < 1:
            errors.append("max_trades_per_day must be >= 1.")
        if self.max_consecutive_losses < 1:
            errors.append("max_consecutive_losses must be >= 1.")
        if self.max_lot_size <= 0:
            errors.append("max_lot_size must be > 0.")
        if self.max_spread_points <= 0:
            errors.append("max_spread_points must be > 0.")
        if self.news_blackout_before_min < 0 or self.news_blackout_after_min < 0:
            errors.append("news blackout windows must be >= 0.")
        return errors

    @property
    def is_valid(self) -> bool:
        return not self.validate()

    def to_dict(self) -> dict:
        return {
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_open_positions": self.max_open_positions,
            "max_xauusd_positions": self.max_xauusd_positions,
            "max_trades_per_day": self.max_trades_per_day,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_lot_size": self.max_lot_size,
            "max_spread_points": self.max_spread_points,
            "news_blackout_before_min": self.news_blackout_before_min,
            "news_blackout_after_min": self.news_blackout_after_min,
        }
