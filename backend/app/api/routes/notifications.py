"""Notification endpoints (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.notifications import get_notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def get_config() -> dict:
    return get_notification_service().get_config()


class UpdateRequest(BaseModel):
    channels: dict[str, bool] | None = None
    events: dict[str, bool] | None = None


@router.post("")
def update_config(req: UpdateRequest) -> dict:
    return get_notification_service().update_config(channels=req.channels, events=req.events)


@router.get("/recent")
def recent(limit: int = 50) -> dict:
    return get_notification_service().recent(limit)


@router.post("/test")
def test() -> dict:
    return get_notification_service().test()
