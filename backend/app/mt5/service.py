"""MT5Service — backend MetaTrader 5 integration (Phase 6, READ-ONLY).

Owns a single MT5ExecutionProvider built from configuration (credentials come
from the environment/secret store and are never logged or returned). Exposes
account/symbol/tick/history/positions/orders reads, position synchronization
and account verification.

Order EXECUTION is disabled: the provider refuses all writes, and there is no
route that can place an order. Live execution arrives in Phase 7 behind
explicit authorization.
"""

from __future__ import annotations

from backend.app.config import get_settings
from backend.app.core.logging_config import get_logger
from execution_engine import (
    BrokerConnectionError,
    ExecOrderRequest,
    InvalidSymbolError,
    MT5ExecutionProvider,
    PositionSynchronizer,
    build_account_verification,
)
from market_data.provider import Timeframe

logger = get_logger("mt5")


class MT5Service:
    def __init__(self) -> None:
        s = get_settings()
        self.symbol = s.mt5_symbol
        self.provider = MT5ExecutionProvider(
            login=s.mt5_login,
            password=s.mt5_password,  # read from env; not stored/logged
            server=s.mt5_server,
            path=s.mt5_path,
            live_enabled=False,  # Phase 6: never enable writes
        )
        self.sync = PositionSynchronizer()

    # ------------------------------------------------------------- connection
    def connect(self) -> dict:
        try:
            ok = self.provider.connect(retries=3)
        except Exception as exc:  # noqa: BLE001
            return {"connected": False, "error": str(exc)}
        return {"connected": ok, "error": self.provider.last_error if not ok else None}

    def disconnect(self) -> dict:
        self.provider.disconnect()
        return {"connected": False}

    def status(self) -> dict:
        return {
            "provider": self.provider.name,
            "connected": self.provider.is_connected(),
            "connect_attempts": self.provider.connect_attempts,
            "last_error": self.provider.last_error,
            "symbol": self.symbol,
            "live_execution_enabled": False,
            "note": "Read-only MetaTrader 5 integration. Order execution is disabled (Phase 7).",
        }

    # ------------------------------------------------------------- reads
    def account(self) -> dict:
        try:
            return self.provider.get_account_info().to_dict()
        except BrokerConnectionError as exc:
            return {"error": str(exc)}

    def symbol_info(self, symbol: str | None = None) -> dict:
        sym = symbol or self.symbol
        try:
            return self.provider.get_symbol_spec(sym).to_dict()
        except (InvalidSymbolError, BrokerConnectionError) as exc:
            return {"error": str(exc)}

    def tick(self, symbol: str | None = None) -> dict:
        sym = symbol or self.symbol
        try:
            return self.provider.get_tick(sym).to_dict()
        except (InvalidSymbolError, BrokerConnectionError) as exc:
            return {"error": str(exc)}

    def positions(self) -> dict:
        try:
            return {"positions": [p.to_dict() for p in self.provider.get_positions()]}
        except BrokerConnectionError as exc:
            return {"error": str(exc), "positions": []}

    def orders(self) -> dict:
        try:
            return {"orders": [o.to_dict() for o in self.provider.get_orders()]}
        except BrokerConnectionError as exc:
            return {"error": str(exc), "orders": []}

    def history(self, from_epoch: float, to_epoch: float) -> dict:
        try:
            return {"deals": self.provider.get_history(from_epoch, to_epoch)}
        except BrokerConnectionError as exc:
            return {"error": str(exc), "deals": []}

    def historical_candles(self, symbol: str | None, timeframe: str, count: int = 200) -> dict:
        sym = symbol or self.symbol
        try:
            tf = Timeframe(timeframe)
        except ValueError:
            tf = Timeframe.H1
        try:
            candles = self.provider.get_historical(sym, tf, count=count)
            return {"symbol": sym, "timeframe": tf.value, "candles": [c.to_dict() for c in candles]}
        except (InvalidSymbolError, BrokerConnectionError) as exc:
            return {"error": str(exc), "candles": []}

    def synchronize(self) -> dict:
        try:
            diff = self.sync.diff(self.provider.get_positions())
            return diff.to_dict()
        except BrokerConnectionError as exc:
            return {"error": str(exc)}

    def verify(self) -> dict:
        return build_account_verification(self.provider, self.symbol)

    # ------------------------------------------------------------- validation
    def check_order(
        self,
        side: str,
        volume: float,
        price: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        symbol: str | None = None,
        order_type: str = "market",
    ) -> dict:
        req = ExecOrderRequest(
            symbol=symbol or self.symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return self.provider.check_order(req).to_dict()


_service: MT5Service | None = None


def get_mt5_service() -> MT5Service:
    global _service
    if _service is None:
        _service = MT5Service()
    return _service
