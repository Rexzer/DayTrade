"""Paper-trading account configuration (pure Python).

Paper trading uses LIVE market data but simulates all execution. It can never
place a real order. ``value_per_unit`` is the account-currency P&L for a 1.0
price move on 1.0 lot; spread/slippage are in price units; commission is per
lot per round turn.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_engine.strategy import SignalLevel


@dataclass
class PaperAccountConfig:
    starting_balance: float = 10_000.0
    risk_per_trade_pct: float = 1.0

    # Risk limits.
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 1
    max_position_lots: float = 100.0

    # Execution realism.
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0
    # Extra adverse price applied to model order latency (price units).
    latency_slippage: float = 0.05

    # Trade management.
    trailing_enabled: bool = False
    trailing_distance: float = 0.0  # price units; 0 disables even if enabled
    partial_tp_enabled: bool = False
    partial_tp_fraction: float = 0.5  # portion closed at the first target
    move_stop_to_breakeven_on_partial: bool = True

    # Only act on signals at or above this level.
    min_signal_level: int = SignalLevel.CONFIRMED_SETUP.value

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.starting_balance <= 0:
            errors.append("starting_balance must be > 0")
        if not (0 < self.risk_per_trade_pct <= 100):
            errors.append("risk_per_trade_pct must be in (0, 100]")
        if not (0 < self.max_daily_loss_pct <= 100):
            errors.append("max_daily_loss_pct must be in (0, 100]")
        if self.max_open_positions < 1:
            errors.append("max_open_positions must be >= 1")
        if self.max_position_lots <= 0:
            errors.append("max_position_lots must be > 0")
        if self.value_per_unit <= 0:
            errors.append("value_per_unit must be > 0")
        if not (0 < self.partial_tp_fraction < 1):
            errors.append("partial_tp_fraction must be in (0, 1)")
        return errors

    def to_dict(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_open_positions": self.max_open_positions,
            "max_position_lots": self.max_position_lots,
            "spread": self.spread,
            "slippage": self.slippage,
            "commission_per_lot": self.commission_per_lot,
            "value_per_unit": self.value_per_unit,
            "latency_slippage": self.latency_slippage,
            "trailing_enabled": self.trailing_enabled,
            "trailing_distance": self.trailing_distance,
            "partial_tp_enabled": self.partial_tp_enabled,
            "partial_tp_fraction": self.partial_tp_fraction,
            "min_signal_level": self.min_signal_level,
        }
