"""Execution engine.

Order execution flows ONLY through the mandatory pipeline:
    Strategy/Signal -> Authorization -> Risk Engine -> Order Validation ->
    Execution (MetaTrader 5) -> result verification -> log.

Writes are refused unless a :class:`LiveAuthorization` (explicit config flag +
all user confirmations + explicit arm + no kill switch) authorizes them; the
authorization is in-memory so a restart disables live trading. The
:class:`ExecutionCoordinator` is the only path to a live order and cannot
bypass the independent risk engine.
"""

from execution_engine.authorization import (
    CONFIRMATION_LABELS,
    REQUIRED_CONFIRMATIONS,
    AuthorizationError,
    LiveAuthorization,
)
from execution_engine.coordinator import (
    ExecutionCoordinator,
    ExecutionLog,
    ExecutionOutcome,
)
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
    "LiveAuthorization",
    "AuthorizationError",
    "REQUIRED_CONFIRMATIONS",
    "CONFIRMATION_LABELS",
    "ExecutionCoordinator",
    "ExecutionLog",
    "ExecutionOutcome",
]
