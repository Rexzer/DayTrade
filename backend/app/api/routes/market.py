"""Market-data endpoints (Phase 2).

Exposes real-time status, quotes, candles, symbol mapping and connection
controls backed by the MarketDataService. Still MARKET DATA ONLY — no orders.
When the provider is "none", every response honestly reports disconnected and
carries no prices.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.status import ConnectionStatus
from backend.app.market_data import get_market_service
from market_data import Timeframe

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/status")
def status() -> dict:
    """Data source, freshness and connection state (source/last-update/status)."""
    return get_market_service().status()


@router.get("/snapshot")
def snapshot(symbol: str = "XAUUSD") -> dict:
    svc = get_market_service()
    snap = svc.snapshot()
    connected = bool(snap.get("connected"))
    snap["connection_status"] = (
        ConnectionStatus.CONNECTED.value if connected else ConnectionStatus.DISCONNECTED.value
    )
    return snap


@router.get("/timeframes")
def timeframes() -> dict:
    return {"timeframes": [tf.value for tf in Timeframe.ordered()]}


@router.get("/candles")
def candles(symbol: str = "XAUUSD", timeframe: str = "15m", limit: int = 300) -> dict:
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        tf = Timeframe.M15
    svc = get_market_service()
    data = svc.get_candles(tf, limit=limit)
    st = svc.status()
    return {
        "symbol": symbol,
        "timeframe": tf.value,
        "connected": st["connected"],
        "source": st["source"],
        "simulated": st["simulated"],
        "candles": data,
    }


@router.get("/symbols")
def symbols() -> dict:
    return get_market_service().symbols()


@router.post("/symbol")
def set_symbol(broker_symbol: str) -> dict:
    if not broker_symbol.strip():
        raise HTTPException(status_code=400, detail="broker_symbol must not be empty.")
    return get_market_service().set_symbol(broker_symbol)
