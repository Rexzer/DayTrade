"""Paper-trading engine (Phase 5).

A virtual-account trading simulator driven by LIVE market data and strategy
signals. It simulates market/limit/stop orders, stop-loss/take-profit, partial
exits and trailing stops with realistic (adverse) fills, enforces risk limits,
records a full journal, and cleanly separates a SIGNAL from an executed TRADE.

It can NEVER place a real order — every fill is simulated.
"""

from paper_trading.config import PaperAccountConfig
from paper_trading.engine import PaperTradingEngine, SignalDecision
from paper_trading.models import (
    JournalEntry,
    OrderSide,
    OrderStatus,
    OrderType,
    PaperOrder,
    PaperPosition,
    PaperTradeRecord,
)
from paper_trading.performance import overall_performance, performance_by_strategy

IMPLEMENTED = True

__all__ = [
    "PaperAccountConfig",
    "PaperTradingEngine",
    "SignalDecision",
    "PaperOrder",
    "PaperPosition",
    "PaperTradeRecord",
    "JournalEntry",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "overall_performance",
    "performance_by_strategy",
]
