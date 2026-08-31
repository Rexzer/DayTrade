"""Paper-trading endpoints (Phase 5).

Simulated trading on live data — NO real orders. Includes account/config,
controls (start/pause/resume/stop/reset/close), state, performance, journal.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.paper_trading import get_paper_service

router = APIRouter(prefix="/paper", tags=["paper"])


class PaperStartRequest(BaseModel):
    starting_balance: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_open_positions: int = 1
    max_position_lots: float = 100.0
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0
    trailing_enabled: bool = False
    trailing_distance: float = 0.0
    partial_tp_enabled: bool = False
    partial_tp_fraction: float = 0.5
    min_signal_level: int = 3


@router.get("/state")
def state() -> dict:
    return get_paper_service().state()


@router.get("/performance")
def performance() -> dict:
    return get_paper_service().performance()


@router.get("/trades")
def trades(limit: int = 100) -> dict:
    return get_paper_service().trades(limit)


@router.get("/journal")
def journal(limit: int = 50, kind: str | None = None) -> dict:
    return get_paper_service().journal(limit, kind)


@router.post("/start")
def start(req: PaperStartRequest) -> dict:
    result = get_paper_service().start(req.model_dump())
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/pause")
def pause() -> dict:
    return get_paper_service().pause()


@router.post("/resume")
def resume() -> dict:
    return get_paper_service().resume()


@router.post("/stop")
def stop() -> dict:
    return get_paper_service().stop()


@router.post("/reset")
def reset() -> dict:
    return get_paper_service().reset()


@router.post("/close/{position_id}")
def close_position(position_id: str) -> dict:
    return get_paper_service().close_position(position_id)


@router.post("/close-all")
def close_all() -> dict:
    return get_paper_service().close_all()
