"""Tests: position synchronization + order validation."""

from execution_engine import (
    BrokerPosition,
    ExecOrderRequest,
    PositionSynchronizer,
    validate_order,
)
from execution_engine.provider import BrokerSymbolSpec

SPEC = BrokerSymbolSpec(
    name="XAUUSD",
    digits=2,
    point=0.01,
    tick_size=0.01,
    tick_value=1.0,
    contract_size=100.0,
    volume_min=0.01,
    volume_max=50.0,
    volume_step=0.01,
)


def _pos(ticket, sl=2390.0, tp=2420.0, vol=0.1):
    return BrokerPosition(
        ticket=ticket,
        symbol="XAUUSD",
        side="buy",
        volume=vol,
        price_open=2400.0,
        stop_loss=sl,
        take_profit=tp,
    )


def test_sync_detects_opened():
    s = PositionSynchronizer()
    diff = s.diff([_pos(1), _pos(2)])
    assert len(diff.opened) == 2 and not diff.closed and not diff.modified


def test_sync_detects_closed():
    s = PositionSynchronizer()
    s.diff([_pos(1), _pos(2)])
    diff = s.diff([_pos(1)])  # ticket 2 gone
    assert [p.ticket for p in diff.closed] == [2]
    assert not diff.opened


def test_sync_detects_modified():
    s = PositionSynchronizer()
    s.diff([_pos(1, sl=2390.0)])
    diff = s.diff([_pos(1, sl=2395.0)])  # stop moved
    assert [p.ticket for p in diff.modified] == [1]


def test_sync_no_changes():
    s = PositionSynchronizer()
    s.diff([_pos(1)])
    diff = s.diff([_pos(1)])
    assert not diff.has_changes


def test_validate_volume_bounds_and_step():
    below = validate_order(ExecOrderRequest("XAUUSD", "buy", "market", 0.005), SPEC)
    assert not below.ok
    above = validate_order(ExecOrderRequest("XAUUSD", "buy", "market", 99.0), SPEC)
    assert not above.ok
    step = validate_order(ExecOrderRequest("XAUUSD", "buy", "market", 0.013), SPEC)
    assert not step.ok


def test_validate_sl_tp_sides():
    buy_bad = validate_order(
        ExecOrderRequest("XAUUSD", "buy", "market", 0.1, price=2400.0, stop_loss=2410.0), SPEC
    )
    assert not buy_bad.ok
    sell_ok = validate_order(
        ExecOrderRequest(
            "XAUUSD", "sell", "market", 0.1, price=2400.0, stop_loss=2410.0, take_profit=2380.0
        ),
        SPEC,
    )
    assert sell_ok.ok


def test_validate_symbol_mismatch():
    res = validate_order(ExecOrderRequest("EURUSD", "buy", "market", 0.1), SPEC)
    assert not res.ok
    assert any("mismatch" in r.lower() for r in res.reasons)


def test_validate_trade_not_allowed():
    spec = BrokerSymbolSpec(
        name="XAUUSD",
        digits=2,
        point=0.01,
        tick_size=0.01,
        tick_value=1.0,
        contract_size=100.0,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
        trade_allowed=False,
    )
    res = validate_order(ExecOrderRequest("XAUUSD", "buy", "market", 0.1), spec)
    assert not res.ok
