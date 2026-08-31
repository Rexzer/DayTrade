"""Modular strategy engine.

Phase 1 defined the plug-in interface and shared vocabulary. Phase 3 adds the
full engine: an indicator library, market-regime detection, five built-in
strategies, a transparent signal-scoring rubric, multi-timeframe analysis,
alert generation, and a user-facing rule builder for custom strategies.

Strategies only classify setups (NO_SETUP / WATCH / POTENTIAL_SETUP /
CONFIRMED_SETUP). They never execute trades — that is a separate concern.
"""

from strategy_engine.alerts import Alert, AlertManager
from strategy_engine.engine import EvaluationResult, SignalEngine
from strategy_engine.mtf import MultiTimeframeAnalyzer
from strategy_engine.regime import RegimeDetector, RegimeResult
from strategy_engine.registry import StrategyRegistry, registry
from strategy_engine.scoring import DEFAULT_WEIGHTS, ScoreCard
from strategy_engine.strategies import build_builtin_strategies
from strategy_engine.strategy import (
    MarketContext,
    MarketRegime,
    Signal,
    SignalLevel,
    Strategy,
    StrategyMetadata,
)


def register_builtin_strategies(target: StrategyRegistry | None = None) -> StrategyRegistry:
    """Register one of each built-in strategy into ``target`` (default global)."""
    reg = target or registry
    existing = set(reg.keys())
    for strat in build_builtin_strategies():
        if strat.key not in existing:
            reg.register(strat)
    return reg


__all__ = [
    "MarketContext",
    "MarketRegime",
    "Signal",
    "SignalLevel",
    "Strategy",
    "StrategyMetadata",
    "StrategyRegistry",
    "registry",
    "DEFAULT_WEIGHTS",
    "ScoreCard",
    "RegimeDetector",
    "RegimeResult",
    "EvaluationResult",
    "SignalEngine",
    "MultiTimeframeAnalyzer",
    "Alert",
    "AlertManager",
    "build_builtin_strategies",
    "register_builtin_strategies",
]
