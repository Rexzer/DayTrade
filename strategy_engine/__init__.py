"""Modular strategy engine.

Phase 1 defines the plug-in interface and shared vocabulary (signal levels,
market regimes) that every strategy will implement in Phase 2. No concrete
strategies are shipped yet — the registry starts empty so the UI honestly
reports "No strategies connected".
"""

from strategy_engine.registry import StrategyRegistry, registry
from strategy_engine.strategy import (
    MarketRegime,
    Signal,
    SignalLevel,
    Strategy,
    StrategyMetadata,
)

__all__ = [
    "MarketRegime",
    "Signal",
    "SignalLevel",
    "Strategy",
    "StrategyMetadata",
    "StrategyRegistry",
    "registry",
]
