"""Backend MetaTrader 5 integration layer (Phase 6, read-only)."""

from backend.app.mt5.service import MT5Service, get_mt5_service

__all__ = ["MT5Service", "get_mt5_service"]
