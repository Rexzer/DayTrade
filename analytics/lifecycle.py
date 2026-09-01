"""Strategy lifecycle / decay monitoring (pure Python).

Watches each strategy's *recent* realized performance and classifies its
health, so a strategy whose edge has decayed can be pulled from automatic
trading before it does more damage. Dependency-free and reproducible; operates
on the same trade dicts as ``analytics.performance``.

Honesty guardrails baked in:
    * Never judge on a tiny sample — below ``min_trades`` the verdict is
      ``insufficient_data`` and the strategy is NOT disabled.
    * A low win rate ALONE is not decay (many sound systems win <40% of the
      time but stay profitable) — it only raises a "watch", not a disable.
    * Auto-disable requires a genuinely poor expectancy / profit factor over a
      meaningful window, or an abnormal losing streak.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from analytics.performance import metrics

# Health status values, worst -> best for reference.
STATUS_DEGRADED = "degraded"  # auto-disable candidate
STATUS_WATCH = "watch"  # keep trading, but flag it
STATUS_HEALTHY = "healthy"
STATUS_INSUFFICIENT = "insufficient_data"  # too few trades to judge


@dataclass
class HealthThresholds:
    """Tunable decay thresholds. Defaults are deliberately conservative."""

    min_trades: int = 20  # don't judge below this sample size
    window: int = 50  # only the most recent N trades count
    min_expectancy: float = 0.0  # avg P&L per trade must stay above this
    min_profit_factor: float = 1.0  # gross win / gross loss must stay above this
    min_win_rate: float = 0.35  # below this -> "watch" (not auto-disable)
    max_consecutive_losses: int = 6  # trailing losing streak that trips a disable

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StrategyHealth:
    strategy_key: str
    status: str
    sample_size: int
    consecutive_losses: int
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def should_disable(self) -> bool:
        return self.status == STATUS_DEGRADED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["should_disable"] = self.should_disable
        return d


def _trailing_losing_streak(pnls: list[float]) -> int:
    """Count consecutive losing/break-even trades at the END of the sequence."""
    streak = 0
    for pnl in reversed(pnls):
        if pnl <= 0:
            streak += 1
        else:
            break
    return streak


def evaluate_health(
    trades: list[dict],
    thresholds: HealthThresholds | None = None,
    *,
    strategy_key: str = "?",
) -> StrategyHealth:
    """Classify one strategy's health from its (chronological) trade list.

    ``trades`` must be ordered oldest -> newest and each carry a ``pnl``.
    """
    th = thresholds or HealthThresholds()
    window_trades = trades[-th.window :] if th.window > 0 else list(trades)
    n = len(window_trades)
    pnls = [float(t.get("pnl", 0) or 0) for t in window_trades]
    consec = _trailing_losing_streak(pnls)
    m = metrics(window_trades)

    if n < th.min_trades:
        return StrategyHealth(
            strategy_key=strategy_key,
            status=STATUS_INSUFFICIENT,
            sample_size=n,
            consecutive_losses=consec,
            reasons=[f"Only {n} trades (need {th.min_trades} to judge)."],
            metrics=m,
        )

    reasons: list[str] = []
    expectancy = m.get("expectancy", 0.0)
    pf = m.get("profit_factor")
    win_rate = m.get("win_rate", 0.0)

    if expectancy <= th.min_expectancy:
        reasons.append(f"Expectancy {expectancy} <= {th.min_expectancy} over last {n} trades.")
    if pf is not None and pf < th.min_profit_factor:
        reasons.append(f"Profit factor {pf} < {th.min_profit_factor}.")
    if consec >= th.max_consecutive_losses:
        reasons.append(f"{consec} consecutive losing trades (>= {th.max_consecutive_losses}).")

    if reasons:
        status = STATUS_DEGRADED
    elif win_rate < th.min_win_rate:
        status = STATUS_WATCH
        reasons.append(
            f"Low win rate {win_rate} (< {th.min_win_rate}) — still profitable, watching."
        )
    else:
        status = STATUS_HEALTHY

    return StrategyHealth(
        strategy_key=strategy_key,
        status=status,
        sample_size=n,
        consecutive_losses=consec,
        reasons=reasons,
        metrics=m,
    )


def monitor_strategies(
    trades: list[dict], thresholds: HealthThresholds | None = None
) -> dict[str, dict]:
    """Group trades by ``strategy_key`` and evaluate each strategy's health.

    Trades with no ``strategy_key`` are grouped under ``"unattributed"`` (e.g.
    live closes not yet linked to the strategy that opened them).
    """
    th = thresholds or HealthThresholds()
    groups: dict[str, list[dict]] = {}
    for t in trades:
        key = t.get("strategy_key") or "unattributed"
        groups.setdefault(key, []).append(t)
    return {key: evaluate_health(ts, th, strategy_key=key).to_dict() for key, ts in groups.items()}


def disabled_keys(monitor_result: dict[str, dict]) -> list[str]:
    """Strategy keys whose health says they should be auto-disabled."""
    return [
        key
        for key, health in monitor_result.items()
        if health.get("should_disable") and key != "unattributed"
    ]
