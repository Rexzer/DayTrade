"""Per-strategy paper-trading performance analytics (pure Python)."""

from __future__ import annotations

from paper_trading.models import PaperTradeRecord


def _max_drawdown_pct(equity_path: list[float]) -> float:
    peak = float("-inf")
    max_pct = 0.0
    for eq in equity_path:
        peak = max(peak, eq)
        if peak > 0:
            max_pct = max(max_pct, (peak - eq) / peak)
    return round(max_pct, 4)


def _metrics(trades: list[PaperTradeRecord], starting_balance: float) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if not t.is_win]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)
    net = sum(t.pnl for t in trades)

    equity = starting_balance
    path = [equity]
    for t in trades:
        equity += t.pnl
        path.append(equity)

    pf = (gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit == 0 else None)
    return {
        "num_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "net_pnl": round(net, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(pf, 4) if pf is not None else None,
        "profit_factor_infinite": gross_loss == 0 and gross_profit > 0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "average_win": round(gross_profit / len(wins), 2) if wins else 0.0,
        "average_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "largest_win": round(max((t.pnl for t in wins), default=0.0), 2),
        "largest_loss": round(min((t.pnl for t in losses), default=0.0), 2),
        "max_drawdown_pct": _max_drawdown_pct(path),
    }


def overall_performance(trades: list[PaperTradeRecord], starting_balance: float) -> dict:
    return _metrics(trades, starting_balance)


def performance_by_strategy(trades: list[PaperTradeRecord], starting_balance: float) -> list[dict]:
    """Return per-strategy metrics so strategies can be compared side by side."""
    by_key: dict[str, list[PaperTradeRecord]] = {}
    names: dict[str, str] = {}
    for t in trades:
        by_key.setdefault(t.strategy_key, []).append(t)
        names[t.strategy_key] = t.strategy_name
    rows = []
    for key, ts in by_key.items():
        row = {"strategy_key": key, "strategy_name": names.get(key, key)}
        row.update(_metrics(ts, starting_balance))
        rows.append(row)
    # Best net P&L first.
    rows.sort(key=lambda r: r["net_pnl"], reverse=True)
    return rows
