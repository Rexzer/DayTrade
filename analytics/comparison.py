"""Strategy comparison table (pure Python).

Merges results from different validation/trading contexts (out-of-sample
backtest, paper trading, live) per strategy into a single comparison. Missing
cells are reported as ``None`` — never fabricated.
"""

from __future__ import annotations


def build_strategy_comparison(
    strategies: list[dict],
    *,
    oos_by_key: dict[str, dict] | None = None,
    paper_by_key: dict[str, dict] | None = None,
    live_by_key: dict[str, dict] | None = None,
) -> list[dict]:
    """Return one comparison row per strategy.

    Args:
        strategies: [{key, name}, ...] the strategies to compare.
        oos_by_key/paper_by_key/live_by_key: metric dicts keyed by strategy key
            (each may contain num_trades/win_rate/profit_factor/net_pnl/...).
    """
    oos_by_key = oos_by_key or {}
    paper_by_key = paper_by_key or {}
    live_by_key = live_by_key or {}
    rows = []
    for s in strategies:
        key = s.get("key")
        rows.append(
            {
                "strategy_key": key,
                "strategy_name": s.get("name", key),
                "backtest_oos": oos_by_key.get(key),
                "paper": paper_by_key.get(key),
                "live": live_by_key.get(key),
            }
        )
    return rows
