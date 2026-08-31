"""Performance metrics + breakdowns across dimensions (pure Python).

Operates on trade records (dicts with at least ``pnl``; optionally
``return_pct``, ``strategy_key``, ``direction``, ``exit_reason``, ``regime``,
``opened_epoch``, ``closed_epoch``). Reproducible and dependency-free.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone


def metrics(trades: list[dict]) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) <= 0]
    gross_profit = sum(t.get("pnl", 0) for t in wins)
    gross_loss = -sum(t.get("pnl", 0) for t in losses)
    net = sum(t.get("pnl", 0) for t in trades)
    pf = (gross_profit / gross_loss) if gross_loss > 0 else None
    holds = [
        (t["closed_epoch"] - t["opened_epoch"])
        for t in trades
        if t.get("closed_epoch") and t.get("opened_epoch")
    ]
    return {
        "num_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "net_pnl": round(net, 2),
        "profit_factor": round(pf, 4) if pf is not None else None,
        "profit_factor_infinite": gross_loss == 0 and gross_profit > 0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "average_win": round(gross_profit / len(wins), 2) if wins else 0.0,
        "average_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "average_holding_seconds": round(sum(holds) / len(holds), 1) if holds else None,
    }


def breakdown(trades: list[dict], key_fn: Callable[[dict], str], *, label: str) -> dict:
    """Group trades by ``key_fn`` and compute metrics per group."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        groups.setdefault(str(key_fn(t)), []).append(t)
    rows = []
    for key, ts in groups.items():
        row = {"group": key}
        row.update(metrics(ts))
        rows.append(row)
    rows.sort(key=lambda r: r["net_pnl"], reverse=True)
    return {"dimension": label, "rows": rows}


def _session(epoch) -> str:
    if not epoch:
        return "unknown"
    h = datetime.fromtimestamp(epoch, tz=timezone.utc).hour
    # Rough FX sessions in UTC.
    if 0 <= h < 7:
        return "asian"
    if 7 <= h < 12:
        return "london"
    if 12 <= h < 16:
        return "london_ny_overlap"
    if 16 <= h < 21:
        return "new_york"
    return "after_hours"


def _weekday(epoch) -> str:
    if not epoch:
        return "unknown"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%A")


def _month(epoch) -> str:
    if not epoch:
        return "unknown"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m")


def standard_breakdowns(trades: list[dict]) -> dict:
    """Return the standard set of breakdowns required by the dashboard."""
    return {
        "overall": metrics(trades),
        "by_strategy": breakdown(
            trades, lambda t: t.get("strategy_name", t.get("strategy_key", "?")), label="strategy"
        ),
        "by_direction": breakdown(trades, lambda t: t.get("direction", "?"), label="direction"),
        "by_exit_reason": breakdown(
            trades, lambda t: t.get("exit_reason", "?"), label="exit_reason"
        ),
        "by_regime": breakdown(trades, lambda t: t.get("regime") or "unknown", label="regime"),
        "by_timeframe": breakdown(
            trades, lambda t: t.get("timeframe") or "unknown", label="timeframe"
        ),
        "by_session": breakdown(trades, lambda t: _session(t.get("opened_epoch")), label="session"),
        "by_weekday": breakdown(trades, lambda t: _weekday(t.get("opened_epoch")), label="weekday"),
        "by_month": breakdown(trades, lambda t: _month(t.get("opened_epoch")), label="month"),
    }
