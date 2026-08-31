"""Simulated execution cost model for paper trading (pure Python).

Models realistic (pessimistic) fills: every fill pays half the spread plus
slippage plus a latency allowance, always ADVERSE to the trader. Commission is
per lot per round turn. This mirrors the backtester so paper results are
comparable to backtests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperCostModel:
    spread: float = 0.30
    slippage: float = 0.10
    latency_slippage: float = 0.05
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0

    @property
    def adverse(self) -> float:
        return self.spread / 2.0 + self.slippage + self.latency_slippage

    def entry_fill(self, direction: str, mid_price: float) -> float:
        return mid_price + self.adverse if direction == "long" else mid_price - self.adverse

    def exit_fill(self, direction: str, mid_price: float) -> float:
        return mid_price - self.adverse if direction == "long" else mid_price + self.adverse

    def commission(self, lots: float) -> float:
        return self.commission_per_lot * lots

    def gross_pnl(self, direction: str, entry: float, exit_price: float, lots: float) -> float:
        move = (exit_price - entry) if direction == "long" else (entry - exit_price)
        return move * lots * self.value_per_unit

    def net_pnl(self, direction: str, entry: float, exit_price: float, lots: float) -> float:
        return self.gross_pnl(direction, entry, exit_price, lots) - self.commission(lots)


def position_lots(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    value_per_unit: float,
    max_lot_size: float,
) -> float:
    """Risk-based lot sizing to the stop distance. Returns 0 on invalid inputs."""
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0 or equity <= 0 or value_per_unit <= 0:
        return 0.0
    risk_amount = equity * (risk_pct / 100.0)
    lots = risk_amount / (stop_distance * value_per_unit)
    return max(0.0, min(lots, max_lot_size))
