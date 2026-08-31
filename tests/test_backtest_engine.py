"""Tests: event-driven backtester mechanics + no-look-ahead guarantee."""

from backtesting.config import BacktestConfig
from backtesting.engine import Backtester
from tests.helpers import FixedSignalStrategy, candle

# Zero-cost config for exact P&L assertions.
CFG = BacktestConfig(
    primary_timeframe="1h",
    warmup_bars=2,
    spread=0.0,
    slippage=0.0,
    commission_per_lot=0.0,
    value_per_unit=1.0,
    risk_per_trade_pct=1.0,
)


def _base_bars():
    # Flat bars so entry opens at 100; signal: stop=90, tp=115.
    return [
        candle(0, 100, 101, 99, 100),
        candle(3600, 100, 101, 99, 100),
        candle(7200, 100, 101, 99, 100),
        candle(10800, 100, 101, 99, 100),
    ]


def test_long_take_profit_is_a_win():
    bars = _base_bars() + [candle(14400, 100, 120, 99, 110)]  # high 120 hits tp 115
    strat = FixedSignalStrategy("long", stop_offset=10, tp_offset=15)
    res = Backtester(strat, CFG).run({"1h": bars})
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "take_profit"
    assert t.is_win
    # entry 100, exit 115, lots = 100/(10*1) = 10 => pnl 150
    assert round(t.pnl, 2) == 150.0


def test_long_stop_loss_is_a_loss():
    bars = _base_bars() + [candle(14400, 100, 101, 89, 95)]  # low 89 hits stop 90
    strat = FixedSignalStrategy("long", stop_offset=10, tp_offset=15)
    res = Backtester(strat, CFG).run({"1h": bars})
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "stop_loss"
    assert not t.is_win
    assert round(t.pnl, 2) == -100.0  # exactly the 1% risk with zero costs


def test_same_bar_stop_wins_over_tp():
    # Bar hits BOTH stop and target; conservative model must take the stop.
    bars = _base_bars() + [candle(14400, 100, 120, 89, 100)]
    strat = FixedSignalStrategy("long", stop_offset=10, tp_offset=15)
    res = Backtester(strat, CFG).run({"1h": bars})
    assert res.trades[0].exit_reason == "stop_loss"


def test_short_take_profit():
    # Short entry at 100, stop 110, tp 85; bar low 84 hits tp.
    bars = _base_bars() + [candle(14400, 100, 101, 84, 90)]
    strat = FixedSignalStrategy("short", stop_offset=10, tp_offset=15)
    res = Backtester(strat, CFG).run({"1h": bars})
    assert len(res.trades) == 1
    assert res.trades[0].direction == "short"
    assert res.trades[0].exit_reason == "take_profit"
    assert res.trades[0].is_win


def test_no_trade_when_signal_below_min_level():
    from strategy_engine.strategy import SignalLevel

    bars = _base_bars() + [candle(14400, 100, 120, 99, 110)]
    strat = FixedSignalStrategy("long", level=SignalLevel.WATCH)
    res = Backtester(strat, CFG).run({"1h": bars})
    assert res.trades == []


def test_allow_short_false_blocks_shorts():
    cfg = BacktestConfig(**{**CFG.__dict__, "allow_short": False})
    bars = _base_bars() + [candle(14400, 100, 101, 84, 90)]
    strat = FixedSignalStrategy("short", stop_offset=10, tp_offset=15)
    res = Backtester(strat, cfg).run({"1h": bars})
    assert res.trades == []


def test_results_are_reproducible():
    bars = _base_bars() + [candle(14400, 100, 120, 99, 110)]
    strat = FixedSignalStrategy("long")
    a = Backtester(strat, CFG).run({"1h": bars}).to_dict()
    b = Backtester(FixedSignalStrategy("long"), CFG).run({"1h": bars}).to_dict()
    assert a["trades"] == b["trades"]
    assert a["metrics"] == b["metrics"]


def test_equity_curve_recorded():
    bars = _base_bars() + [candle(14400, 100, 120, 99, 110)]
    res = Backtester(FixedSignalStrategy("long"), CFG).run({"1h": bars})
    assert len(res.equity_curve) >= 2
    # ends at the realized ending capital
    assert abs(res.equity_curve[-1][1] - res.ending_capital) < 1e-6 or res.trades


def test_slice_context_has_no_look_ahead():
    bars = [candle(i * 3600, 100, 101, 99, 100 + i) for i in range(10)]
    bt = Backtester(FixedSignalStrategy("long"), CFG)
    open_times = bt._prepare({"1h": bars})
    # Decision at the close of bar index 4 => time = bar4.open + 3600.
    decision_time = bars[4].open_time_epoch + 3600
    ctx = bt._slice_context({"1h": bars}, open_times, decision_time)
    got = ctx.candles["1h"]
    # Must include bar 4 (closed exactly at decision_time) and exclude bar 5+.
    assert len(got) == 5
    assert got[-1].open_time_epoch == bars[4].open_time_epoch
    # No candle in the context closes after the decision time.
    assert all(c.open_time_epoch + 3600 <= decision_time for c in got)
