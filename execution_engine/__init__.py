"""Execution engine — HARD-DISABLED in Phase 1.

This package exists only to reserve the interface. Any attempt to place,
modify, or close an order raises :class:`ExecutionDisabledError`. Live order
execution is implemented in Phase 6, and only behind explicit user
authorization, a verified MetaTrader connection, and a working kill switch.
"""

from execution_engine.engine import (
    ExecutionDisabledError,
    ExecutionEngine,
    OrderRequest,
)

__all__ = ["ExecutionDisabledError", "ExecutionEngine", "OrderRequest"]
