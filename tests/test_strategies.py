"""Tests: the five built-in strategies produce explainable, safe signals."""

import pytest

from strategy_engine.strategies import build_builtin_strategies
from strategy_engine.strategies.breakout_retest import BreakoutRetestStrategy
from strategy_engine.strategies.trend_following import TrendFollowingStrategy
from strategy_engine.strategy import MarketContext, SignalLevel
from tests.helpers import make_candles, uptrend


def _mtf_context(builder=uptrend):
    return MarketContext(
        symbol="XAUUSD",
        candles={
            "4h": builder(120),
            "1h": builder(120),
            "15m": builder(120),
            "5m": builder(120),
        },
        now_epoch=1_700_000_000,
    )


def test_all_five_strategies_registered():
    strategies = build_builtin_strategies()
    keys = {s.key for s in strategies}
    assert keys == {
        "trend_following",
        "ema_pullback",
        "breakout_retest",
        "sr_reversal",
        "mtf_confluence",
    }


def test_metadata_documents_conditions():
    for s in build_builtin_strategies():
        md = s.metadata.to_dict()
        assert md["entry_conditions"], f"{s.key} missing entry_conditions"
        assert md["stop_loss_logic"]
        assert md["invalidation_logic"]
        assert md["is_builtin"] is True


def test_strategies_never_emit_trade_executed():
    ctx = _mtf_context()
    for s in build_builtin_strategies():
        sig = s.evaluate(ctx)
        # Strategies classify setups only; execution level is forbidden here.
        assert sig.level != SignalLevel.TRADE_EXECUTED
        assert sig.level.value <= SignalLevel.CONFIRMED_SETUP.value


def test_signals_explain_themselves():
    ctx = _mtf_context()
    for s in build_builtin_strategies():
        sig = s.evaluate(ctx)
        # Transparent reasoning: an actionable signal lists its conditions; a
        # NO_SETUP must still explain itself with a note.
        total = len(sig.confirmations) + len(sig.missing_confirmations)
        if sig.level is SignalLevel.NO_SETUP:
            assert sig.notes, f"{s.key} NO_SETUP without explanation"
        else:
            assert total >= 1, f"{s.key} produced no explainable conditions"


def test_insufficient_data_returns_no_setup():
    tiny = MarketContext(candles={"1h": make_candles([2000, 2001, 2002])})
    sig = TrendFollowingStrategy().evaluate(tiny)
    assert sig.level is SignalLevel.NO_SETUP
    assert sig.entry_zone is None  # no fabricated prices without a setup


def test_trend_following_goes_long_in_uptrend():
    ctx = _mtf_context(uptrend)
    sig = TrendFollowingStrategy().evaluate(ctx)
    assert sig.direction == "long"
    assert sig.confidence_score is not None


def test_confirmed_setup_has_prices_and_rr():
    ctx = _mtf_context(uptrend)
    sig = TrendFollowingStrategy().evaluate(ctx)
    if sig.level.value >= SignalLevel.POTENTIAL_SETUP.value:
        assert sig.entry_zone is not None
        assert sig.stop_loss is not None
        assert sig.take_profits
        assert sig.risk_reward is not None


def test_breakout_needs_a_break():
    # A perfectly flat market should not produce a breakout setup.
    flat_ctx = MarketContext(candles={"15m": make_candles([2000.0] * 60)})
    sig = BreakoutRetestStrategy().evaluate(flat_ctx)
    assert sig.level is SignalLevel.NO_SETUP


@pytest.mark.parametrize("strategy", build_builtin_strategies())
def test_every_strategy_runs_without_error(strategy):
    ctx = _mtf_context()
    sig = strategy.evaluate(ctx)
    assert sig.strategy_key == strategy.key
