"""Monte Carlo analysis of a trade sequence (pure Python).

Bootstraps the realized trades to estimate a RANGE of possible outcomes
(ending equity, maximum drawdown). This illustrates how much of the historical
result may be down to trade ordering/luck. Results are DISTRIBUTIONS, never
predictions — they are not guarantees of anything.
"""

from __future__ import annotations

import random

from backtesting.trade import Trade


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _max_drawdown_pct(equity_path: list[float]) -> float:
    peak = float("-inf")
    max_pct = 0.0
    for eq in equity_path:
        peak = max(peak, eq)
        if peak > 0:
            max_pct = max(max_pct, (peak - eq) / peak)
    return max_pct


def monte_carlo(
    trades: list[Trade],
    starting_capital: float,
    *,
    iterations: int = 1000,
    method: str = "resample",  # "resample" (bootstrap) | "shuffle"
    seed: int = 42,
) -> dict:
    pnls = [t.pnl for t in trades]
    if len(pnls) < 5:
        return {"note": "Too few trades for a meaningful Monte Carlo analysis.", "iterations": 0}

    rng = random.Random(seed)
    ending_equities: list[float] = []
    max_dds: list[float] = []
    ruin_count = 0

    for _ in range(iterations):
        if method == "shuffle":
            seq = pnls[:]
            rng.shuffle(seq)
        else:  # bootstrap resample with replacement
            seq = [rng.choice(pnls) for _ in range(len(pnls))]

        equity = starting_capital
        path = [equity]
        ruined = False
        for pnl in seq:
            equity += pnl
            path.append(equity)
            if equity <= 0:
                ruined = True
                break
        ending_equities.append(equity)
        max_dds.append(_max_drawdown_pct(path))
        if ruined:
            ruin_count += 1

    ending_equities.sort()
    max_dds.sort()
    return {
        "iterations": iterations,
        "method": method,
        "ending_equity": {
            "p5": round(_percentile(ending_equities, 0.05), 2),
            "p50": round(_percentile(ending_equities, 0.50), 2),
            "p95": round(_percentile(ending_equities, 0.95), 2),
        },
        "max_drawdown_pct": {
            "p5": round(_percentile(max_dds, 0.05), 4),
            "p50": round(_percentile(max_dds, 0.50), 4),
            "p95": round(_percentile(max_dds, 0.95), 4),
        },
        "risk_of_ruin_estimate": round(ruin_count / iterations, 4),
        "disclaimer": (
            "Monte Carlo outputs are distributions of historical resampling, " "NOT predictions."
        ),
    }
