"""Integration tests: cross-component live-trading reliability behaviours.

These drive the REAL components together against the MetaTrader5 mock
(``FakeMT5``) — execution provider + coordinator + independent risk engine +
authorization + position synchronizer + persistence store + decay monitor — to
verify the Feature 1/2 wiring (closed-P&L accounting, restart-safe risk state,
startup reconciliation, decayed-strategy exclusion) works as a whole, not just
in isolation.
"""

from analytics.lifecycle import HealthThresholds, disabled_keys, monitor_strategies
from backend.app.persistence.store import InMemoryTradeStore, stored_trade_from_position
from execution_engine import (
    REQUIRED_CONFIRMATIONS,
    BrokerPosition,
    ExecutionCoordinator,
    LiveAuthorization,
    MT5ExecutionProvider,
    PositionSynchronizer,
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


def _ctx(risk_state_engine, **kw):
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


def _pos(ticket, profit, *, symbol="XAUUSDm", vol=0.1):
    return BrokerPosition(
        ticket=ticket,
        symbol=symbol,
        side="buy",
        volume=vol,
        price_open=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
        price_current=2405.0,
        profit=profit,
        time_epoch=1_700_000_000.0,
    )


def _coord(risk, auth=None):
    provider = MT5ExecutionProvider(client=FakeMT5())
    provider.connect()
    coord = ExecutionCoordinator(provider, risk, auth or _authorized())
    spec = provider.get_symbol_spec("XAUUSDm")
    return coord, provider, spec


# --------------------------------------------------------------------------- #
def test_open_then_closed_loss_feeds_risk_and_halts_further_trading():
    """A losing close must flow into the risk engine and trip the daily halt."""
    risk = LiveRiskEngine(RiskSettings(max_daily_loss_pct=2.0, max_open_positions=3))
    risk.update_equity(10_000.0)
    coord, provider, spec = _coord(risk)

    # 1) Open a live trade through the full pipeline.
    out = coord.execute_signal(SIGNAL, _ctx(risk), spec)
    assert out.executed is True
    assert risk.state.trades_today == 1

    # 2) A position closes at a big loss — detected via the synchronizer, then
    #    fed into the risk engine exactly as LiveTradingService._record_closed_pnl does.
    sync = PositionSynchronizer()
    losing = _pos(ticket=1, profit=-250.0)
    sync.diff([losing])  # baseline: position open
    diff = sync.diff([])  # now gone -> closed
    assert len(diff.closed) == 1
    for p in diff.closed:
        risk.record_trade_closed(float(p.profit), 9_750.0)

    # 3) The daily loss limit is now latched and blocks the next execution.
    assert risk.state.daily_loss_halt is True
    blocked = coord.execute_signal(
        dict(SIGNAL, strategy_key="s2"), _ctx(risk, now_epoch=1_700_000_100.0), spec
    )
    assert blocked.executed is False and blocked.stage == "risk"


def test_risk_halt_survives_simulated_restart_via_store():
    """Persisted risk state must keep blocking after a process restart."""
    store = InMemoryTradeStore()

    # Session 1: trip the halt, persist.
    risk1 = LiveRiskEngine(RiskSettings(max_daily_loss_pct=2.0))
    risk1.update_equity(10_000.0)
    risk1.record_trade_closed(-250.0, 9_750.0)
    assert risk1.state.daily_loss_halt is True
    store.save_risk_state(risk1.state.to_dict())

    # Session 2: brand-new engine (as after a restart), restore from the store.
    risk2 = LiveRiskEngine(RiskSettings(max_daily_loss_pct=2.0))
    assert risk2.state.daily_loss_halt is False
    risk2.restore_state(store.load_risk_state())

    coord, provider, spec = _coord(risk2)
    out = coord.execute_signal(SIGNAL, _ctx(risk2, equity=9_750.0), spec)
    assert out.executed is False and out.stage == "risk"


def test_startup_reconciliation_adopts_then_detects_close():
    """First sync adopts pre-existing positions; later closes still fire."""
    sync = PositionSynchronizer()
    existing = _pos(ticket=1, profit=50.0)

    # Startup reconcile: seed baseline (adopt) — we IGNORE this diff's 'opened'.
    sync.diff([existing])
    # Next sync with the same position: no spurious open/close events.
    steady = sync.diff([existing])
    assert not steady.has_changes

    # When it finally closes, it's reported so P&L can be journaled.
    closed = sync.diff([])
    assert len(closed.closed) == 1
    trade = stored_trade_from_position(closed.closed[0], mode="live")
    assert trade.pnl == 50.0


def test_decayed_strategy_is_excluded_from_signal_selection():
    """The decay monitor's disabled set filters candidate signals (as in service)."""
    th = HealthThresholds(min_trades=10)
    good = [{"pnl": p, "strategy_key": "good"} for p in [10, -5, 10, 10, -5, 10, 10, -5, 10, 10]]
    bad = [{"pnl": p, "strategy_key": "bad"} for p in [-10, 5, -10, -10, 5, -10, -10, 5, -10, -10]]
    disabled = set(disabled_keys(monitor_strategies(good + bad, th)))
    assert disabled == {"bad"}

    # Reproduce the service's best-of-all filter: disabled strategies dropped.
    signals = [
        {"strategy_key": "bad", "level": 3},
        {"strategy_key": "good", "level": 3},
    ]
    candidates = [s for s in signals if s["strategy_key"] not in disabled]
    best = next((s for s in candidates if s.get("level", 0) >= 3), None)
    assert best is not None and best["strategy_key"] == "good"
