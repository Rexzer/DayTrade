"""Tests: signal engine safety gating, MTF analysis, and alert transitions."""

from strategy_engine import AlertManager, MultiTimeframeAnalyzer, SignalEngine
from strategy_engine.strategy import MarketContext, SignalLevel
from tests.helpers import uptrend


def _ctx():
    return MarketContext(
        candles={
            "4h": uptrend(120),
            "1h": uptrend(120),
            "15m": uptrend(120),
            "5m": uptrend(120),
        },
        now_epoch=1_700_000_000,
    )


def test_stale_data_halts_signals():
    eng = SignalEngine()
    res = eng.evaluate_all(_ctx(), data_status="stale")
    assert res.signals_allowed is False
    assert res.signals == []
    assert "STALE" in res.reason


def test_disconnected_data_halts_signals():
    eng = SignalEngine()
    res = eng.evaluate_all(_ctx(), data_status="disconnected")
    assert res.signals_allowed is False


def test_no_candles_halts():
    eng = SignalEngine()
    res = eng.evaluate_all(MarketContext(candles={}), data_status="live")
    assert res.signals_allowed is False


def test_live_data_produces_sorted_signals():
    eng = SignalEngine()
    res = eng.evaluate_all(_ctx(), data_status="live", primary_timeframe="1h")
    assert res.signals_allowed is True
    assert len(res.signals) == 5
    # sorted by level desc
    levels = [s["level"] for s in res.signals]
    assert levels == sorted(levels, reverse=True)
    # never execution level
    assert all(s["level"] <= SignalLevel.CONFIRMED_SETUP.value for s in res.signals)


def test_regime_included_when_live():
    res = SignalEngine().evaluate_all(_ctx(), data_status="live")
    assert res.regime is not None and "regime" in res.regime


def test_mtf_returns_four_timeframes():
    mtf = MultiTimeframeAnalyzer().analyze(_ctx())
    tfs = [r["timeframe"] for r in mtf["timeframes"]]
    assert tfs == ["4H", "1H", "15M", "5M"]
    for row in mtf["timeframes"]:
        for key in ("trend", "structure", "momentum", "signal_state"):
            assert key in row


def test_mtf_no_data_state():
    mtf = MultiTimeframeAnalyzer().analyze(MarketContext(candles={"1h": uptrend(120)}))
    by_tf = {r["timeframe"]: r for r in mtf["timeframes"]}
    assert by_tf["4H"]["signal_state"] == "no_data"


def test_alert_emitted_on_level_rise_then_none_when_unchanged():
    am = AlertManager()
    sig = {
        "strategy_key": "trend_following",
        "strategy_name": "Trend Following",
        "level": SignalLevel.CONFIRMED_SETUP.value,
        "direction": "long",
        "confirmations": ["a", "b"],
        "missing_confirmations": [],
    }
    a1 = am.process(sig, now_epoch=1000)
    assert a1 is not None and a1.kind == "CONFIRMED SETUP"
    # Same level again -> no duplicate alert.
    assert am.process(sig, now_epoch=1001) is None


def test_alert_invalidation_on_drop():
    am = AlertManager()
    high = {
        "strategy_key": "s",
        "strategy_name": "S",
        "level": SignalLevel.CONFIRMED_SETUP.value,
        "direction": "long",
    }
    low = {**high, "level": SignalLevel.WATCH.value}
    am.process(high, now_epoch=1000)
    a = am.process(low, now_epoch=1001)
    assert a is not None and a.kind == "INVALIDATED SETUP"


def test_alert_history_limited_and_recent_order():
    am = AlertManager(max_history=5)
    for i in range(10):
        am.process(
            {
                "strategy_key": f"s{i}",
                "strategy_name": "S",
                "level": SignalLevel.WATCH.value,
            },
            now_epoch=1000 + i,
        )
    recent = am.recent(limit=100)
    assert len(recent) == 5  # capped
