"""Tests: config safety invariants + strategy registry emptiness."""

import importlib

from strategy_engine import SignalLevel, registry
from strategy_engine.strategy import MarketRegime, Signal


def _fresh_settings(monkeypatch, **env):
    # Reset cached settings and rebuild from a controlled environment.
    import backend.app.config as config

    for key in [
        "APP_ENV",
        "ENABLE_LIVE_TRADING",
        "ENABLE_PAPER_TRADING",
        "SECRET_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    importlib.reload(config)
    return config.Settings()


def test_live_trading_default_off(monkeypatch):
    s = _fresh_settings(monkeypatch)
    assert s.enable_live_trading is False
    assert s.enable_paper_trading is False


def test_config_flags_live_trading_as_problem(monkeypatch):
    s = _fresh_settings(monkeypatch, ENABLE_LIVE_TRADING="true")
    problems = s.validate()
    assert any("ENABLE_LIVE_TRADING" in p for p in problems)


def test_production_requires_secret_key(monkeypatch):
    s = _fresh_settings(monkeypatch, APP_ENV="production", SECRET_KEY="")
    assert any("SECRET_KEY" in p for p in s.validate())


def test_strategy_registry_empty_in_phase_1():
    assert registry.is_empty() is True
    assert registry.all() == []


def test_signal_levels_distinguish_execution():
    # A confirmed setup is NOT an executed trade.
    assert SignalLevel.CONFIRMED_SETUP.value == 3
    assert SignalLevel.TRADE_EXECUTED.value == 4
    assert SignalLevel.CONFIRMED_SETUP is not SignalLevel.TRADE_EXECUTED


def test_signal_serialization_includes_reasoning_fields():
    sig = Signal(
        strategy_key="demo",
        level=SignalLevel.NO_SETUP,
        regime=MarketRegime.UNKNOWN,
        confirmations=("trend up",),
        missing_confirmations=("volume",),
        invalidation="close below X",
    )
    d = sig.to_dict()
    for key in ("confirmations", "missing_confirmations", "invalidation", "level_name"):
        assert key in d
    assert d["level_name"] == "NO_SETUP"
