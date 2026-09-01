"""Strategy Lab endpoints — champion/challenger promotion funnel.

New strategies advance only by clearing hard, out-of-sample gates
(backtest -> walk-forward -> shadow paper) and a final human promotion. No
candidate can reach live capital automatically.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api.deps import require_operator
from backend.app.strategy_lab import get_lab_service

router = APIRouter(prefix="/lab", tags=["strategy_lab"])


@router.get("/funnel")
def funnel() -> dict:
    """Current candidates grouped by lifecycle stage + the active gates."""
    return get_lab_service().funnel()


class RegisterRequest(BaseModel):
    key: str
    name: str
    source: str = "human"  # human | param_sweep | recombination | external


@router.post("/candidates")
def register(req: RegisterRequest) -> dict:
    return get_lab_service().register(req.key, req.name, req.source)


class MetricsRequest(BaseModel):
    metrics: dict


@router.post("/candidates/{key}/backtest")
def record_backtest(key: str, req: MetricsRequest) -> dict:
    return get_lab_service().record_backtest(key, req.metrics)


@router.post("/candidates/{key}/walk-forward")
def record_walk_forward(key: str, req: MetricsRequest) -> dict:
    return get_lab_service().record_walk_forward(key, req.metrics)


class ShadowRequest(BaseModel):
    metrics: dict
    champion_metrics: dict | None = None


@router.post("/candidates/{key}/shadow")
def record_shadow(key: str, req: ShadowRequest) -> dict:
    return get_lab_service().record_shadow(key, req.metrics, req.champion_metrics)


@router.post("/candidates/{key}/promote")
def promote(key: str, _op: str = Depends(require_operator)) -> dict:
    """Promote an APPROVED candidate to LIVE. Operator-authorized (touches capital)."""
    return get_lab_service().promote(key)


class RetireRequest(BaseModel):
    reason: str = "Retired by operator."


@router.post("/candidates/{key}/retire")
def retire(key: str, req: RetireRequest) -> dict:
    return get_lab_service().retire(key, req.reason)
