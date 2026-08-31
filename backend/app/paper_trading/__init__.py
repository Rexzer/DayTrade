"""Backend paper-trading integration layer (Phase 5)."""

from backend.app.paper_trading.service import PaperTradingService, get_paper_service

__all__ = ["PaperTradingService", "get_paper_service"]
