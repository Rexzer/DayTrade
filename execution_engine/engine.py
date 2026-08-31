"""Disabled execution engine (pure Python, safety-critical).

Every order-facing method fails closed. There is no code path in Phase 1 that
can reach a broker. The ``enabled`` flag defaults to False and cannot be
flipped on by configuration in this phase — the guard is enforced in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass(frozen=True)
class OrderRequest:
    """A prospective order. Constructing one is harmless; submitting is not."""

    symbol: str
    side: str  # "buy" | "sell"
    order_type: OrderType
    volume_lots: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


class ExecutionDisabledError(RuntimeError):
    """Raised whenever any execution operation is attempted in Phase 1."""


_DISABLED_MESSAGE = (
    "Execution engine is disabled. Live/automated order execution is not "
    "implemented in Phase 1 (analysis-only). It is added in Phase 6 behind "
    "explicit user authorization and a verified broker connection."
)


class ExecutionEngine:
    """Placeholder execution engine that refuses to execute anything."""

    def __init__(self) -> None:
        # Immutable in Phase 1: there is no setter and no config path to True.
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _refuse(self) -> None:
        raise ExecutionDisabledError(_DISABLED_MESSAGE)

    def submit_order(self, request: OrderRequest) -> None:
        self._refuse()

    def modify_position(self, position_id: str, **changes) -> None:
        self._refuse()

    def close_position(self, position_id: str, volume_lots: float | None = None) -> None:
        self._refuse()

    def cancel_order(self, order_id: str) -> None:
        self._refuse()

    def kill_switch(self) -> None:
        """No-op in Phase 1 (nothing is running), but always safe to call."""
        # Intentionally does nothing except assert the disabled invariant.
        assert self._enabled is False
