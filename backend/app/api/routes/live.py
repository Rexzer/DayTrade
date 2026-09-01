"""Live-trading endpoints (Phase 7).

Live execution is user-initiated and gated by the independent risk engine plus
an explicit authorization (config flag + all confirmations + arm + no kill).
There is NO autonomous execution. A restart disables live trading.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.deps import require_operator
from backend.app.live import get_live_service

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/status")
def status() -> dict:
    return get_live_service().status()


class ConfirmRequest(BaseModel):
    confirmations: dict[str, bool]


@router.post("/confirm")
def confirm(req: ConfirmRequest, _op: str = Depends(require_operator)) -> dict:
    return get_live_service().set_confirmations(req.confirmations)


@router.post("/enable")
def enable(_op: str = Depends(require_operator)) -> dict:
    """Arm live trading. Fails unless every requirement is met."""
    result = get_live_service().enable()
    if result.get("error"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/disable")
def disable() -> dict:
    return get_live_service().disable()


class DryRunRequest(BaseModel):
    enabled: bool


@router.post("/dry-run")
def set_dry_run(req: DryRunRequest, _op: str = Depends(require_operator)) -> dict:
    """Toggle dry-run. ON = validate the full chain but NEVER send an order."""
    return get_live_service().set_dry_run(req.enabled)


class KillRequest(BaseModel):
    cancel_pending: bool = False
    close_positions: bool = False


@router.post("/kill")
def kill(req: KillRequest) -> dict:
    """EMERGENCY STOP — always blocks new trades immediately."""
    return get_live_service().kill(
        cancel_pending=req.cancel_pending, close_positions=req.close_positions
    )


@router.post("/kill/clear")
def clear_kill() -> dict:
    return get_live_service().clear_kill()


class RiskRequest(BaseModel):
    risk_per_trade_pct: float | None = None
    max_daily_loss_pct: float | None = None
    max_weekly_loss_pct: float | None = None
    max_drawdown_pct: float | None = None
    max_open_positions: int | None = None
    max_xauusd_positions: int | None = None
    max_trades_per_day: int | None = None
    max_consecutive_losses: int | None = None
    max_lot_size: float | None = None
    max_spread_points: float | None = None
    news_blackout_before_min: float | None = None
    news_blackout_after_min: float | None = None


@router.post("/risk")
def set_risk(req: RiskRequest, _op: str = Depends(require_operator)) -> dict:
    result = get_live_service().set_risk(req.model_dump(exclude_none=True))
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/risk/reset")
def reset_risk() -> dict:
    return get_live_service().reset_risk_halts()


@router.post("/execute")
def execute(_op: str = Depends(require_operator)) -> dict:
    """USER-INITIATED single execution of the best current confirmed signal."""
    return get_live_service().execute_current_signal()


@router.get("/health")
def strategy_health(limit: int = 500) -> dict:
    """Per-strategy decay monitoring. Degraded strategies are auto-skipped.

    A strategy is only auto-disabled on a meaningful sample with genuinely poor
    expectancy / profit factor or an abnormal losing streak — a low win rate
    alone is just a 'watch'.
    """
    return get_live_service().strategy_health(limit)


@router.get("/auto/intervals")
def auto_intervals() -> dict:
    """Selectable scan intervals + the recommended interval per strategy.

    The recommended interval is each strategy's entry/trigger timeframe:
    scanning faster mostly re-reads the same forming candle, scanning slower
    risks missing the entry window.
    """
    from backend.app.strategy import get_strategy_service
    from execution_engine import interval_options, recommend_for_strategy

    recommendations = []
    for md in get_strategy_service().list_strategies().get("strategies", []):
        rec = recommend_for_strategy(md.get("key"), md.get("suitable_timeframes"))
        recommendations.append(
            {
                "strategy_key": md.get("key"),
                "name": md.get("name"),
                "suitable_timeframes": md.get("suitable_timeframes"),
                **rec,
            }
        )
    return {"intervals": interval_options(), "recommendations": recommendations}


class AutoTradeRequest(BaseModel):
    enabled: bool
    interval_seconds: int | None = None
    strategy_key: str | None = None  # null/omitted = best confirmed across all


@router.post("/auto")
async def set_auto_trade(req: AutoTradeRequest, _op: str = Depends(require_operator)) -> dict:
    """Turn the automatic trading loop on/off.

    When ON, the platform runs the full risk-gated execution pipeline on the
    chosen interval with no per-trade clicks. Requires live trading to already
    be armed/authorized; the kill switch stops it and a restart disables it.
    """
    result = await get_live_service().set_auto_trade(
        enabled=req.enabled,
        interval_seconds=req.interval_seconds,
        strategy_key=req.strategy_key,
    )
    if result.get("error"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/sync")
def sync() -> dict:
    """Reconcile broker positions and journal any closes (incl. manual ones).

    Read-only against the broker; safe to call without operator authorization.
    """
    return get_live_service().sync_positions()


@router.get("/log")
def log(limit: int = 100) -> dict:
    return get_live_service().execution_log(limit)


@router.get("/history")
def history(limit: int = 100) -> dict:
    """Durably-persisted live signals, orders and trades."""
    return get_live_service().history(limit)
