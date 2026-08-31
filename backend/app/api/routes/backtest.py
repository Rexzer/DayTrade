"""Backtesting & validation endpoints (Phase 4).

Analysis only — running a backtest can never place an order. Results are
historical measurements, never guarantees of future performance.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.backtesting import get_backtest_service

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy_key: str
    starting_capital: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    primary_timeframe: str = "1h"
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0
    min_signal_level: int = 3
    allow_long: bool = True
    allow_short: bool = True

    def overrides(self) -> dict:
        d = self.model_dump()
        d.pop("strategy_key", None)
        return d


@router.get("/strategies")
def strategies() -> dict:
    return get_backtest_service().available_strategies()


@router.post("/run")
def run(req: BacktestRequest) -> dict:
    return get_backtest_service().run(req.strategy_key, req.overrides())


@router.post("/report")
def report(req: BacktestRequest) -> dict:
    return get_backtest_service().report(req.strategy_key, req.overrides())
