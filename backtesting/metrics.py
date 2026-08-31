"""Backtest performance metrics (pure Python, reference-consistent).

All metrics are computed deterministically from the completed trades and the
equity curve. Sharpe/Sortino are computed from per-trade returns and reported
UN-annualized (labelled as such) to avoid implying a false annualization.
"""

from __future__ import annotations

import math

from backtesting.trade import Trade


def max_drawdown(equity_values: list[float]) -> tuple[float, float]:
    """Return (max_drawdown_abs, max_drawdown_pct) from an equity series."""
    peak = float("-inf")
    max_abs = 0.0
    max_pct = 0.0
    for eq in equity_values:
        peak = max(peak, eq)
        dd = peak - eq
        if dd > max_abs:
            max_abs = dd
        if peak > 0 and (dd / peak) > max_pct:
            max_pct = dd / peak
    return round(max_abs, 2), round(max_pct, 4)


def drawdown_curve(equity_curve: list[tuple[float, float]]) -> list[dict]:
    """Return a per-point drawdown series ({time, drawdown, drawdown_pct})."""
    out = []
    peak = float("-inf")
    for t, eq in equity_curve:
        peak = max(peak, eq)
        dd = peak - eq
        out.append(
            {
                "time": t,
                "drawdown": round(dd, 2),
                "drawdown_pct": round((dd / peak) if peak > 0 else 0.0, 4),
            }
        )
    return out


def _consecutive(trades: list[Trade]) -> tuple[int, int]:
    max_win_streak = max_loss_streak = 0
    win_streak = loss_streak = 0
    for t in trades:
        if t.is_win:
            win_streak += 1
            loss_streak = 0
        else:
            loss_streak += 1
            win_streak = 0
        max_win_streak = max(max_win_streak, win_streak)
        max_loss_streak = max(max_loss_streak, loss_streak)
    return max_win_streak, max_loss_streak


def _sharpe(returns: list[float], risk_free: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - risk_free for r in returns]
    mean = sum(excess) / len(excess)
    var = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return round(mean / sd, 4)


def _sortino(returns: list[float], risk_free: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    excess = [r - risk_free for r in returns]
    mean = sum(excess) / len(excess)
    downside = [min(0.0, r) for r in excess]
    dd_var = sum(d**2 for d in downside) / len(excess)
    dd = math.sqrt(dd_var)
    if dd == 0:
        return None
    return round(mean / dd, 4)


def compute_metrics(
    trades: list[Trade],
    equity_curve: list[tuple[float, float]],
    starting_capital: float,
    *,
    risk_free_rate: float = 0.0,
) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if not t.is_win]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)  # positive magnitude
    net_profit = sum(t.pnl for t in trades)

    equity_values = [e for _, e in equity_curve] or [starting_capital]
    ending = equity_values[-1]
    mdd_abs, mdd_pct = max_drawdown(equity_values)
    win_streak, loss_streak = _consecutive(trades)
    returns = [t.return_pct for t in trades]

    profit_factor = (
        (gross_profit / gross_loss)
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

    return {
        "num_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "loss_rate": round(len(losses) / n, 4) if n else 0.0,
        "net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": (round(profit_factor, 4) if profit_factor != float("inf") else None),
        "profit_factor_infinite": profit_factor == float("inf"),
        "expectancy": round(net_profit / n, 2) if n else 0.0,
        "average_trade": round(net_profit / n, 2) if n else 0.0,
        "average_win": round(gross_profit / len(wins), 2) if wins else 0.0,
        "average_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "largest_win": round(max((t.pnl for t in wins), default=0.0), 2),
        "largest_loss": round(min((t.pnl for t in losses), default=0.0), 2),
        "max_consecutive_wins": win_streak,
        "max_consecutive_losses": loss_streak,
        "max_drawdown": mdd_abs,
        "max_drawdown_pct": mdd_pct,
        "return_pct": (
            round((ending - starting_capital) / starting_capital, 4) if starting_capital else 0.0
        ),
        "ending_capital": round(ending, 2),
        "sharpe_ratio": _sharpe(returns, risk_free_rate),
        "sortino_ratio": _sortino(returns, risk_free_rate),
        "sharpe_note": "Per-trade, un-annualized.",
        "disclaimer": "Historical metrics do not guarantee future results.",
    }
