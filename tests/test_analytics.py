"""Tests: analytics (performance breakdowns, journal intelligence, comparison,
signal history, system health)."""

from analytics import (
    HealthStatus,
    JournalAnalyzer,
    SignalHistory,
    SystemHealth,
    build_strategy_comparison,
    metrics,
    standard_breakdowns,
)


def _t(**kw):
    base = {
        "id": kw.get("id", 1),
        "pnl": 0.0,
        "return_pct": 0.0,
        "strategy_key": "tf",
        "strategy_name": "Trend",
        "direction": "long",
        "exit_reason": "take_profit",
        "regime": "strong_bullish",
        "timeframe": "1h",
        "opened_epoch": 1_700_000_000,
        "closed_epoch": 1_700_003_600,
    }
    base.update(kw)
    return base


def test_metrics_basic():
    m = metrics([_t(pnl=100), _t(pnl=-50), _t(pnl=100)])
    assert m["num_trades"] == 3
    assert m["win_rate"] == round(2 / 3, 4)
    assert m["net_pnl"] == 150.0
    assert m["profit_factor"] == 4.0
    assert m["average_holding_seconds"] == 3600.0


def test_standard_breakdowns_dimensions():
    bd = standard_breakdowns([_t(pnl=100), _t(pnl=-50, direction="short")])
    for key in ("overall", "by_strategy", "by_direction", "by_session", "by_month", "by_regime"):
        assert key in bd
    assert len(bd["by_direction"]["rows"]) == 2


def test_journal_overtrading_and_after_losses():
    trades = [
        _t(id=1, pnl=-10, opened_epoch=1_700_000_000),
        _t(id=2, pnl=-10, opened_epoch=1_700_000_100),
        _t(id=3, pnl=-10, opened_epoch=1_700_000_200),
        _t(id=4, pnl=-10, opened_epoch=1_700_000_300),
    ]
    obs = JournalAnalyzer(max_trades_per_day=2, consecutive_loss_threshold=2).analyze(trades)
    codes = {o.code for o in obs}
    assert "overtrading" in codes
    assert "trading_after_losses" in codes


def test_journal_large_position_impact():
    obs = JournalAnalyzer(large_impact_pct=0.03).analyze([_t(pnl=500, return_pct=0.05)])
    assert any(o.code == "large_position_impact" for o in obs)


def test_comparison_merges_sources():
    rows = build_strategy_comparison(
        [{"key": "tf", "name": "Trend"}],
        oos_by_key={"tf": {"net_pnl": 100}},
        paper_by_key={"tf": {"net_pnl": 50}},
    )
    assert rows[0]["backtest_oos"]["net_pnl"] == 100
    assert rows[0]["paper"]["net_pnl"] == 50
    assert rows[0]["live"] is None


def test_signal_history_transitions():
    sh = SignalHistory()
    sh.record_snapshot([{"strategy_key": "tf", "strategy_name": "T", "level": 1}], now_epoch=1)
    ev = sh.record_snapshot(
        [
            {
                "strategy_key": "tf",
                "strategy_name": "T",
                "level": 3,
                "confirmations": ["a"],
                "missing_confirmations": [],
            }
        ],
        now_epoch=2,
    )
    assert ev[0].transition == "confirmed"
    ev2 = sh.record_snapshot(
        [{"strategy_key": "tf", "strategy_name": "T", "level": 1, "invalidation": "x"}], now_epoch=3
    )
    assert ev2[0].transition == "invalidated"


def test_system_health_overall_is_worst():
    h = SystemHealth()
    h.add("A", HealthStatus.HEALTHY)
    h.add("B", HealthStatus.WARNING)
    assert h.overall() is HealthStatus.WARNING
    h.add("C", HealthStatus.FAILURE)
    assert h.overall() is HealthStatus.FAILURE
    assert h.to_dict()["overall"] == "failure"
