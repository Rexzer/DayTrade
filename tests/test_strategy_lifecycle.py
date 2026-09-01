"""Tests: strategy decay monitoring (pure lifecycle evaluator)."""

from analytics.lifecycle import (
    STATUS_DEGRADED,
    STATUS_HEALTHY,
    STATUS_INSUFFICIENT,
    STATUS_WATCH,
    HealthThresholds,
    disabled_keys,
    evaluate_health,
    monitor_strategies,
)


def _trades(pnls, strategy_key="s"):
    return [{"pnl": p, "strategy_key": strategy_key} for p in pnls]


def test_insufficient_sample_is_never_disabled():
    th = HealthThresholds(min_trades=20)
    h = evaluate_health(_trades([-5] * 5), th, strategy_key="s")
    assert h.status == STATUS_INSUFFICIENT
    assert h.should_disable is False  # too few trades to judge


def test_profitable_strategy_is_healthy():
    th = HealthThresholds(min_trades=10)
    # 7 wins of +10, 3 losses of -5 => positive expectancy, pf = 70/15 > 1
    h = evaluate_health(_trades([10, -5, 10, 10, -5, 10, 10, -5, 10, 10]), th)
    assert h.status == STATUS_HEALTHY
    assert h.should_disable is False


def test_negative_expectancy_degrades_and_disables():
    th = HealthThresholds(min_trades=10)
    # Net losing set over the window.
    h = evaluate_health(_trades([-10, 5, -10, -10, 5, -10, -10, 5, -10, -10]), th)
    assert h.status == STATUS_DEGRADED
    assert h.should_disable is True
    assert any("Expectancy" in r or "Profit factor" in r for r in h.reasons)


def test_losing_streak_trips_disable_even_if_expectancy_ok():
    # Many early wins keep expectancy positive, but a long tail of losses.
    th = HealthThresholds(min_trades=10, max_consecutive_losses=5, min_expectancy=-999)
    pnls = [100, 100, 100, 100, 100, -5, -5, -5, -5, -5, -5]
    h = evaluate_health(_trades(pnls), th)
    assert h.consecutive_losses == 6
    assert h.status == STATUS_DEGRADED
    assert any("consecutive" in r for r in h.reasons)


def test_low_win_rate_but_profitable_is_only_watch():
    th = HealthThresholds(min_trades=10, min_win_rate=0.5)
    # 3 big wins, 7 small losses: win rate 0.3 but expectancy positive, pf > 1.
    pnls = [100, -5, -5, 100, -5, -5, 100, -5, -5, -5]
    h = evaluate_health(_trades(pnls), th)
    assert h.metrics["win_rate"] < 0.5
    assert h.status == STATUS_WATCH  # not disabled — still has an edge
    assert h.should_disable is False


def test_window_limits_to_recent_trades():
    th = HealthThresholds(min_trades=5, window=5, min_expectancy=0.0)
    # Old trades terrible, recent 5 all winners -> judged healthy on the window.
    pnls = [-100, -100, -100, -100, -100, 10, 10, 10, 10, 10]
    h = evaluate_health(_trades(pnls), th)
    assert h.sample_size == 5
    assert h.status == STATUS_HEALTHY


def test_monitor_groups_by_strategy_and_reports_disabled():
    th = HealthThresholds(min_trades=10)
    good = _trades([10, -5, 10, 10, -5, 10, 10, -5, 10, 10], strategy_key="good")
    bad = _trades([-10, 5, -10, -10, 5, -10, -10, 5, -10, -10], strategy_key="bad")
    result = monitor_strategies(good + bad, th)
    assert result["good"]["status"] == STATUS_HEALTHY
    assert result["bad"]["status"] == STATUS_DEGRADED
    assert disabled_keys(result) == ["bad"]


def test_unattributed_trades_never_auto_disable():
    th = HealthThresholds(min_trades=5)
    result = monitor_strategies(_trades([-10] * 10, strategy_key=None), th)
    assert "unattributed" in result
    # Even though degraded, we never auto-disable the unattributed bucket.
    assert disabled_keys(result) == []
