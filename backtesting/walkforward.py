"""Walk-forward analysis (pure Python).

For each fold: optimize parameters on an in-sample window, then evaluate the
chosen parameters on the immediately-following out-of-sample window. The
optimizer NEVER sees data beyond the in-sample window (no look-ahead), and OOS
windows are strictly later in time than their IS window.

``strategy_factory`` is a callable ``params -> Strategy``; ``param_grid`` is a
list of parameter dicts to try.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from backtesting.config import BacktestConfig
from backtesting.engine import Backtester
from backtesting.metrics import compute_metrics


def _metric_value(metrics: dict, name: str) -> float:
    v = metrics.get(name)
    if v is None:
        # Infinite profit factor (no losses) counts as strong; else neutral.
        return 1e9 if (name == "profit_factor" and metrics.get("profit_factor_infinite")) else -1e9
    return float(v)


def walk_forward(
    strategy_factory: Callable[[dict], object],
    param_grid: list[dict],
    base_config: BacktestConfig,
    candles_by_tf: dict[str, list],
    *,
    folds: int = 4,
    metric: str = "profit_factor",
) -> dict:
    prim = candles_by_tf.get(base_config.primary_timeframe, [])
    n = len(prim)
    if n < (folds + 1) * 20 or not param_grid:
        return {"folds": [], "note": "Insufficient data or empty grid for walk-forward."}

    block = n // (folds + 1)
    fold_reports: list[dict] = []
    combined_oos_trades = []

    for k in range(folds):
        is_start_idx = 0
        is_end_idx = (k + 1) * block
        oos_start_idx = is_end_idx
        oos_end_idx = min((k + 2) * block, n)
        if oos_start_idx >= oos_end_idx:
            break

        is_window = (prim[is_start_idx].open_time_epoch, prim[is_end_idx - 1].open_time_epoch)
        oos_window = (prim[oos_start_idx].open_time_epoch, prim[oos_end_idx - 1].open_time_epoch)

        # Optimize on the in-sample window only.
        best_params = None
        best_score = float("-inf")
        for params in param_grid:
            cfg = replace(base_config, start_epoch=is_window[0], end_epoch=is_window[1])
            res = Backtester(strategy_factory(params), cfg).run(candles_by_tf)
            score = _metric_value(res.metrics, metric)
            if score > best_score:
                best_score = score
                best_params = params

        # Evaluate the chosen params on the strictly-later OOS window.
        oos_cfg = replace(base_config, start_epoch=oos_window[0], end_epoch=oos_window[1])
        oos_res = Backtester(strategy_factory(best_params), oos_cfg).run(candles_by_tf)
        combined_oos_trades.extend(oos_res.trades)

        fold_reports.append(
            {
                "fold": k + 1,
                "in_sample_window": is_window,
                "oos_window": oos_window,
                "best_params": best_params,
                "in_sample_metric": round(best_score, 4) if best_score > -1e8 else None,
                "oos_metrics": {
                    "net_profit": oos_res.metrics.get("net_profit"),
                    "profit_factor": oos_res.metrics.get("profit_factor"),
                    "win_rate": oos_res.metrics.get("win_rate"),
                    "num_trades": oos_res.metrics.get("num_trades"),
                    "max_drawdown_pct": oos_res.metrics.get("max_drawdown_pct"),
                },
            }
        )

    aggregate = compute_metrics(combined_oos_trades, [], base_config.starting_capital)
    return {
        "folds": fold_reports,
        "aggregate_oos": {
            "net_profit": aggregate.get("net_profit"),
            "profit_factor": aggregate.get("profit_factor"),
            "win_rate": aggregate.get("win_rate"),
            "num_trades": aggregate.get("num_trades"),
        },
        "note": "Optimization used in-sample windows only; OOS windows are strictly later.",
    }
