"""Backtesting & validation engine (Phase 4).

A professional, leakage-free backtester with execution costs, full performance
metrics, equity/drawdown curves, train/validation/out-of-sample splitting,
walk-forward analysis, parameter-sensitivity checks, Monte Carlo analysis, and
a PASS/WARNING/FAILED strategy report.

Purpose: determine whether a strategy's historical performance survives outside
its fitting period — NOT to guarantee future profitability. No strategy is ever
presented as guaranteed to make money.
"""

from backtesting.config import BacktestConfig, TradingSession
from backtesting.engine import Backtester, BacktestResult
from backtesting.execution import CostModel, position_lots
from backtesting.metrics import compute_metrics, drawdown_curve, max_drawdown
from backtesting.montecarlo import monte_carlo
from backtesting.report import (
    STATUS_FAILED,
    STATUS_PASS,
    STATUS_WARNING,
    build_report,
)
from backtesting.sensitivity import parameter_sensitivity
from backtesting.splitting import compute_windows, run_all_segments, run_window
from backtesting.trade import Trade
from backtesting.walkforward import walk_forward

IMPLEMENTED = True

__all__ = [
    "BacktestConfig",
    "TradingSession",
    "Backtester",
    "BacktestResult",
    "CostModel",
    "position_lots",
    "compute_metrics",
    "drawdown_curve",
    "max_drawdown",
    "monte_carlo",
    "build_report",
    "STATUS_PASS",
    "STATUS_WARNING",
    "STATUS_FAILED",
    "parameter_sensitivity",
    "compute_windows",
    "run_all_segments",
    "run_window",
    "walk_forward",
    "Trade",
]
