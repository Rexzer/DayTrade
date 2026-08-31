"""Execution-provider abstraction + broker data models (pure Python).

Defines the venue-agnostic ``ExecutionProvider`` interface and the data types
returned by a broker (account, symbol spec, positions, orders). READ operations
(account/symbol/positions/orders/history) are always available; WRITE
operations (send/modify/close) are HARD-DISABLED until Phase 7 — every attempt
raises :class:`LiveExecutionDisabledError`, regardless of configuration.

``check_order`` is a safe, read-only dry-run validation and is allowed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Phase gate: live order execution is implemented in Phase 7, not here.
LIVE_EXECUTION_IMPLEMENTED = False


class LiveExecutionDisabledError(RuntimeError):
    """Raised when a write/execution op is attempted while live is disabled."""


class BrokerConnectionError(RuntimeError):
    """Raised when the broker connection cannot be established."""


class InvalidSymbolError(ValueError):
    """Raised when a requested symbol is unknown to the broker."""


# --- Data models -------------------------------------------------------------


@dataclass(frozen=True)
class BrokerAccountInfo:
    login: int | None = None
    name: str | None = None
    server: str | None = None
    company: str | None = None
    currency: str | None = None
    balance: float | None = None
    equity: float | None = None
    margin: float | None = None
    free_margin: float | None = None
    margin_level: float | None = None
    leverage: int | None = None
    trade_mode: str | None = None  # "demo" | "real" | "contest"

    def to_dict(self) -> dict:
        return {
            "login": self.login,
            "name": self.name,
            "server": self.server,
            "company": self.company,
            "currency": self.currency,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "margin_level": self.margin_level,
            "leverage": self.leverage,
            "trade_mode": self.trade_mode,
        }


@dataclass(frozen=True)
class BrokerSymbolSpec:
    """Actual broker contract spec — NEVER assumed to be universal."""

    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    trade_allowed: bool = True
    description: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "digits": self.digits,
            "point": self.point,
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "contract_size": self.contract_size,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
            "trade_allowed": self.trade_allowed,
            "description": self.description,
        }


@dataclass(frozen=True)
class BrokerTick:
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None = None
    volume: float | None = None
    time_epoch: float | None = None

    @property
    def spread(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return round(self.ask - self.bid, 6)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "spread": self.spread,
            "time_epoch": self.time_epoch,
        }


@dataclass(frozen=True)
class BrokerPosition:
    ticket: int
    symbol: str
    side: str  # "buy" | "sell"
    volume: float
    price_open: float
    stop_loss: float | None = None
    take_profit: float | None = None
    price_current: float | None = None
    profit: float | None = None
    time_epoch: float | None = None

    def to_dict(self) -> dict:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "price_open": self.price_open,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "price_current": self.price_current,
            "profit": self.profit,
            "time_epoch": self.time_epoch,
        }


@dataclass(frozen=True)
class BrokerOrder:
    ticket: int
    symbol: str
    side: str
    order_type: str  # "market" | "limit" | "stop"
    volume: float
    price_open: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    state: str | None = None
    time_epoch: float | None = None

    def to_dict(self) -> dict:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "volume": self.volume,
            "price_open": self.price_open,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "state": self.state,
            "time_epoch": self.time_epoch,
        }


@dataclass(frozen=True)
class ExecOrderRequest:
    """A prospective order for validation/execution."""

    symbol: str
    side: str  # "buy" | "sell"
    order_type: str  # "market" | "limit" | "stop"
    volume: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class OrderCheckResult:
    ok: bool
    reasons: tuple[str, ...] = ()
    retcode: int | None = None
    comment: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "retcode": self.retcode,
            "comment": self.comment,
        }


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    order_id: int | None = None
    price: float | None = None
    retcode: int | None = None
    comment: str | None = None


# --- Abstract provider -------------------------------------------------------


class ExecutionProvider(ABC):
    """Venue-agnostic execution/broker interface.

    Write operations are gated by :meth:`_require_live`, which in Phase 6 ALWAYS
    raises (live execution is implemented in Phase 7). Concrete providers must
    not override the gate.
    """

    name: str = "abstract"

    # Legacy flag retained for compatibility; it does NOT unlock execution.
    live_enabled: bool = False

    # The single authorization gate. Writes are refused unless this is set to a
    # LiveAuthorization whose is_authorized() returns True. Default None => all
    # writes disabled (Phase 6 semantics preserved).
    authorization: object | None = None

    # --- connection ----------------------------------------------------------
    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    # --- reads ---------------------------------------------------------------
    @abstractmethod
    def get_account_info(self) -> BrokerAccountInfo: ...

    @abstractmethod
    def get_symbol_spec(self, symbol: str) -> BrokerSymbolSpec: ...

    @abstractmethod
    def get_tick(self, symbol: str) -> BrokerTick: ...

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    def get_orders(self) -> list[BrokerOrder]: ...

    # --- validation (safe / read-only) --------------------------------------
    @abstractmethod
    def check_order(self, request: ExecOrderRequest) -> OrderCheckResult: ...

    # --- writes (require explicit authorization) ----------------------------
    def _require_authorized(self) -> None:
        auth = self.authorization
        if auth is None or not auth.is_authorized():
            raise LiveExecutionDisabledError(
                "Live order execution is NOT authorized. It requires an explicit "
                "authorization: LIVE_EXECUTION_ENABLED at the backend, all user "
                "confirmations, an explicit arm action, and no active kill switch."
            )

    # Backwards-compatible alias.
    def _require_live(self) -> None:
        self._require_authorized()

    def send_order(self, request: ExecOrderRequest) -> OrderResult:
        self._require_authorized()
        raise NotImplementedError("This provider does not implement send_order.")

    def modify_order(self, ticket: int, *, stop_loss=None, take_profit=None) -> OrderResult:
        self._require_authorized()
        raise NotImplementedError("This provider does not implement modify_order.")

    def close_position(self, ticket: int, volume: float | None = None) -> OrderResult:
        self._require_authorized()
        raise NotImplementedError("This provider does not implement close_position.")


# --- Order validation (pure) -------------------------------------------------


def _almost_multiple(value: float, step: float, tol: float = 1e-9) -> bool:
    if step <= 0:
        return True
    ratio = value / step
    return abs(ratio - round(ratio)) <= 1e-6 or abs(value - round(ratio) * step) <= tol


def validate_order(request: ExecOrderRequest, spec: BrokerSymbolSpec) -> OrderCheckResult:
    """Validate volume and SL/TP geometry against the broker spec (dry-run).

    Covers the required edge cases: invalid volume (below min / above max / not
    a multiple of step) and invalid SL/TP (wrong side of price / equal to price).
    """
    reasons: list[str] = []

    if request.symbol != spec.name:
        reasons.append(f"Symbol mismatch: request '{request.symbol}' vs spec '{spec.name}'.")

    v = request.volume
    if v <= 0:
        reasons.append("Volume must be > 0.")
    else:
        if v < spec.volume_min:
            reasons.append(f"Volume {v} below minimum {spec.volume_min}.")
        if v > spec.volume_max:
            reasons.append(f"Volume {v} above maximum {spec.volume_max}.")
        if not _almost_multiple(v, spec.volume_step):
            reasons.append(f"Volume {v} is not a multiple of step {spec.volume_step}.")

    # Reference price for SL/TP side checks.
    ref = request.price
    if ref is not None:
        sl, tp = request.stop_loss, request.take_profit
        if request.side == "buy":
            if sl is not None and sl >= ref:
                reasons.append("For a BUY, stop-loss must be below the price.")
            if tp is not None and tp <= ref:
                reasons.append("For a BUY, take-profit must be above the price.")
        elif request.side == "sell":
            if sl is not None and sl <= ref:
                reasons.append("For a SELL, stop-loss must be above the price.")
            if tp is not None and tp >= ref:
                reasons.append("For a SELL, take-profit must be below the price.")
        else:
            reasons.append(f"Unknown side '{request.side}'.")
        if sl is not None and abs(sl - ref) < spec.point:
            reasons.append("Stop-loss is effectively equal to the price.")
        if tp is not None and abs(tp - ref) < spec.point:
            reasons.append("Take-profit is effectively equal to the price.")

    if not spec.trade_allowed:
        reasons.append(f"Trading is not allowed on symbol '{spec.name}'.")

    return OrderCheckResult(ok=not reasons, reasons=tuple(reasons))
