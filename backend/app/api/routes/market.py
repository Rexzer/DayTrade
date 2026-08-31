"""Market-data endpoints (Phase 1: null provider only)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.status import ConnectionStatus, DataStatus
from market_data import NullMarketDataProvider, Timeframe

router = APIRouter(prefix="/market", tags=["market"])

# Phase 1 uses the null provider — no fabricated prices.
_provider = NullMarketDataProvider()


@router.get("/snapshot")
def snapshot(symbol: str = "XAUUSD") -> dict:
    snap = _provider.get_snapshot(symbol)
    return {
        **snap.to_dict(),
        "connection_status": (
            ConnectionStatus.CONNECTED.value
            if _provider.is_connected()
            else ConnectionStatus.DISCONNECTED.value
        ),
        "data_status": (
            DataStatus.LIVE.value if _provider.is_connected() else DataStatus.DISCONNECTED.value
        ),
    }


@router.get("/timeframes")
def timeframes() -> dict:
    return {"timeframes": [tf.value for tf in Timeframe.ordered()]}


@router.get("/candles")
def candles(symbol: str = "XAUUSD", timeframe: str = "15m", limit: int = 500) -> dict:
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        tf = Timeframe.M15
    data = _provider.get_candles(symbol, tf, limit=limit)
    return {
        "symbol": symbol,
        "timeframe": tf.value,
        "connected": _provider.is_connected(),
        "candles": [c.to_dict() for c in data],
        "note": "No market-data provider connected in Phase 1.",
    }
