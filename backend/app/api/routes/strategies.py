"""Strategy & signal endpoints (Phase 3).

Exposes the strategy library, live signals, multi-timeframe analysis, alerts,
and CRUD for user-created (rule-based) strategies. Analysis only — no endpoint
here can place an order.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.strategy_repository import UserStrategyRepository
from backend.app.strategy import get_strategy_service
from strategy_engine.rules import validate_rule_dict

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
def list_strategies() -> dict:
    return get_strategy_service().list_strategies()


@router.get("/signals")
def signals() -> dict:
    return get_strategy_service().signals()


@router.get("/analysis/mtf")
def multi_timeframe() -> dict:
    return get_strategy_service().analyze_mtf()


@router.get("/alerts")
def alerts(limit: int = 20) -> dict:
    return {"alerts": get_strategy_service().recent_alerts(limit)}


@router.get("/custom")
def list_custom() -> dict:
    return {"custom": get_strategy_service().custom_definitions()}


@router.post("/custom", status_code=201)
def create_custom(definition: dict, db: Session = Depends(get_db)) -> dict:
    """Create a user strategy from a rule definition (validated, then saved)."""
    errors = validate_rule_dict(definition)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    svc = get_strategy_service()
    add_errors = svc.add_custom(definition)
    if add_errors:
        raise HTTPException(status_code=422, detail={"errors": add_errors})
    # Best-effort persistence (analysis still works if the DB is unavailable).
    try:
        repo = UserStrategyRepository(db)
        if repo.get(definition["key"]) is None:
            repo.create(definition)
    except Exception:  # noqa: BLE001
        pass
    return {"created": definition["key"], "custom": svc.custom_definitions()}


@router.delete("/custom/{key}")
def delete_custom(key: str, db: Session = Depends(get_db)) -> dict:
    svc = get_strategy_service()
    removed = svc.remove_custom(key)
    try:
        UserStrategyRepository(db).delete(key)
    except Exception:  # noqa: BLE001
        pass
    if not removed:
        raise HTTPException(status_code=404, detail=f"Custom strategy '{key}' not found.")
    return {"deleted": key}


@router.get("/{key}")
def strategy_detail(key: str) -> dict:
    detail = get_strategy_service().detail(key)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{key}' not found.")
    return detail
