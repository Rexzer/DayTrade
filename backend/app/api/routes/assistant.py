"""AI assistant endpoints (Phase 8). Data-grounded; never invents data."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.assistant import get_assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(req: AskRequest) -> dict:
    return get_assistant_service().ask(req.question)


@router.get("/examples")
def examples() -> dict:
    return get_assistant_service().examples()
