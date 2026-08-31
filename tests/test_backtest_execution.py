"""Tests: execution cost model and risk-based position sizing."""

from backtesting.execution import CostModel, position_lots


def test_entry_fill_is_adverse():
    cm = CostModel(spread=0.4, slippage=0.1)
    # adverse = 0.2 + 0.1 = 0.3
    assert cm.entry_fill("long", 100.0) == 100.3
    assert cm.entry_fill("short", 100.0) == 99.7


def test_exit_fill_is_adverse():
    cm = CostModel(spread=0.4, slippage=0.1)
    assert cm.exit_fill("long", 100.0) == 99.7
    assert cm.exit_fill("short", 100.0) == 100.3


def test_commission_per_lot():
    cm = CostModel(commission_per_lot=7.0)
    assert cm.commission(2.0) == 14.0


def test_net_pnl_long_profit_minus_costs():
    cm = CostModel(spread=0, slippage=0, commission_per_lot=5.0, value_per_unit=1.0)
    # long 100->110, 2 lots => gross 20, minus commission 10 => 10
    assert cm.net_pnl("long", 100.0, 110.0, 2.0) == 10.0


def test_net_pnl_short_profit():
    cm = CostModel(spread=0, slippage=0, commission_per_lot=0.0, value_per_unit=1.0)
    assert cm.gross_pnl("short", 100.0, 90.0, 1.0) == 10.0


def test_position_lots_risk_based():
    # risk 1% of 10,000 = 100; stop distance 5; value 1 => 20 lots
    lots = position_lots(10_000, 1.0, 100.0, 95.0, value_per_unit=1.0, max_lot_size=1e9)
    assert lots == 20.0


def test_position_lots_capped():
    lots = position_lots(10_000, 5.0, 100.0, 95.0, value_per_unit=1.0, max_lot_size=10.0)
    assert lots == 10.0  # raw would be 100, capped


def test_position_lots_zero_on_bad_inputs():
    assert position_lots(10_000, 1.0, 100.0, 100.0, 1.0, 1e9) == 0.0  # zero stop distance
    assert position_lots(0, 1.0, 100.0, 95.0, 1.0, 1e9) == 0.0
