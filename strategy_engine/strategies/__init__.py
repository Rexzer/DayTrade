"""Built-in strategy implementations.

Five families ship in Phase 3. None is claimed to be profitable — each is a
hypothesis that must be backtested and validated (Phase 4+). Strategies only
produce explainable signals (NO_SETUP / WATCH / POTENTIAL_SETUP /
CONFIRMED_SETUP); they can never place an order.
"""

from strategy_engine.strategies.breakout_retest import BreakoutRetestStrategy
from strategy_engine.strategies.ema_pullback import EmaPullbackStrategy
from strategy_engine.strategies.mtf_confluence import MultiTimeframeConfluenceStrategy
from strategy_engine.strategies.sr_reversal import SupportResistanceReversalStrategy
from strategy_engine.strategies.trend_following import TrendFollowingStrategy

BUILTIN_STRATEGY_CLASSES = [
    TrendFollowingStrategy,
    EmaPullbackStrategy,
    BreakoutRetestStrategy,
    SupportResistanceReversalStrategy,
    MultiTimeframeConfluenceStrategy,
]


def build_builtin_strategies() -> list:
    """Instantiate one of each built-in strategy."""
    return [cls() for cls in BUILTIN_STRATEGY_CLASSES]


__all__ = [
    "TrendFollowingStrategy",
    "EmaPullbackStrategy",
    "BreakoutRetestStrategy",
    "SupportResistanceReversalStrategy",
    "MultiTimeframeConfluenceStrategy",
    "BUILTIN_STRATEGY_CLASSES",
    "build_builtin_strategies",
]
