"""Durable trade/signal/order persistence — interface + records (pure Python).

This module defines the storage contract and the record types, plus an
in-memory implementation used for tests and for graceful operation when no
database is configured. The SQLAlchemy-backed implementation lives in
``sql_store.py`` and is imported lazily so this module has NO third-party
dependency and is fully unit-testable offline.

Persisting live signals/orders/trades makes analytics durable across restarts.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


@dataclass
class StoredSignal:
    strategy_key: str
    symbol: str
    timeframe: str | None
    level: int
    direction: str | None
    regime: str | None = None
    confidence_score: int | None = None
    reasoning: str | None = None  # JSON-serialisable explanation
    epoch: float = field(default_factory=time.time)
    id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StoredOrder:
    account_label: str
    symbol: str
    side: str  # buy | sell
    order_type: str  # market | limit | stop
    volume_lots: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    status: str = "submitted"  # submitted | filled | rejected
    mode: str = "live"
    broker_order_id: int | None = None
    retcode: int | None = None
    comment: str | None = None
    epoch: float = field(default_factory=time.time)
    id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StoredTrade:
    strategy_key: str | None
    symbol: str
    side: str
    volume_lots: float
    entry_price: float | None
    exit_price: float | None
    pnl: float | None
    exit_reason: str | None = None
    regime: str | None = None
    mode: str = "live"
    opened_epoch: float | None = None
    closed_epoch: float | None = None
    id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def stored_trade_from_position(
    pos, *, mode: str = "live", closed_epoch: float | None = None
) -> StoredTrade:
    """Build a round-trip ``StoredTrade`` from a (now-closed) broker position.

    Accepts any object exposing symbol/side/volume/price_open/price_current/
    profit/time_epoch (e.g. a BrokerPosition) — duck-typed so this module stays
    dependency-free. The exit price is the last-known current price and the P&L
    is the broker's last-reported profit for the position.
    """
    return StoredTrade(
        strategy_key=None,
        symbol=getattr(pos, "symbol", "XAUUSD"),
        side=getattr(pos, "side", "?"),
        volume_lots=getattr(pos, "volume", 0.0) or 0.0,
        entry_price=getattr(pos, "price_open", None),
        exit_price=getattr(pos, "price_current", None),
        pnl=getattr(pos, "profit", None),
        exit_reason="closed",
        mode=mode,
        opened_epoch=getattr(pos, "time_epoch", None),
        closed_epoch=closed_epoch,
    )


class TradeStore(ABC):
    """Storage contract for durable live records."""

    @abstractmethod
    def save_signal(self, signal: StoredSignal) -> int: ...

    @abstractmethod
    def save_order(self, order: StoredOrder) -> int: ...

    @abstractmethod
    def save_trade(self, trade: StoredTrade) -> int: ...

    @abstractmethod
    def recent_signals(self, limit: int = 100) -> list[dict]: ...

    @abstractmethod
    def recent_orders(self, limit: int = 100) -> list[dict]: ...

    @abstractmethod
    def recent_trades(self, limit: int = 100) -> list[dict]: ...

    # --- risk state (single latest snapshot) --------------------------------
    @abstractmethod
    def save_risk_state(self, state: dict) -> None:
        """Persist the latest risk-engine state (halts, counters, equity)."""

    @abstractmethod
    def load_risk_state(self) -> dict | None:
        """Return the last persisted risk-engine state, or None if never saved."""


class InMemoryTradeStore(TradeStore):
    """Non-persistent store (tests + no-DB fallback). Auto-increments ids."""

    def __init__(self) -> None:
        self._signals: list[StoredSignal] = []
        self._orders: list[StoredOrder] = []
        self._trades: list[StoredTrade] = []
        self._risk_state: dict | None = None
        self._seq = 0

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    def save_signal(self, signal: StoredSignal) -> int:
        signal.id = self._next_id()
        self._signals.append(signal)
        return signal.id

    def save_order(self, order: StoredOrder) -> int:
        order.id = self._next_id()
        self._orders.append(order)
        return order.id

    def save_trade(self, trade: StoredTrade) -> int:
        trade.id = self._next_id()
        self._trades.append(trade)
        return trade.id

    def recent_signals(self, limit: int = 100) -> list[dict]:
        return [s.to_dict() for s in self._signals[-limit:][::-1]]

    def recent_orders(self, limit: int = 100) -> list[dict]:
        return [o.to_dict() for o in self._orders[-limit:][::-1]]

    def recent_trades(self, limit: int = 100) -> list[dict]:
        return [t.to_dict() for t in self._trades[-limit:][::-1]]

    def save_risk_state(self, state: dict) -> None:
        self._risk_state = dict(state) if state is not None else None

    def load_risk_state(self) -> dict | None:
        return dict(self._risk_state) if self._risk_state is not None else None
