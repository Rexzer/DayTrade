"""Trading-mode endpoints.

Exposes the current mode and the availability of each mode. Enforces the
Phase 1 lock: attempts to switch to paper/live return HTTP 409 with an
explanation and never change server state.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.trading_mode import (
    ModeTransitionError,
    TradingMode,
    TradingModeManager,
)

router = APIRouter(prefix="/mode", tags=["mode"])

# A single process-wide manager. It starts in ANALYSIS_ONLY and rejects locks.
_manager = TradingModeManager()


@router.get("")
def get_modes() -> dict:
    return {
        "current": _manager.current.value,
        "live_trading_active": _manager.is_live_trading_active(),
        "modes": _manager.status_dicts(),
    }


@router.post("/{mode}")
def set_mode(mode: str) -> dict:
    try:
        target = TradingMode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown mode '{mode}'.") from exc
    try:
        _manager.set_mode(target)
    except ModeTransitionError as exc:
        # 409 Conflict: the request is well-formed but not permitted in this phase.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"current": _manager.current.value, "modes": _manager.status_dicts()}
