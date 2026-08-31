"""Settings endpoints.

Returns the settings sections the UI renders. Trading settings explicitly
report that live trading is disabled. No secret values are ever returned.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def settings() -> dict:
    s = get_settings()
    return {
        "sections": [
            "general",
            "market_data",
            "strategies",
            "risk_management",
            "notifications",
            "trading",
            "security",
        ],
        "general": {"app_name": s.app_name, "env": s.app_env, "phase": 1},
        "trading": {
            "mode": "analysis_only",
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "message": "LIVE TRADING DISABLED",
        },
        "market_data": {"provider": "none", "connected": False},
        "notifications": {
            "channels": ["browser", "desktop", "sound", "email", "telegram", "discord"],
            "configured": [],
        },
        "security": {"secret_key_set": bool(s.secret_key), "jwt_algorithm": s.jwt_algorithm},
    }
