"""Parameter-sensitivity analysis (pure Python).

Varies a single parameter across nearby values and measures how stable a chosen
metric is. A strategy whose performance collapses or flips sign for small
parameter changes is flagged FRAGILE — a strong overfitting warning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from backtesting.config import BacktestConfig
from backtesting.engine import Backtester


def _metric(metrics: dict, name: str) -> float | None:
    if name == "profit_factor" and metrics.get("profit_factor_infinite"):
        return None  # treat unbounded PF as "not comparable" here
    return metrics.get(name)


def parameter_sensitivity(
    strategy_factory: Callable[[dict], object],
    base_params: dict,
    param_name: str,
    values: list,
    base_config: BacktestConfig,
    candles_by_tf: dict[str, list],
    *,
    metric: str = "net_profit",
    window: tuple[float, float] | None = None,
) -> dict:
    results = []
    metric_values: list[float] = []
    for v in values:
        params = dict(base_params)
        params[param_name] = v
        cfg = base_config
        if window is not None:
            cfg = replace(base_config, start_epoch=window[0], end_epoch=window[1])
        res = Backtester(strategy_factory(params), cfg).run(candles_by_tf)
        m = _metric(res.metrics, metric)
        results.append(
            {
                "value": v,
                "metric": m,
                "net_profit": res.metrics.get("net_profit"),
                "profit_factor": res.metrics.get("profit_factor"),
                "num_trades": res.metrics.get("num_trades"),
            }
        )
        if m is not None:
            metric_values.append(float(m))

    fragile = False
    reasons: list[str] = []
    if len(metric_values) < 2:
        fragile = True
        reasons.append("Too few comparable results to assess stability.")
    else:
        mean = sum(metric_values) / len(metric_values)
        var = sum((x - mean) ** 2 for x in metric_values) / len(metric_values)
        sd = var**0.5
        cov = (sd / abs(mean)) if mean != 0 else float("inf")
        sign_flip = any(a * b < 0 for a, b in zip(metric_values, metric_values[1:], strict=False))
        if sign_flip:
            fragile = True
            reasons.append("Metric changes sign across nearby parameter values.")
        if cov > 0.75:
            fragile = True
            reasons.append(f"High variability across parameters (CoV={cov:.2f}).")

    return {
        "param_name": param_name,
        "metric": metric,
        "results": results,
        "fragile": fragile,
        "reasons": reasons,
    }
