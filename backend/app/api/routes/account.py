"""Account endpoints (Phase 1: no account connected — no fake balances)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/account", tags=["account"])


@router.get("")
def account() -> dict:
    return {
        "connected": False,
        "status": "ACCOUNT NOT CONNECTED",
        "balance": None,
        "equity": None,
        "margin": None,
        "free_margin": None,
        "open_positions": 0,
        "today_pnl": None,
        "daily_drawdown": None,
        "note": "MetaTrader integration is added in Phase 5. No real account is connected.",
    }
