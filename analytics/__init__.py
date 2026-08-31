"""Advanced analytics (Phase 8, pure Python).

Trade-journal intelligence (neutral behavioural observations), performance
breakdowns across many dimensions, strategy comparison, signal-transition
history, and a system-health aggregator. All computed only from data the
platform actually has — nothing is invented, and no result is presented as a
guarantee of future performance.
"""

from analytics.comparison import build_strategy_comparison
from analytics.health import HealthStatus, SystemHealth
from analytics.journal_intelligence import JournalAnalyzer, Observation
from analytics.performance import breakdown, metrics, standard_breakdowns
from analytics.signal_history import SignalHistory

__all__ = [
    "JournalAnalyzer",
    "Observation",
    "breakdown",
    "metrics",
    "standard_breakdowns",
    "build_strategy_comparison",
    "SignalHistory",
    "HealthStatus",
    "SystemHealth",
]
