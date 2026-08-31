"""Execution engine.

Live/automated ORDER EXECUTION is hard-disabled until Phase 7 — every write
operation raises. Phase 6 adds MetaTrader 5 connectivity for READS only:
account, symbol specs, ticks, historical data, positions, orders and trade
history, plus dry-run order validation and account verification.

The base :class:`ExecutionEngine` remains a fail-closed placeholder; the
:class:`MT5ExecutionProvider` implements the read surface behind the
:class:`ExecutionProvider` interface and refuses all writes.
"""

from execution_engine.engine import (
    ExecutionDisabledError,
    ExecutionEngine,
    OrderRequest,
)
from execution_engine.mt5_connector import MT5ExecutionProvider
from execution_engine.mt5_market_data import MT5MarketDataProvider
from execution_engine.provider import (
    BrokerAccountInfo,
    BrokerConnectionError,
    BrokerOrder,
    BrokerPosition,
    BrokerSymbolSpec,
    BrokerTick,
    ExecOrderRequest,
    ExecutionProvider,
    InvalidSymbolError,
    LiveExecutionDisabledError,
    OrderCheckResult,
    OrderResult,
    validate_order,
)
from execution_engine.sync import PositionSynchronizer, SyncDiff
from execution_engine.verification import build_account_verification

__all__ = [
    "ExecutionDisabledError",
    "ExecutionEngine",
    "OrderRequest",
    "ExecutionProvider",
    "LiveExecutionDisabledError",
    "BrokerConnectionError",
    "InvalidSymbolError",
    "BrokerAccountInfo",
    "BrokerSymbolSpec",
    "BrokerTick",
    "BrokerPosition",
    "BrokerOrder",
    "ExecOrderRequest",
    "OrderCheckResult",
    "OrderResult",
    "validate_order",
    "MT5ExecutionProvider",
    "MT5MarketDataProvider",
    "PositionSynchronizer",
    "SyncDiff",
    "build_account_verification",
]
