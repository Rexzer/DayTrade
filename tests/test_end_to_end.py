"""End-to-end integration test (offline, deterministic).

Exercises the full trading pipeline with real engine code and a MOCKED broker:

    market data (candles) -> strategy/signal engine -> INDEPENDENT risk engine
    -> execution coordinator -> mock MetaTrader 5 -> durable store

A deterministic stub strategy provides a CONFIRMED signal so the execution path
is exercised reliably; the REAL strategy engine is used to prove the stale-data
failsafe. Also asserts risk-rejection-never-sends and kill-switch-blocks. No
real broker is contacted.
"""

from backend.app.persistence.store import InMemoryTradeStore, StoredOrder, StoredSignal
from execution_engine import (
    REQUIRED_CONFIRMATIONS,
    ExecutionCoordinator,
    LiveAuthorization,
    MT5ExecutionProvider,
)
from market_data.provider import Timeframe
from risk_engine import LiveRiskEngine, RiskContext, RiskSettings
from strategy_engine import SignalEngine
from strategy_engine.strategy import MarketContext, SignalLevel
from tests.helpers import FakeMT5, FixedSignalStrategy, uptrend


def _authorized() -> LiveAuthorization:
    auth = LiveAuthorization(config_enabled=True)
    for k in REQUIRED_CONFIRMATIONS:
        auth.confirm(k, True)
    auth.arm()
    return auth


def _context() -> MarketContext:
    return MarketContext(
        symbol="XAUUSD",
        candles={
            "4h": uptrend(150, timeframe=Timeframe.H4),
            "1h": uptrend(150, timeframe=Timeframe.H1),
            "15m": uptrend(150, timeframe=Timeframe.M15),
            "5m": uptrend(150, timeframe=Timeframe.M5),
        },
    )


def _stub_engine() -> SignalEngine:
    # Deterministic CONFIRMED long on the 1h timeframe.
    return SignalEngine(
        strategies=[FixedSignalStrategy("long", stop_offset=10, tp_offset=15, timeframe="1h")]
    )


def _confirmed_signal(ctx: MarketContext) -> dict:
    res = _stub_engine().evaluate_all(ctx, data_status="live", primary_timeframe="1h")
    assert res.signals_allowed
    sig = res.signals[0]
    assert sig["level"] == SignalLevel.CONFIRMED_SETUP.value
    sig["symbol"] = "XAUUSD"
    return sig


def _risk_ctx(price: float, **kw) -> RiskContext:
    base = dict(
        equity=10_000.0,
        spread_points=5.0,
        price=price,
        data_status="live",
        broker_connected=True,
        now_epoch=1_700_000_000.0,
    )
    base.update(kw)
    return RiskContext(**base)


def _provider() -> MT5ExecutionProvider:
    p = MT5ExecutionProvider(client=FakeMT5(symbol="XAUUSD"))
    p.connect()
    return p


def test_full_pipeline_signal_to_execution_and_persistence():
    ctx = _context()
    price = ctx.candles["1h"][-1].close
    signal = _confirmed_signal(ctx)

    provider = _provider()
    spec = provider.get_symbol_spec("XAUUSD")
    coord = ExecutionCoordinator(provider, LiveRiskEngine(RiskSettings()), _authorized())

    outcome = coord.execute_signal(signal, _risk_ctx(price), spec)
    assert outcome.executed is True
    assert outcome.risk_decision.approved is True
    assert outcome.order_result.ok and outcome.order_result.retcode == 10009

    # Durable persistence (mirrors LiveTradingService._persist).
    store = InMemoryTradeStore()
    store.save_signal(
        StoredSignal(
            strategy_key=signal["strategy_key"],
            symbol="XAUUSD",
            timeframe=signal.get("timeframe"),
            level=signal["level"],
            direction=signal["direction"],
        )
    )
    store.save_order(
        StoredOrder(
            account_label="Live",
            symbol="XAUUSD",
            side="buy",
            order_type="market",
            volume_lots=outcome.risk_decision.sizing.lots,
            broker_order_id=outcome.order_result.order_id,
            status="filled",
        )
    )
    assert len(store.recent_signals()) == 1
    assert store.recent_orders()[0]["broker_order_id"] == 987654

    # The risk engine recorded the opened trade against its daily counter.
    assert coord.risk.state.trades_today == 1

    # Execution-log stages tell the full story.
    stages = [e["stage"] for e in coord.log.recent(20)]
    for stage in ("signal", "risk", "order_check", "order_request", "order_response", "position"):
        assert stage in stages


def test_failsafe_stale_data_halts_real_engine():
    # The REAL strategy engine must produce no signals on stale data.
    res = SignalEngine().evaluate_all(_context(), data_status="stale", primary_timeframe="1h")
    assert res.signals_allowed is False and res.signals == []


def test_failsafe_risk_rejection_never_sends_order():
    ctx = _context()
    signal = _confirmed_signal(ctx)
    provider = _provider()
    coord = ExecutionCoordinator(
        provider, LiveRiskEngine(RiskSettings(max_spread_points=50)), _authorized()
    )
    outcome = coord.execute_signal(
        signal,
        _risk_ctx(ctx.candles["1h"][-1].close, spread_points=999.0),
        provider.get_symbol_spec("XAUUSD"),
    )
    assert outcome.executed is False and outcome.stage == "risk"
    assert provider._client.last_order_request is None  # never sent


def test_failsafe_kill_switch_blocks_execution():
    ctx = _context()
    signal = _confirmed_signal(ctx)
    provider = _provider()
    coord = ExecutionCoordinator(provider, LiveRiskEngine(RiskSettings()), _authorized())
    coord.kill_switch()
    outcome = coord.execute_signal(
        signal, _risk_ctx(ctx.candles["1h"][-1].close), provider.get_symbol_spec("XAUUSD")
    )
    assert outcome.executed is False and outcome.stage == "authorization"
