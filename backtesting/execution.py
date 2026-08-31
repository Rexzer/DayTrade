"""Execution cost model for the backtester (pure Python).

Applies spread and slippage ADVERSELY to every fill (you buy at the ask plus
slippage, sell at the bid minus slippage) and charges commission per lot as a
round turn. Modelling costs pessimistically avoids optimistic bias in results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0

    # --- fills (adverse) -----------------------------------------------------
    def entry_fill(self, direction: str, intended_price: float) -> float:
        adverse = self.spread / 2.0 + self.slippage
        return intended_price + adverse if direction == "long" else intended_price - adverse

    def exit_fill(self, direction: str, intended_price: float) -> float:
        adverse = self.spread / 2.0 + self.slippage
        return intended_price - adverse if direction == "long" else intended_price + adverse

    def commission(self, lots: float) -> float:
        return self.commission_per_lot * lots

    def gross_pnl(self, direction: str, entry_fill: float, exit_fill: float, lots: float) -> float:
        move = (exit_fill - entry_fill) if direction == "long" else (entry_fill - exit_fill)
        return move * lots * self.value_per_unit

    def net_pnl(self, direction: str, entry_fill: float, exit_fill: float, lots: float) -> float:
        return self.gross_pnl(direction, entry_fill, exit_fill, lots) - self.commission(lots)


def position_lots(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    value_per_unit: float,
    max_lot_size: float,
) -> float:
    """Risk-based lot sizing: risk ``risk_pct`` of equity to the stop distance.

    Returns 0.0 if the stop distance is non-positive (no valid trade).
    """
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0 or equity <= 0 or value_per_unit <= 0:
        return 0.0
    risk_amount = equity * (risk_pct / 100.0)
    lots = risk_amount / (stop_distance * value_per_unit)
    return max(0.0, min(lots, max_lot_size))
