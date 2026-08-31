"""Tests: backtest performance metrics."""

from backtesting.metrics import compute_metrics, drawdown_curve, max_drawdown
from backtesting.trade import Trade


def _trade(pnl: float) -> Trade:
    return Trade(
        strategy_key="s",
        direction="long",
        entry_time=0,
        exit_time=1,
        entry_price=100,
        exit_price=100 + pnl,
        stop_loss=90,
        take_profit=120,
        lots=1,
        pnl=pnl,
        return_pct=pnl / 10_000,
        exit_reason="take_profit" if pnl > 0 else "stop_loss",
        bars_held=1,
    )


def test_max_drawdown_basic():
    abs_dd, pct = max_drawdown([100, 120, 90, 110, 80])
    assert abs_dd == 40  # peak 120 -> trough 80
    assert round(pct, 4) == round(40 / 120, 4)


def test_drawdown_curve_length():
    curve = drawdown_curve([(0, 100), (1, 120), (2, 90)])
    assert len(curve) == 3
    assert curve[-1]["drawdown"] == 30


def test_metrics_win_rate_and_profit_factor():
    trades = [_trade(150), _trade(-100), _trade(150), _trade(-100), _trade(150)]
    equity = [(0, 10_000), (1, 10_150), (2, 10_050), (3, 10_200), (4, 10_100), (5, 10_250)]
    m = compute_metrics(trades, equity, 10_000)
    assert m["num_trades"] == 5
    assert m["winning_trades"] == 3
    assert m["losing_trades"] == 2
    assert m["win_rate"] == 0.6
    assert m["gross_profit"] == 450.0
    assert m["gross_loss"] == 200.0
    assert m["net_profit"] == 250.0
    assert m["profit_factor"] == 2.25
    assert m["expectancy"] == 50.0
    assert m["average_win"] == 150.0
    assert m["average_loss"] == -100.0
    assert m["largest_win"] == 150.0
    assert m["largest_loss"] == -100.0


def test_metrics_consecutive_streaks():
    # W W L L L W  -> max win streak 2, max loss streak 3
    trades = [_trade(10), _trade(10), _trade(-5), _trade(-5), _trade(-5), _trade(10)]
    m = compute_metrics(trades, [(0, 10_000)], 10_000)
    assert m["max_consecutive_wins"] == 2
    assert m["max_consecutive_losses"] == 3


def test_profit_factor_infinite_when_no_losses():
    m = compute_metrics([_trade(10), _trade(20)], [(0, 10_000)], 10_000)
    assert m["profit_factor"] is None
    assert m["profit_factor_infinite"] is True


def test_sharpe_and_sortino_present_with_enough_trades():
    trades = [_trade(150), _trade(-100), _trade(150), _trade(-100)]
    m = compute_metrics(trades, [(0, 10_000)], 10_000)
    assert m["sharpe_ratio"] is not None
    assert m["sortino_ratio"] is not None


def test_empty_trades_safe():
    m = compute_metrics([], [(0, 10_000)], 10_000)
    assert m["num_trades"] == 0
    assert m["win_rate"] == 0.0
    assert m["net_profit"] == 0.0
