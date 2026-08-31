"""Null market-data provider used in Phase 1.

Represents the "no data source connected" state. It always reports a
disconnected snapshot with ``None`` prices and returns no candles. This is
what lets the UI honestly display "DATA SOURCE NOT CONNECTED" instead of
inventing numbers.
"""

from __future__ import annotations

from market_data.provider import Candle, MarketDataProvider, PriceSnapshot, Timeframe


class NullMarketDataProvider(MarketDataProvider):
    name = "none"

    def is_connected(self) -> bool:
        return False

    def get_snapshot(self, symbol: str) -> PriceSnapshot:
        return PriceSnapshot(symbol=symbol, connected=False, source=self.name)

    def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500) -> list[Candle]:
        return []

    def supported_timeframes(self) -> list[Timeframe]:
        return Timeframe.ordered()
