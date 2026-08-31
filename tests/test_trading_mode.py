"""Safety-critical tests: LIVE TRADING CANNOT BE ACTIVATED in Phase 1."""

import pytest

from backend.app.core.trading_mode import (
    ModeAvailability,
    ModeTransitionError,
    TradingMode,
    TradingModeManager,
)


def test_default_mode_is_analysis_only():
    mgr = TradingModeManager()
    assert mgr.current is TradingMode.ANALYSIS_ONLY
    assert mgr.is_live_trading_active() is False


def test_analysis_only_is_enabled():
    mgr = TradingModeManager()
    assert mgr.is_enabled(TradingMode.ANALYSIS_ONLY) is True


def test_paper_and_live_are_locked():
    mgr = TradingModeManager()
    assert mgr.is_enabled(TradingMode.PAPER_TRADING) is False
    assert mgr.is_enabled(TradingMode.LIVE_TRADING) is False


def test_cannot_switch_to_live_trading():
    mgr = TradingModeManager()
    with pytest.raises(ModeTransitionError):
        mgr.set_mode(TradingMode.LIVE_TRADING)
    # State is unchanged after a rejected transition.
    assert mgr.current is TradingMode.ANALYSIS_ONLY
    assert mgr.is_live_trading_active() is False


def test_cannot_switch_to_paper_trading():
    mgr = TradingModeManager()
    with pytest.raises(ModeTransitionError):
        mgr.set_mode(TradingMode.PAPER_TRADING)
    assert mgr.current is TradingMode.ANALYSIS_ONLY


def test_setting_analysis_only_is_idempotent():
    mgr = TradingModeManager()
    assert mgr.set_mode(TradingMode.ANALYSIS_ONLY) is TradingMode.ANALYSIS_ONLY


def test_status_dicts_report_locks_with_reasons():
    mgr = TradingModeManager()
    by_mode = {d["mode"]: d for d in mgr.status_dicts()}
    assert by_mode["analysis_only"]["availability"] == "enabled"
    assert by_mode["analysis_only"]["active"] is True
    assert by_mode["paper_trading"]["availability"] == "locked"
    assert by_mode["live_trading"]["availability"] == "locked"
    # Locked modes must explain why.
    assert by_mode["live_trading"]["reason"]


def test_unknown_mode_raises():
    mgr = TradingModeManager()
    with pytest.raises(ModeTransitionError):
        mgr.set_mode("something_else")  # type: ignore[arg-type]


def test_even_if_availability_tampered_default_start_is_analysis():
    # Sanity: a manager constructed with everything enabled still STARTS in
    # analysis-only (defence in depth for the default state).
    everything_on = {m: ModeAvailability.ENABLED for m in TradingMode}
    mgr = TradingModeManager(availability=everything_on)
    assert mgr.current is TradingMode.ANALYSIS_ONLY
