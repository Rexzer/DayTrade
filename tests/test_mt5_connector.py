"""Tests: MT5 connector (mocked client) — reads, validation, disabled writes."""

import pytest

from execution_engine import (
    ExecOrderRequest,
    InvalidSymbolError,
    LiveExecutionDisabledError,
    MT5ExecutionProvider,
    MT5MarketDataProvider,
    build_account_verification,
)
from market_data.provider import Timeframe
from tests.helpers import FakeMT5


def _connected(**kw):
    p = MT5ExecutionProvider(client=FakeMT5(**kw))
    assert p.connect() is True
    return p


def test_connection_failure_sets_error_and_stays_disconnected():
    p = MT5ExecutionProvider(client=FakeMT5(init_ok=False))
    assert p.connect() is False
    assert p.is_connected() is False
    assert p.last_error is not None


def test_reconnection_after_failure():
    fake = FakeMT5(init_ok=False)
    p = MT5ExecutionProvider(client=fake)
    assert p.connect() is False
    fake.init_ok = True  # broker comes back
    assert p.reconnect() is True
    assert p.is_connected() is True


def test_account_info_mapping():
    p = _connected()
    acc = p.get_account_info()
    assert acc.company == "ACME Markets"
    assert acc.currency == "USD"
    assert acc.balance == 10_000.0
    assert acc.trade_mode == "demo"
    assert acc.free_margin == 9_850.0


def test_symbol_spec_mapping():
    p = _connected()
    spec = p.get_symbol_spec("XAUUSDm")
    assert spec.name == "XAUUSDm"
    assert spec.volume_min == 0.01 and spec.volume_step == 0.01 and spec.volume_max == 50.0
    assert spec.contract_size == 100.0 and spec.tick_value == 1.0


def test_invalid_symbol_raises():
    p = _connected()
    with pytest.raises(InvalidSymbolError):
        p.get_symbol_spec("EURUSD")


def test_tick_and_spread():
    p = _connected()
    t = p.get_tick("XAUUSDm")
    assert round(t.spread, 2) == 0.30


def test_historical_candles():
    p = _connected()
    candles = p.get_historical("XAUUSDm", Timeframe.H1, count=10)
    assert len(candles) == 10
    assert candles[0].timeframe is Timeframe.H1
    assert candles[0].close == 2401.0


def test_positions_and_orders_mapping():
    p = _connected()
    positions = p.get_positions()
    assert len(positions) == 1
    assert positions[0].side == "buy" and positions[0].stop_loss == 2390.0
    orders = p.get_orders()
    assert orders[0].order_type == "limit" and orders[0].side == "buy"


def test_check_order_valid():
    p = _connected()
    req = ExecOrderRequest(
        "XAUUSDm", "buy", "market", 0.10, price=2400.4, stop_loss=2390.0, take_profit=2420.0
    )
    assert p.check_order(req).ok is True


def test_check_order_invalid_volume():
    p = _connected()
    req = ExecOrderRequest(
        "XAUUSDm", "buy", "market", 0.005, price=2400.4, stop_loss=2390.0, take_profit=2420.0
    )
    res = p.check_order(req)
    assert res.ok is False
    assert any("minimum" in r for r in res.reasons)


def test_check_order_invalid_stop_side():
    p = _connected()
    # BUY with stop ABOVE price is invalid.
    req = ExecOrderRequest(
        "XAUUSDm", "buy", "market", 0.10, price=2400.4, stop_loss=2410.0, take_profit=2420.0
    )
    res = p.check_order(req)
    assert res.ok is False
    assert any("stop-loss must be below" in r for r in res.reasons)


def test_check_order_broker_rejection():
    # Broker order_check returns a non-OK retcode -> rejected.
    p = MT5ExecutionProvider(client=FakeMT5(order_check_retcode=10015))
    p.connect()
    req = ExecOrderRequest(
        "XAUUSDm", "buy", "market", 0.10, price=2400.4, stop_loss=2390.0, take_profit=2420.0
    )
    res = p.check_order(req)
    assert res.ok is False
    assert res.retcode == 10015


def test_writes_are_disabled():
    p = _connected()
    req = ExecOrderRequest("XAUUSDm", "buy", "market", 0.10)
    with pytest.raises(LiveExecutionDisabledError):
        p.send_order(req)
    with pytest.raises(LiveExecutionDisabledError):
        p.modify_order(1, stop_loss=2390.0)
    with pytest.raises(LiveExecutionDisabledError):
        p.close_position(1)


def test_live_enabled_flag_does_not_unlock_writes():
    # Even if an operator sets live_enabled True, Phase 6 keeps writes disabled.
    p = MT5ExecutionProvider(client=FakeMT5(), live_enabled=True)
    p.connect()
    with pytest.raises(LiveExecutionDisabledError):
        p.send_order(ExecOrderRequest("XAUUSDm", "buy", "market", 0.10))


def test_market_data_adapter():
    p = _connected()
    md = MT5MarketDataProvider(p)
    assert md.is_connected() is True
    snap = md.get_snapshot("XAUUSDm")
    assert snap.connected is True and snap.bid == 2400.10
    assert len(md.get_candles("XAUUSDm", Timeframe.H1, 5)) == 5


def test_market_data_adapter_disconnected():
    p = MT5ExecutionProvider(client=FakeMT5())  # not connected
    md = MT5MarketDataProvider(p)
    snap = md.get_snapshot("XAUUSDm")
    assert snap.connected is False and snap.bid is None
    assert md.get_candles("XAUUSDm", Timeframe.H1, 5) == []


def test_verification_payload():
    p = _connected()
    v = build_account_verification(p, "XAUUSDm")
    assert v["connected"] is True
    assert v["broker"] == "ACME Markets"
    assert v["account_type"] == "demo"
    assert v["currency"] == "USD"
    assert v["symbol"] == "XAUUSDm"
    assert v["live_execution_enabled"] is False
    assert v["contract_specifications"]["volume_step"] == 0.01
