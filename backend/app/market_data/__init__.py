"""Backend market-data integration layer.

Orchestrates a market_data provider into the running FastAPI app: builds
candles, tracks health, drives reconnection/backfill, persists candles, and
broadcasts real-time updates over WebSockets.
"""

from backend.app.market_data.service import MarketDataService, get_market_service

__all__ = ["MarketDataService", "get_market_service"]
