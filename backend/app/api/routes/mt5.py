"""MetaTrader 5 endpoints (Phase 6, READ-ONLY).

All endpoints here are reads, validation or verification. There is NO endpoint
that can place, modify or close an order — order execution is a Phase 7 feature
and the execution provider refuses all writes. The single /mt5/execution/*
endpoints exist only to make the disabled state explicit.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.mt5 import get_mt5_service

router = APIRouter(prefix="/mt5", tags=["metatrader5"])


@router.get("/status")
def status() -> dict:
    return get_mt5_service().status()


@router.post("/connect")
def connect() -> dict:
    return get_mt5_service().connect()


@router.post("/disconnect")
def disconnect() -> dict:
    return get_mt5_service().disconnect()


@router.get("/account")
def account() -> dict:
    return get_mt5_service().account()


@router.get("/symbol")
def symbol(name: str | None = None) -> dict:
    return get_mt5_service().symbol_info(name)


@router.get("/tick")
def tick(name: str | None = None) -> dict:
    return get_mt5_service().tick(name)


@router.get("/positions")
def positions() -> dict:
    return get_mt5_service().positions()


@router.get("/orders")
def orders() -> dict:
    return get_mt5_service().orders()


@router.get("/history")
def history(days: int = 7) -> dict:
    now = time.time()
    return get_mt5_service().history(now - days * 86400, now)


@router.get("/candles")
def candles(name: str | None = None, timeframe: str = "1h", count: int = 200) -> dict:
    return get_mt5_service().historical_candles(name, timeframe, count)


@router.get("/sync")
def sync() -> dict:
    return get_mt5_service().synchronize()


@router.get("/verify")
def verify() -> dict:
    return get_mt5_service().verify()


class OrderCheckRequest(BaseModel):
    side: str
    volume: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    symbol: str | None = None
    order_type: str = "market"


@router.post("/check-order")
def check_order(req: OrderCheckRequest) -> dict:
    """Dry-run validation only — this NEVER sends an order."""
    svc = get_mt5_service()
    return svc.check_order(
        side=req.side,
        volume=req.volume,
        price=req.price,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        symbol=req.symbol,
        order_type=req.order_type,
    )


@router.get("/execution/status")
def execution_status() -> dict:
    """Report that order execution is disabled (Phase 7 feature)."""
    return {
        "live_execution_enabled": False,
        "implemented": False,
        "message": (
            "Order execution is DISABLED. It is implemented in Phase 7 behind "
            "explicit backend authorization, account verification and a kill switch."
        ),
    }
