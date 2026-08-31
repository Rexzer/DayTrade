"""Tests: paper execution cost model and sizing."""

from paper_trading.execution import PaperCostModel, position_lots


def test_adverse_includes_spread_slippage_latency():
    cm = PaperCostModel(spread=0.4, slippage=0.1, latency_slippage=0.05)
    assert cm.adverse == 0.2 + 0.1 + 0.05


def test_entry_and_exit_fills_are_adverse():
    cm = PaperCostModel(spread=0.4, slippage=0.1, latency_slippage=0.0)
    assert cm.entry_fill("long", 100.0) == 100.3
    assert cm.entry_fill("short", 100.0) == 99.7
    assert cm.exit_fill("long", 100.0) == 99.7
    assert cm.exit_fill("short", 100.0) == 100.3


def test_net_pnl_deducts_commission():
    cm = PaperCostModel(
        spread=0, slippage=0, latency_slippage=0, commission_per_lot=5, value_per_unit=1
    )
    assert cm.net_pnl("long", 100.0, 110.0, 2.0) == 20.0 - 10.0


def test_position_lots_risk_based_and_capped():
    assert position_lots(10_000, 1.0, 100.0, 95.0, 1.0, 1e9) == 20.0
    assert position_lots(10_000, 5.0, 100.0, 95.0, 1.0, 10.0) == 10.0
    assert position_lots(10_000, 1.0, 100.0, 100.0, 1.0, 1e9) == 0.0
