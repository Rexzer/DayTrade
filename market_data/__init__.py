"""Market-data abstraction layer.

Defines a provider-agnostic interface so concrete data sources (broker feeds,
MetaTrader, third-party APIs) can be plugged in without touching the rest of
the application.

Phase 2 adds: a tick model, UTC-aligned candle aggregation, feed-health/stale
detection, a reconnection state machine, broker-symbol mapping, a clearly
labelled simulated provider (for offline development), and a generic REST
provider scaffold for real feeds. The NullMarketDataProvider remains for the
"no source connected" state and never fabricates prices.
"""

from market_data.candle_engine import AggregationResult, CandleAggregator
from market_data.health import FeedHealth, FeedHealthMonitor
from market_data.null_provider import NullMarketDataProvider
from market_data.provider import (
    Candle,
    MarketDataProvider,
    PriceSnapshot,
    SymbolSpec,
    Timeframe,
)
from market_data.reconnection import ConnectionState, ReconnectionController
from market_data.simulated_provider import SimulatedMarketDataProvider
from market_data.symbols import CANONICAL_XAUUSD, SymbolMapper
from market_data.tick import Tick

__all__ = [
    "MarketDataProvider",
    "PriceSnapshot",
    "SymbolSpec",
    "Timeframe",
    "Candle",
    "Tick",
    "NullMarketDataProvider",
    "AggregationResult",
    "CandleAggregator",
    "FeedHealth",
    "FeedHealthMonitor",
    "ConnectionState",
    "ReconnectionController",
    "SymbolMapper",
    "CANONICAL_XAUUSD",
    "SimulatedMarketDataProvider",
]
