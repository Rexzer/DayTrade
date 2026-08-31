"""Health / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "phase": 1,
        "mode": "analysis_only",
        "live_trading_implemented": False,
    }


@router.get("/health/db")
def health_db() -> dict:
    """Report database reachability without leaking connection details."""
    from sqlalchemy import text

    from backend.app.db.session import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:  # noqa: BLE001 - do not leak driver internals to clients
        return {"database": "disconnected"}
