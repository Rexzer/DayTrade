"""Tests: splitting, walk-forward, sensitivity, Monte Carlo, and the report."""

from backtesting.config import BacktestConfig
from backtesting.metrics import compute_metrics  # noqa: F401 (kept for parity)
from backtesting.montecarlo import monte_carlo
from backtesting.report import STATUS_FAILED, STATUS_PASS, STATUS_WARNING, build_report
from backtesting.sensitivity import parameter_sensitivity
from backtesting.splitting import compute_windows, run_all_segments
from backtesting.trade import Trade
from backtesting.walkforward import walk_forward
from market_data.provider import Timeframe
from strategy_engine.strategy import SignalLevel
from tests.helpers import FixedSignalStrategy, uptrend

CFG = BacktestConfig(
    primary_timeframe="1h", warmup_bars=5, spread=0, slippage=0, commission_per_lot=0
)


def _h1(n: int):
    """H1 candles so open-time spacing matches the '1h' primary timeframe."""
    return {"1h": uptrend(n, timeframe=Timeframe.H1)}


def test_compute_windows_are_ordered_and_disjoint():
    candles = _h1(100)
    w = compute_windows(candles, "1h", train=0.5, validation=0.25)
    assert w["train"][0] <= w["train"][1] < w["validation"][0] <= w["validation"][1]
    assert w["validation"][1] < w["oos"][0] <= w["oos"][1]


def test_run_all_segments_returns_three():
    candles = _h1(120)
    segs = run_all_segments(FixedSignalStrategy("long"), CFG, candles)
    assert set(segs.keys()) == {"train", "validation", "oos"}


def test_report_failed_when_insufficient_trades():
    # WATCH-level strategy never trades -> insufficient evidence -> FAILED.
    candles = _h1(120)
    strat = FixedSignalStrategy("long", level=SignalLevel.WATCH)
    rep = build_report(strat, candles, CFG, min_oos_trades=5)
    assert rep["status"] == STATUS_FAILED
    assert any("Insufficient evidence" in w for w in rep["warnings"])


def test_report_status_is_valid_value():
    candles = _h1(160)
    rep = build_report(FixedSignalStrategy("long", stop_offset=8, tp_offset=12), candles, CFG)
    assert rep["status"] in (STATUS_PASS, STATUS_WARNING, STATUS_FAILED)
    assert "in_sample" in rep and "out_of_sample" in rep


def test_walk_forward_oos_windows_are_strictly_later():
    candles = _h1(160)

    def factory(params):
        return FixedSignalStrategy("long", stop_offset=params.get("stop_offset", 10))

    wf = walk_forward(factory, [{"stop_offset": 8}, {"stop_offset": 12}], CFG, candles, folds=2)
    assert len(wf["folds"]) >= 1
    for fold in wf["folds"]:
        is_end = fold["in_sample_window"][1]
        oos_start = fold["oos_window"][0]
        # Out-of-sample must begin at or after in-sample end (no future leak).
        assert oos_start >= is_end


def test_sensitivity_structure_and_stable_case():
    candles = _h1(140)

    def factory(params):
        return FixedSignalStrategy("long", stop_offset=params.get("stop_offset", 10))

    sens = parameter_sensitivity(
        factory, {"stop_offset": 10}, "stop_offset", [9, 10, 11], CFG, candles, metric="net_profit"
    )
    assert sens["param_name"] == "stop_offset"
    assert len(sens["results"]) == 3
    assert isinstance(sens["fragile"], bool)


def test_sensitivity_flags_fragile_when_too_few_values():
    candles = _h1(140)

    def factory(params):
        return FixedSignalStrategy("long", stop_offset=params.get("stop_offset", 10))

    sens = parameter_sensitivity(
        factory, {"stop_offset": 10}, "stop_offset", [10], CFG, candles, metric="net_profit"
    )
    assert sens["fragile"] is True


def _mk_trade(pnl):
    return Trade("s", "long", 0, 1, 100, 100 + pnl, 90, 120, 1, pnl, pnl / 10_000, "x", 1)


def test_monte_carlo_deterministic_and_shaped():
    trades = [_mk_trade(x) for x in (150, -100, 150, -100, 150, -100, 200)]
    a = monte_carlo(trades, 10_000, iterations=200, seed=7)
    b = monte_carlo(trades, 10_000, iterations=200, seed=7)
    assert a == b  # deterministic given the seed
    assert set(a["ending_equity"].keys()) == {"p5", "p50", "p95"}
    assert a["ending_equity"]["p5"] <= a["ending_equity"]["p95"]


def test_monte_carlo_too_few_trades():
    out = monte_carlo([_mk_trade(1)], 10_000)
    assert out["iterations"] == 0
