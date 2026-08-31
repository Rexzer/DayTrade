"""Trade and open-position models for the backtester (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OpenPosition:
    """An in-flight position during a backtest."""

    strategy_key: str
    direction: str  # "long" | "short"
    entry_time: float
    entry_price: float  # fill price (already includes costs)
    stop_loss: float
    take_profit: float | None
    lots: float
    entry_index: int

    def unrealized(self, price: float, value_per_unit: float) -> float:
        move = (
            (price - self.entry_price) if self.direction == "long" else (self.entry_price - price)
        )
        return move * self.lots * value_per_unit


@dataclass
class Trade:
    """A completed round-trip trade."""

    strategy_key: str
    direction: str
    entry_time: float
    exit_time: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float | None
    lots: float
    pnl: float  # net of commission
    return_pct: float  # relative to equity at entry
    exit_reason: str  # "take_profit" | "stop_loss" | "signal_exit" | "end_of_data"
    bars_held: int

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    def to_dict(self) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "direction": self.direction,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": round(self.entry_price, 3),
            "exit_price": round(self.exit_price, 3),
            "stop_loss": round(self.stop_loss, 3),
            "take_profit": round(self.take_profit, 3) if self.take_profit is not None else None,
            "lots": round(self.lots, 4),
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 4),
            "exit_reason": self.exit_reason,
            "bars_held": self.bars_held,
            "is_win": self.is_win,
        }
