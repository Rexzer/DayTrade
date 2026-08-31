"""Risk engine.

Phase 1 defines risk settings and a position-size calculator interface. Hard
enforcement (daily loss limits, kill switch, max positions) is wired into the
execution path in Phase 6. Nothing here can place or size a real order in
Phase 1 because no execution engine is active.
"""

from risk_engine.engine import RiskCheckResult, RiskEngine
from risk_engine.settings import RiskSettings

__all__ = ["RiskSettings", "RiskEngine", "RiskCheckResult"]
