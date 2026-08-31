"""Market-data abstraction layer.

Defines a provider-agnostic interface so concrete data sources (broker feeds,
MetaTrader, third-party APIs) can be plugged in without touching the rest of
the application. Phase 1 ships only the NullMarketDataProvider, which reports
a disconnected state and never fabricates prices.
"""

from market_data.null_provider import NullMarketDataProvider
from market_data.provider import (
    MarketDataProvider,
    PriceSnapshot,
    Timeframe,
)

__all__ = [
    "MarketDataProvider",
    "PriceSnapshot",
    "Timeframe",
    "NullMarketDataProvider",
]
