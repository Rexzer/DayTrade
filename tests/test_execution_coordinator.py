"""Tests: execution coordinator pipeline (Signal->Risk->Execution) + kill switch."""

from execution_engine import (
    REQUIRED_CONFIRMATIONS,
    ExecutionCoordinator,
    LiveAuthorization,
    MT5ExecutionProvider,
)
from risk_engine import LiveRiskEngine, RiskContext, RiskSettings
from tests.helpers import FakeMT5

SIGNAL = {
    "strategy_key": "s",
    "symbol": "XAUUSDm",
    "level": 3,
    "direction": "long",
    "stop_loss": 2390.0,
    "take_profits": (2420.0,),
}


def _authorized() -> LiveAuthorization:
    auth = LiveAuthorization(config_enabled=True)
    for k in REQUIRED_CONFIRMATIONS:
        auth.confirm(k, True)
    auth.arm()
    return auth


def _setup(client=None, risk_settings=None, auth=None):
    provider = MT5ExecutionProvider(client=client or FakeMT5())
    provider.connect()
    risk = LiveRiskEngine(
        risk_settings or RiskSettings(max_open_positions=2, max_xauusd_positions=2)
    )
    authorization = auth if auth is not None else _authorized()
    coord = ExecutionCoordinator(provider, risk, authorization)
    spec = provider.get_symbol_spec("XAUUSDm")
    return coord, provider, spec


def _ctx(**kw):
    base = dict(
        equity=10_000.0,
        spread_points=10.0,
        price=2400.4,
        data_status="live",
        broker_connected=True,
        now_epoch=1_700_000_000.0,
    )
    base.update(kw)
    return RiskContext(**base)


def test_unauthorized_blocks_and_never_sends():
    coord, provider, spec = _setup(auth=LiveAuthorization(config_enabled=False))
    out = coord.execute_signal(SIGNAL, _ctx(), spec)
    assert out.executed is False
    assert out.stage == "authorization"
    assert provider._client.last_order_request is None  # no order attempted


def test_authorized_happy_path_executes():
    coord, provider, spec = _setup()
    out = coord.execute_signal(SIGNAL, _ctx(), spec)
    assert out.executed is True
    assert out.order_result.ok and out.order_result.order_id == 987654
    assert out.risk_decision.approved
    stages = [e["stage"] for e in coord.log.recent(20)]
    for stage in ("signal", "risk", "order_check", "order_request", "order_response", "position"):
        assert stage in stages


def test_duplicate_within_window_is_blocked():
    coord, provider, spec = _setup()
    coord.execute_signal(SIGNAL, _ctx(now_epoch=1000.0), spec)
    out2 = coord.execute_signal(SIGNAL, _ctx(now_epoch=1010.0), spec)
    assert out2.executed is False and out2.stage == "duplicate"


def test_risk_rejection_prevents_order():
    # Huge spread -> risk rejects; order_send must never be called.
    coord, provider, spec = _setup(risk_settings=RiskSettings(max_spread_points=50))
    out = coord.execute_signal(SIGNAL, _ctx(spread_points=999.0), spec)
    assert out.executed is False and out.stage == "risk"
    assert provider._client.last_order_request is None


def test_data_stale_blocks_before_send():
    coord, provider, spec = _setup()
    out = coord.execute_signal(SIGNAL, _ctx(data_status="stale"), spec)
    assert out.executed is False and out.stage == "risk"
    assert provider._client.last_order_request is None


def test_broker_disconnected_blocks():
    provider = MT5ExecutionProvider(client=FakeMT5())  # not connected
    coord = ExecutionCoordinator(provider, LiveRiskEngine(RiskSettings()), _authorized())
    # spec fetch would fail while disconnected; pass a standalone spec instead.
    from execution_engine.provider import BrokerSymbolSpec

    spec = BrokerSymbolSpec("XAUUSDm", 2, 0.01, 0.01, 1.0, 100.0, 0.01, 50.0, 0.01)
    out = coord.execute_signal(SIGNAL, _ctx(broker_connected=False), spec)
    assert out.executed is False
    assert out.stage in ("execution_failsafe", "risk")


def test_broker_order_rejection_is_not_success():
    coord, provider, spec = _setup(client=FakeMT5(order_send_retcode=10015))
    out = coord.execute_signal(SIGNAL, _ctx(), spec)
    assert out.executed is False
    assert out.order_result is not None and out.order_result.ok is False
    assert out.order_result.retcode == 10015


def test_order_check_rejection_blocks_send():
    # Broker order_check returns a bad retcode -> blocked at validation stage.
    coord, provider, spec = _setup(client=FakeMT5(order_check_retcode=10015))
    out = coord.execute_signal(SIGNAL, _ctx(), spec)
    assert out.executed is False and out.stage == "order_check"
    assert provider._client.last_order_request is None  # never sent


def test_kill_switch_blocks_subsequent_execution():
    coord, provider, spec = _setup()
    coord.execute_signal(dict(SIGNAL, strategy_key="a"), _ctx(now_epoch=1000.0), spec)
    res = coord.kill_switch()
    assert res["killed"] is True
    out = coord.execute_signal(dict(SIGNAL, strategy_key="b"), _ctx(now_epoch=2000.0), spec)
    assert out.executed is False and out.stage == "authorization"


def test_kill_switch_closes_positions_when_requested():
    coord, provider, spec = _setup()
    res = coord.kill_switch(close_positions=True)
    assert res["killed"] is True
    # FakeMT5 has one open position; it should have been closed.
    assert res["closed"] >= 1


def test_records_trade_opened_on_success():
    coord, provider, spec = _setup()
    assert coord.risk.state.trades_today == 0
    coord.execute_signal(SIGNAL, _ctx(), spec)
    assert coord.risk.state.trades_today == 1
