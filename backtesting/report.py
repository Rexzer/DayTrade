"""Strategy validation report + PASS/WARNING/FAILED status (pure Python).

Compares in-sample (training + validation) performance against strictly-later
out-of-sample performance and assigns a robustness rating and a status. A
strategy FAILS if it deteriorates severely out-of-sample or if there is
insufficient evidence (too few OOS trades).

This report never asserts future profitability. It only measures whether the
historical result survives outside the fitting period.
"""

from __future__ import annotations

from backtesting.config import BacktestConfig
from backtesting.splitting import compute_windows, run_window

STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAILED = "FAILED"


def _pf(metrics: dict) -> float:
    """Comparable profit factor: infinite -> large; no data -> 0."""
    if metrics.get("profit_factor_infinite"):
        return 999.0
    pf = metrics.get("profit_factor")
    return float(pf) if pf is not None else 0.0


def build_report(
    strategy,
    candles_by_tf: dict[str, list],
    base_config: BacktestConfig,
    *,
    train: float = 0.5,
    validation: float = 0.25,
    min_oos_trades: int = 5,
    max_acceptable_dd_pct: float = 0.5,
) -> dict:
    windows = compute_windows(
        candles_by_tf, base_config.primary_timeframe, train=train, validation=validation
    )
    in_sample_window = (windows["train"][0], windows["validation"][1])
    oos_window = windows["oos"]

    is_res = run_window(strategy, base_config, candles_by_tf, in_sample_window)
    oos_res = run_window(strategy, base_config, candles_by_tf, oos_window)
    is_m = is_res.metrics
    oos_m = oos_res.metrics

    warnings: list[str] = []
    status = STATUS_PASS

    is_pf = _pf(is_m)
    oos_pf = _pf(oos_m)
    is_net = is_m.get("net_profit", 0.0)
    oos_net = oos_m.get("net_profit", 0.0)
    oos_trades = oos_m.get("num_trades", 0)
    is_trades = is_m.get("num_trades", 0)
    oos_dd = oos_m.get("max_drawdown_pct", 0.0) or 0.0

    # --- Failure conditions --------------------------------------------------
    if is_trades < min_oos_trades or oos_trades < min_oos_trades:
        status = STATUS_FAILED
        warnings.append(
            f"Insufficient evidence: too few trades (in-sample={is_trades}, "
            f"out-of-sample={oos_trades}; need >= {min_oos_trades})."
        )
    if is_net > 0 and oos_net < 0:
        status = STATUS_FAILED
        warnings.append("Profitable in-sample but LOSING out-of-sample (severe deterioration).")
    if oos_dd > max_acceptable_dd_pct:
        status = STATUS_FAILED
        warnings.append(
            f"Out-of-sample max drawdown {oos_dd:.0%} exceeds acceptable "
            f"{max_acceptable_dd_pct:.0%}."
        )

    # --- Warning conditions (only if not already failed) ---------------------
    if status != STATUS_FAILED:
        if is_pf > 0 and oos_pf < is_pf * 0.6:
            status = STATUS_WARNING
            warnings.append("Profit factor dropped >40% out-of-sample.")
        is_wr = is_m.get("win_rate", 0.0)
        oos_wr = oos_m.get("win_rate", 0.0)
        if is_wr > 0 and oos_wr < is_wr * 0.7:
            status = STATUS_WARNING
            warnings.append("Win rate deteriorated notably out-of-sample.")
        if oos_pf < 1.0:
            status = STATUS_WARNING
            warnings.append("Out-of-sample profit factor below 1.0.")

    robustness = {
        STATUS_PASS: "HIGH" if oos_pf >= 1.3 else "MEDIUM",
        STATUS_WARNING: "LOW",
        STATUS_FAILED: "INSUFFICIENT",
    }[status]

    return {
        "strategy_key": strategy.key,
        "strategy_name": getattr(strategy.metadata, "name", strategy.key),
        "status": status,
        "robustness": robustness,
        "in_sample": {
            "window": in_sample_window,
            "profit_factor": is_m.get("profit_factor"),
            "win_rate": is_m.get("win_rate"),
            "net_profit": is_m.get("net_profit"),
            "max_drawdown_pct": is_m.get("max_drawdown_pct"),
            "num_trades": is_trades,
        },
        "out_of_sample": {
            "window": oos_window,
            "profit_factor": oos_m.get("profit_factor"),
            "win_rate": oos_m.get("win_rate"),
            "net_profit": oos_m.get("net_profit"),
            "max_drawdown_pct": oos_m.get("max_drawdown_pct"),
            "num_trades": oos_trades,
        },
        "warnings": warnings,
        "disclaimer": (
            "Validation measures historical robustness only. Past performance "
            "does not guarantee future results."
        ),
    }
