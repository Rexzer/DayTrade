"""MT5 as a market-data source (adapter to the MarketDataProvider interface).

Lets MetaTrader 5 be selected via ``MARKET_DATA_PROVIDER=mt5``. It delegates to
an :class:`MT5ExecutionProvider` for ticks and historical candles, so the same
verified connection powers both data and (future) execution. Read-only.
"""

from __future__ import annotations

from execution_engine.mt5_connector import MT5ExecutionProvider
from execution_engine.provider import BrokerConnectionError, InvalidSymbolError
from market_data.provider import Candle, MarketDataProvider, PriceSnapshot, SymbolSpec, Timeframe
from market_data.tick import Tick


class MT5MarketDataProvider(MarketDataProvider):
    name = "mt5"

    def __init__(self, connector: MT5ExecutionProvider) -> None:
        self._c = connector

    def connect(self) -> bool:
        return self._c.connect(retries=3)

    def disconnect(self) -> None:
        self._c.disconnect()

    def is_connected(self) -> bool:
        return self._c.is_connected()

    def supported_timeframes(self) -> list[Timeframe]:
        return Timeframe.ordered()

    def symbol_spec(self, symbol: str) -> SymbolSpec:
        try:
            spec = self._c.get_symbol_spec(symbol)
            return SymbolSpec(
                canonical="XAUUSD",
                broker_symbol=spec.name,
                digits=spec.digits,
                point=spec.point,
                description=spec.description or "Gold vs US Dollar",
            )
        except (InvalidSymbolError, BrokerConnectionError):
            return SymbolSpec(canonical="XAUUSD", broker_symbol=symbol)

    def get_snapshot(self, symbol: str) -> PriceSnapshot:
        if not self._c.is_connected():
            return PriceSnapshot(symbol=symbol, connected=False, source=self.name)
        try:
            t = self._c.get_tick(symbol)
        except (InvalidSymbolError, BrokerConnectionError):
            return PriceSnapshot(symbol=symbol, connected=False, source=self.name)
        return PriceSnapshot(
            symbol=symbol,
            connected=True,
            bid=t.bid,
            ask=t.ask,
            last=t.last,
            timestamp_epoch=t.time_epoch,
            source=self.name,
        )

    def get_tick(self, symbol: str) -> Tick | None:
        if not self._c.is_connected():
            return None
        try:
            t = self._c.get_tick(symbol)
        except (InvalidSymbolError, BrokerConnectionError):
            return None
        return Tick(
            symbol="XAUUSD",
            timestamp_epoch=float(t.time_epoch or 0.0),
            bid=t.bid,
            ask=t.ask,
            last=t.last,
            volume=t.volume,
            source=self.name,
        )

    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        return self.get_historical_candles(symbol, timeframe, limit=limit)

    def get_historical_candles(
        self, symbol: str, timeframe: Timeframe, limit: int = 500, end_epoch: float | None = None
    ) -> list[Candle]:
        if not self._c.is_connected():
            return []
        try:
            return self._c.get_historical(symbol, timeframe, count=limit)
        except (InvalidSymbolError, BrokerConnectionError):
            return []
