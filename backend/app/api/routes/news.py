"""News endpoints (Phase 1: no source connected — never fabricate events)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/next")
def next_event() -> dict:
    return {
        "connected": False,
        "next_high_impact_event": None,
        "status": "Data unavailable.",
        "note": "Economic calendar integration is added in a later phase.",
    }
