"""Risk engine.

Phase 1 defined risk settings and a position-size calculator. Phase 7 adds the
INDEPENDENT, authoritative :class:`LiveRiskEngine` that gates every prospective
live order: broker-spec position sizing plus all hard limits, spread/news/data
failsafes, and latched daily/weekly/drawdown halts that require a manual reset.

The strategy engine cannot bypass the risk engine — the execution coordinator
must obtain an approving RiskDecision before any order is sent. Nothing here
can place an order.
"""

from risk_engine.engine import RiskCheckResult, RiskEngine
from risk_engine.live_risk import (
    LiveRiskEngine,
    ProspectiveTrade,
    RiskContext,
    RiskDecision,
    RiskState,
    SizingResult,
)
from risk_engine.settings import RISK_PER_TRADE_PRESETS, RiskSettings

__all__ = [
    "RiskSettings",
    "RISK_PER_TRADE_PRESETS",
    "RiskEngine",
    "RiskCheckResult",
    "LiveRiskEngine",
    "ProspectiveTrade",
    "RiskContext",
    "RiskDecision",
    "RiskState",
    "SizingResult",
]
