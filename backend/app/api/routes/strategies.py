"""Strategy endpoints (Phase 1: registry is empty)."""

from __future__ import annotations

from fastapi import APIRouter

from strategy_engine import registry

router = APIRouter(prefix="/strategies", tags=["strategies"])

# Families that will be added in Phase 2, shown so the UI can preview them.
_PLANNED_FAMILIES = [
    {"key": "trend_following", "name": "Trend Following"},
    {"key": "ema_pullback", "name": "EMA Pullback"},
    {"key": "breakout_retest", "name": "Breakout + Retest"},
    {"key": "sr_reversal", "name": "Support/Resistance Reversal"},
    {"key": "rsi_divergence", "name": "RSI / Momentum Divergence"},
    {"key": "volatility_breakout", "name": "Volatility Breakout"},
    {"key": "vwap_mean_reversion", "name": "VWAP / Mean Reversion"},
    {"key": "mtf_confluence", "name": "Multi-Timeframe Confluence"},
]


@router.get("")
def list_strategies() -> dict:
    active = [s.metadata.to_dict() for s in registry.all()]
    return {
        "connected": not registry.is_empty(),
        "active": active,
        "planned": _PLANNED_FAMILIES,
        "note": "No strategies connected in Phase 1. Built-in families arrive in Phase 2.",
    }
