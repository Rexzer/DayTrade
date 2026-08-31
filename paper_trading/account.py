"""Paper account state (pure Python).

Holds realized cash balance, open positions, pending orders, closed trades and
daily/drawdown tracking. Behaviour (fills, risk checks) lives in the engine;
this is the state container it mutates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from paper_trading.config import PaperAccountConfig
from paper_trading.models import PaperOrder, PaperPosition, PaperTradeRecord


def _day_key(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass
class PaperAccount:
    config: PaperAccountConfig
    balance: float = 0.0
    peak_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    day_key: str | None = None
    day_start_balance: float = 0.0
    paused: bool = False
    halted: bool = False
    halt_reason: str | None = None

    positions: dict[str, PaperPosition] = field(default_factory=dict)
    pending_orders: dict[str, PaperOrder] = field(default_factory=dict)
    closed_trades: list[PaperTradeRecord] = field(default_factory=list)

    _seq: int = 0

    def __post_init__(self) -> None:
        if self.balance == 0.0:
            self.reset()

    def reset(self) -> None:
        self.balance = self.config.starting_balance
        self.peak_equity = self.config.starting_balance
        self.max_drawdown_pct = 0.0
        self.day_key = None
        self.day_start_balance = self.config.starting_balance
        self.paused = False
        self.halted = False
        self.halt_reason = None
        self.positions.clear()
        self.pending_orders.clear()
        self.closed_trades.clear()
        self._seq = 0

    def next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"

    # --- daily / equity tracking --------------------------------------------
    def roll_day(self, epoch: float) -> None:
        """Reset daily counters (and clear a daily-loss halt) on a new UTC day."""
        key = _day_key(epoch)
        if self.day_key != key:
            self.day_key = key
            self.day_start_balance = self.balance
            if self.halted and self.halt_reason and "daily loss" in self.halt_reason.lower():
                self.halted = False
                self.halt_reason = None

    def realized_daily_pnl(self) -> float:
        return self.balance - self.day_start_balance

    def unrealized(self, price: float) -> float:
        return sum(p.unrealized(price, self.config.value_per_unit) for p in self.positions.values())

    def equity(self, price: float | None) -> float:
        if price is None:
            return self.balance
        return self.balance + self.unrealized(price)

    def update_drawdown(self, price: float | None) -> None:
        eq = self.equity(price)
        if eq > self.peak_equity:
            self.peak_equity = eq
        if self.peak_equity > 0:
            dd = (self.peak_equity - eq) / self.peak_equity
            self.max_drawdown_pct = max(self.max_drawdown_pct, dd)

    def open_position_count(self) -> int:
        return len(self.positions)

    def snapshot(self, price: float | None) -> dict:
        eq = self.equity(price)
        dd_now = 0.0
        if self.peak_equity > 0:
            dd_now = max(0.0, (self.peak_equity - eq) / self.peak_equity)
        return {
            "balance": round(self.balance, 2),
            "equity": round(eq, 2),
            "unrealized_pnl": round(self.unrealized(price), 2) if price is not None else None,
            "realized_daily_pnl": round(self.realized_daily_pnl(), 2),
            "daily_loss_pct": round(
                max(0.0, -self.realized_daily_pnl()) / self.config.starting_balance, 4
            ),
            "drawdown_pct_now": round(dd_now, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "open_positions": self.open_position_count(),
            "paused": self.paused,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "peak_equity": round(self.peak_equity, 2),
        }
