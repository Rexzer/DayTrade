"""System-health endpoint (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.health import get_health_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def system_health() -> dict:
    return get_health_service().snapshot()
