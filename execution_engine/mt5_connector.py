"""MetaTrader 5 execution provider (read-only in Phase 6).

Wraps a MetaTrader5-style client. The client is INJECTABLE so the connector is
fully testable with a mock; when none is injected it lazily imports the real
``MetaTrader5`` module (available only on a machine with the MT5 terminal).

READS (account/symbol/tick/history/positions/orders) work. WRITES remain
hard-disabled via the base class until Phase 7. Credentials are provided at
construction from the environment/secret store and are never logged.
"""

from __future__ import annotations

import time

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
    OrderCheckResult,
    validate_order,
)
from market_data.provider import Candle, Timeframe

# MT5 trade-mode codes -> labels.
_TRADE_MODE = {0: "demo", 1: "contest", 2: "real"}

# Fallback MT5 timeframe integer constants (used if the client lacks the attrs).
_TF_FALLBACK = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 16385,
    Timeframe.H4: 16388,
    Timeframe.D1: 16408,
}
_TF_ATTR = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
    Timeframe.M30: "TIMEFRAME_M30",
    Timeframe.H1: "TIMEFRAME_H1",
    Timeframe.H4: "TIMEFRAME_H4",
    Timeframe.D1: "TIMEFRAME_D1",
}

# Retcodes considered a successful order_check.
_OK_RETCODES = {0, 10009}  # 10009 = TRADE_RETCODE_DONE


def _g(obj, name, default=None):
    """Attribute or dict-key getter tolerant of namedtuples and dicts."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class MT5ExecutionProvider(ExecutionProvider):
    name = "metatrader5"

    def __init__(
        self,
        client=None,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        path: str | None = None,
        live_enabled: bool = False,
    ) -> None:
        self._client = client
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        # Phase 6: even if an operator sets this True, writes stay disabled
        # (the base class _require_live always raises until Phase 7).
        self.live_enabled = bool(live_enabled)
        self._connected = False
        self.connect_attempts = 0
        self.last_error: str | None = None

    # --- client resolution ---------------------------------------------------
    def _ensure_client(self):
        if self._client is None:
            try:
                import MetaTrader5 as mt5  # type: ignore
            except Exception as exc:  # noqa: BLE001 - not installed in this env
                raise BrokerConnectionError(
                    "MetaTrader5 package is not available. Inject a client or "
                    "install MetaTrader5 on a machine with the MT5 terminal."
                ) from exc
            self._client = mt5
        return self._client

    # --- connection ----------------------------------------------------------
    def connect(self, retries: int = 1, retry_delay: float = 0.0) -> bool:
        self.connect_attempts += 1
        try:
            client = self._ensure_client()
        except BrokerConnectionError as exc:
            self.last_error = str(exc)
            self._connected = False
            return False

        attempt = 0
        while attempt < max(1, retries):
            attempt += 1
            try:
                kwargs = {}
                if self._path:
                    kwargs["path"] = self._path
                if self._login is not None:
                    kwargs.update(login=self._login, password=self._password, server=self._server)
                initialized = client.initialize(**kwargs) if kwargs else client.initialize()
                if not initialized:
                    self.last_error = self._read_error(client)
                    if attempt < retries and retry_delay:
                        time.sleep(retry_delay)
                    continue
                # Explicit login when credentials are supplied separately.
                if self._login is not None and hasattr(client, "login"):
                    logged_in = client.login(
                        self._login, password=self._password, server=self._server
                    )
                    if not logged_in:
                        self.last_error = self._read_error(client)
                        continue
                self._connected = True
                self.last_error = None
                return True
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                if attempt < retries and retry_delay:
                    time.sleep(retry_delay)
        self._connected = False
        return False

    def reconnect(self, retries: int = 3, retry_delay: float = 0.0) -> bool:
        self.disconnect()
        return self.connect(retries=retries, retry_delay=retry_delay)

    def disconnect(self) -> None:
        if self._client is not None and hasattr(self._client, "shutdown"):
            try:
                self._client.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _read_error(self, client) -> str | None:
        if hasattr(client, "last_error"):
            try:
                err = client.last_error()
                return str(err)
            except Exception:  # noqa: BLE001
                return None
        return None

    def _require_connected(self) -> None:
        if not self._connected:
            raise BrokerConnectionError("Not connected to MetaTrader 5.")

    # --- reads ---------------------------------------------------------------
    def get_account_info(self) -> BrokerAccountInfo:
        self._require_connected()
        ai = self._client.account_info()
        if ai is None:
            raise BrokerConnectionError("account_info() returned no data.")
        return BrokerAccountInfo(
            login=_g(ai, "login"),
            name=_g(ai, "name"),
            server=_g(ai, "server"),
            company=_g(ai, "company"),
            currency=_g(ai, "currency"),
            balance=_g(ai, "balance"),
            equity=_g(ai, "equity"),
            margin=_g(ai, "margin"),
            free_margin=_g(ai, "margin_free"),
            margin_level=_g(ai, "margin_level"),
            leverage=_g(ai, "leverage"),
            trade_mode=_TRADE_MODE.get(_g(ai, "trade_mode"), None),
        )

    def get_symbol_spec(self, symbol: str) -> BrokerSymbolSpec:
        self._require_connected()
        # Make the symbol visible in Market Watch where supported.
        if hasattr(self._client, "symbol_select"):
            try:
                self._client.symbol_select(symbol, True)
            except Exception:  # noqa: BLE001
                pass
        si = self._client.symbol_info(symbol)
        if si is None:
            raise InvalidSymbolError(f"Symbol '{symbol}' is unknown to the broker.")
        return BrokerSymbolSpec(
            name=_g(si, "name", symbol),
            digits=int(_g(si, "digits", 2)),
            point=float(_g(si, "point", 0.01)),
            tick_size=float(_g(si, "trade_tick_size", _g(si, "point", 0.01))),
            tick_value=float(_g(si, "trade_tick_value", 0.0)),
            contract_size=float(_g(si, "trade_contract_size", 100.0)),
            volume_min=float(_g(si, "volume_min", 0.01)),
            volume_max=float(_g(si, "volume_max", 100.0)),
            volume_step=float(_g(si, "volume_step", 0.01)),
            trade_allowed=bool(_g(si, "visible", True)),
            description=_g(si, "description"),
        )

    def get_tick(self, symbol: str) -> BrokerTick:
        self._require_connected()
        t = self._client.symbol_info_tick(symbol)
        if t is None:
            raise InvalidSymbolError(f"No tick for symbol '{symbol}'.")
        return BrokerTick(
            symbol=symbol,
            bid=_g(t, "bid"),
            ask=_g(t, "ask"),
            last=_g(t, "last"),
            volume=_g(t, "volume"),
            time_epoch=_g(t, "time"),
        )

    def get_historical(self, symbol: str, timeframe: Timeframe, count: int = 500) -> list[Candle]:
        self._require_connected()
        tf_const = getattr(self._client, _TF_ATTR[timeframe], _TF_FALLBACK[timeframe])
        rates = self._client.copy_rates_from_pos(symbol, tf_const, 0, count)
        candles: list[Candle] = []
        for r in rates or []:
            candles.append(
                Candle(
                    timeframe=timeframe,
                    open_time_epoch=float(_g(r, "time")),
                    open=float(_g(r, "open")),
                    high=float(_g(r, "high")),
                    low=float(_g(r, "low")),
                    close=float(_g(r, "close")),
                    volume=float(_g(r, "tick_volume", _g(r, "real_volume", 0.0)) or 0.0),
                )
            )
        return candles

    def get_positions(self) -> list[BrokerPosition]:
        self._require_connected()
        raw = self._client.positions_get() or ()
        out = []
        for p in raw:
            out.append(
                BrokerPosition(
                    ticket=int(_g(p, "ticket")),
                    symbol=_g(p, "symbol"),
                    side="buy" if int(_g(p, "type", 0)) == 0 else "sell",
                    volume=float(_g(p, "volume", 0.0)),
                    price_open=float(_g(p, "price_open", 0.0)),
                    stop_loss=_none_if_zero(_g(p, "sl")),
                    take_profit=_none_if_zero(_g(p, "tp")),
                    price_current=_g(p, "price_current"),
                    profit=_g(p, "profit"),
                    time_epoch=_g(p, "time"),
                )
            )
        return out

    def get_orders(self) -> list[BrokerOrder]:
        self._require_connected()
        raw = self._client.orders_get() or ()
        out = []
        for o in raw:
            otype = int(_g(o, "type", 0))
            side = "buy" if otype in (0, 2, 4) else "sell"
            kind = "market" if otype in (0, 1) else ("limit" if otype in (2, 3) else "stop")
            out.append(
                BrokerOrder(
                    ticket=int(_g(o, "ticket")),
                    symbol=_g(o, "symbol"),
                    side=side,
                    order_type=kind,
                    volume=float(_g(o, "volume_current", _g(o, "volume_initial", 0.0))),
                    price_open=_g(o, "price_open"),
                    stop_loss=_none_if_zero(_g(o, "sl")),
                    take_profit=_none_if_zero(_g(o, "tp")),
                    state=str(_g(o, "state", "")),
                    time_epoch=_g(o, "time_setup"),
                )
            )
        return out

    def get_history(self, from_epoch: float, to_epoch: float) -> list[dict]:
        self._require_connected()
        if not hasattr(self._client, "history_deals_get"):
            return []
        deals = self._client.history_deals_get(from_epoch, to_epoch) or ()
        return [
            {
                "ticket": _g(d, "ticket"),
                "symbol": _g(d, "symbol"),
                "volume": _g(d, "volume"),
                "price": _g(d, "price"),
                "profit": _g(d, "profit"),
                "time_epoch": _g(d, "time"),
            }
            for d in deals
        ]

    # --- validation (safe) ---------------------------------------------------
    def check_order(self, request: ExecOrderRequest) -> OrderCheckResult:
        # Local, deterministic validation against the broker's spec.
        try:
            spec = self.get_symbol_spec(request.symbol)
        except (InvalidSymbolError, BrokerConnectionError) as exc:
            return OrderCheckResult(ok=False, reasons=(str(exc),))
        local = validate_order(request, spec)
        if not local.ok:
            return local
        # Optional broker-side dry run (never sends the order).
        if self._connected and hasattr(self._client, "order_check"):
            try:
                res = self._client.order_check(self._to_mt5_request(request))
                retcode = _g(res, "retcode")
                comment = _g(res, "comment")
                if retcode is not None and retcode not in _OK_RETCODES:
                    return OrderCheckResult(
                        ok=False,
                        reasons=(f"Broker rejected check: {comment or retcode}",),
                        retcode=retcode,
                        comment=comment,
                    )
                return OrderCheckResult(ok=True, retcode=retcode, comment=comment)
            except Exception as exc:  # noqa: BLE001
                return OrderCheckResult(ok=False, reasons=(f"order_check failed: {exc}",))
        return local

    def _to_mt5_request(self, request: ExecOrderRequest) -> dict:
        return {
            "symbol": request.symbol,
            "volume": request.volume,
            "type": request.side,
            "price": request.price,
            "sl": request.stop_loss,
            "tp": request.take_profit,
        }


def _none_if_zero(value):
    if value in (None, 0, 0.0):
        return None
    return value
