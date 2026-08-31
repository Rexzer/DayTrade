"""Analytics endpoints (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.analytics import get_analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/performance")
def performance() -> dict:
    return get_analytics_service().performance()


@router.get("/journal")
def journal() -> dict:
    return get_analytics_service().journal()


@router.get("/comparison")
def comparison() -> dict:
    return get_analytics_service().comparison()


@router.get("/signals/history")
def signal_history(limit: int = 100, transition: str | None = None) -> dict:
    return get_analytics_service().signal_history_recent(limit=limit, transition=transition)
