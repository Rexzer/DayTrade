"""Tests: independent live risk engine (sizing + hard limits + halts)."""

from execution_engine.provider import BrokerSymbolSpec
from risk_engine import LiveRiskEngine, ProspectiveTrade, RiskContext, RiskSettings

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

TRADE = ProspectiveTrade(
    symbol="XAUUSD", direction="long", entry=2400.0, stop_loss=2390.0, take_profit=2420.0
)


def _ctx(**kw):
    base = dict(
        equity=10_000.0,
        spread_points=10.0,
        price=2400.0,
        data_status="live",
        broker_connected=True,
        now_epoch=1_700_000_000.0,
        open_positions=0,
        open_xauusd_positions=0,
    )
    base.update(kw)
    return RiskContext(**base)


def _engine(**settings):
    return LiveRiskEngine(RiskSettings(**settings))


def test_position_sizing_from_broker_spec():
    eng = _engine(risk_per_trade_pct=1.0)
    sizing = eng.position_size(10_000.0, TRADE, SPEC)
    # risk 100; stop 10 price / 0.01 tick = 1000 ticks * 1.0 = 1000/lot => 0.1 lots
    assert sizing.lots == 0.1
    assert sizing.risk_amount == 100.0
    assert sizing.money_per_lot == 1000.0


def test_approval_when_all_pass():
    dec = _engine().evaluate(TRADE, _ctx(), SPEC)
    assert dec.approved is True
    assert dec.sizing.lots > 0


def test_spread_filter_rejects():
    dec = _engine(max_spread_points=50).evaluate(TRADE, _ctx(spread_points=99), SPEC)
    assert not dec.approved
    assert any("spread" in r.lower() for r in dec.reasons)


def test_data_failsafe_rejects():
    for status in ("stale", "disconnected", "invalid"):
        dec = _engine().evaluate(TRADE, _ctx(data_status=status), SPEC)
        assert not dec.approved


def test_broker_disconnected_rejects():
    dec = _engine().evaluate(TRADE, _ctx(broker_connected=False), SPEC)
    assert not dec.approved


def test_news_blackout_rejects_inside_window_allows_outside():
    eng = _engine(news_blackout_before_min=10, news_blackout_after_min=15)
    now = 1_700_000_000.0
    inside = eng.evaluate(TRADE, _ctx(now_epoch=now, news_events=((now + 60, "high"),)), SPEC)
    assert not inside.approved
    outside = eng.evaluate(TRADE, _ctx(now_epoch=now, news_events=((now + 3600, "high"),)), SPEC)
    assert outside.approved


def test_max_open_positions_rejects():
    dec = _engine(max_open_positions=1).evaluate(TRADE, _ctx(open_positions=1), SPEC)
    assert not dec.approved


def test_max_xauusd_positions_rejects():
    dec = _engine(max_xauusd_positions=1).evaluate(TRADE, _ctx(open_xauusd_positions=1), SPEC)
    assert not dec.approved


def test_max_trades_per_day_rejects():
    eng = _engine(max_trades_per_day=2)
    eng.roll_periods(1_700_000_000.0, 10_000.0)
    eng.state.trades_today = 2
    dec = eng.evaluate(TRADE, _ctx(), SPEC)
    assert not dec.approved


def test_max_consecutive_losses_rejects():
    eng = _engine(max_consecutive_losses=3)
    eng.state.consecutive_losses = 3
    dec = eng.evaluate(TRADE, _ctx(), SPEC)
    assert not dec.approved


def test_stop_geometry_rejects():
    bad = ProspectiveTrade(symbol="XAUUSD", direction="long", entry=2400.0, stop_loss=2410.0)
    dec = _engine().evaluate(bad, _ctx(), SPEC)
    assert not dec.approved


def test_daily_loss_halt_latches_and_manual_reset_clears():
    eng = _engine(max_daily_loss_pct=2.0)
    eng.roll_periods(1_700_000_000.0, 10_000.0)
    eng.update_equity(10_000.0)  # peak = 10,000
    eng.record_trade_closed(-250.0, 9_750.0)  # -2.5% > 2% limit -> halt
    assert eng.state.daily_loss_halt is True
    assert not eng.evaluate(TRADE, _ctx(equity=9_750.0), SPEC).approved
    eng.manual_reset()
    assert eng.state.daily_loss_halt is False


def test_drawdown_halt_latches():
    eng = _engine(max_drawdown_pct=10.0)
    eng.update_equity(10_000.0)
    eng.update_equity(8_900.0)  # 11% drawdown
    assert eng.state.drawdown_halt is True
    assert not eng.evaluate(TRADE, _ctx(equity=8_900.0), SPEC).approved
    eng.manual_reset()
    assert eng.state.drawdown_halt is False


def test_consecutive_losses_increment_and_reset():
    eng = _engine()
    eng.update_equity(10_000.0)
    eng.record_trade_closed(-50.0, 9_950.0)
    eng.record_trade_closed(-50.0, 9_900.0)
    assert eng.state.consecutive_losses == 2
    eng.record_trade_closed(100.0, 10_000.0)
    assert eng.state.consecutive_losses == 0


def test_sizing_below_broker_minimum_is_rejected():
    # Huge stop distance -> tiny lots below volume_min -> rejected.
    tiny = ProspectiveTrade(symbol="XAUUSD", direction="long", entry=2400.0, stop_loss=100.0)
    dec = _engine(risk_per_trade_pct=0.25).evaluate(tiny, _ctx(price=2400.0), SPEC)
    assert not dec.approved
    assert any("size" in r.lower() or "minimum" in r.lower() for r in dec.reasons)
