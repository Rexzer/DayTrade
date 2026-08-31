"""Backend live-execution integration layer (Phase 7).

Live execution is user-initiated only and gated by the independent risk engine
and an explicit authorization. The platform never auto-executes trades.
"""

from backend.app.live.service import LiveTradingService, get_live_service

__all__ = ["LiveTradingService", "get_live_service"]
