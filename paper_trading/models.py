"""Paper-trading domain models (pure Python)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class PaperOrder:
    id: str
    side: OrderSide
    order_type: OrderType
    requested_lots: float
    strategy_key: str = "manual"
    strategy_name: str = "Manual"
    regime: str | None = None
    price: float | None = None  # limit/stop trigger price
    stop_loss: float | None = None
    take_profit: float | None = None
    created_epoch: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_lots: float = 0.0
    avg_fill_price: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "requested_lots": round(self.requested_lots, 4),
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "status": self.status.value,
            "filled_lots": round(self.filled_lots, 4),
            "avg_fill_price": self.avg_fill_price,
            "reason": self.reason,
            "created_epoch": self.created_epoch,
        }


@dataclass
class PaperPosition:
    id: str
    direction: str  # "long" | "short"
    entry_price: float
    lots: float
    strategy_key: str
    strategy_name: str
    opened_epoch: float
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_2: float | None = None  # remainder target after a partial exit
    regime: str | None = None
    realized_pnl: float = 0.0  # from partial exits
    partial_taken: bool = False
    initial_lots: float = 0.0
    highest_price: float = 0.0  # for trailing (long)
    lowest_price: float = float("inf")  # for trailing (short)

    def unrealized(self, price: float, value_per_unit: float) -> float:
        move = (
            (price - self.entry_price) if self.direction == "long" else (self.entry_price - price)
        )
        return move * self.lots * value_per_unit

    def to_dict(self, price: float | None = None, value_per_unit: float = 1.0) -> dict:
        return {
            "id": self.id,
            "direction": self.direction,
            "entry_price": round(self.entry_price, 3),
            "current_price": round(price, 3) if price is not None else None,
            "lots": round(self.lots, 4),
            "stop_loss": round(self.stop_loss, 3) if self.stop_loss is not None else None,
            "take_profit": round(self.take_profit, 3) if self.take_profit is not None else None,
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "regime": self.regime,
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": (
                round(self.unrealized(price, value_per_unit), 2) if price is not None else None
            ),
            "opened_epoch": self.opened_epoch,
        }


@dataclass
class PaperTradeRecord:
    """A completed (fully-closed) paper trade, for journal + performance."""

    id: str
    strategy_key: str
    strategy_name: str
    direction: str
    entry_price: float
    exit_price: float
    lots: float
    pnl: float
    return_pct: float
    exit_reason: str
    regime: str | None
    opened_epoch: float
    closed_epoch: float
    stop_loss: float | None = None
    take_profit: float | None = None

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "direction": self.direction,
            "entry_price": round(self.entry_price, 3),
            "exit_price": round(self.exit_price, 3),
            "lots": round(self.lots, 4),
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 4),
            "exit_reason": self.exit_reason,
            "regime": self.regime,
            "opened_epoch": self.opened_epoch,
            "closed_epoch": self.closed_epoch,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "is_win": self.is_win,
        }


@dataclass
class JournalEntry:
    epoch: float
    kind: str  # "signal" | "trade_opened" | "trade_closed" | "rejected" | "info"
    message: str
    strategy_key: str | None = None
    strategy_name: str | None = None
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "epoch": self.epoch,
            "kind": self.kind,
            "message": self.message,
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "payload": self.payload,
        }
