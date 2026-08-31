"""Tests: risk settings validation and transparent position sizing."""

import pytest

from risk_engine import RiskEngine, RiskSettings


def test_default_settings_are_valid():
    assert RiskSettings().is_valid


def test_invalid_risk_pct_flagged():
    s = RiskSettings(risk_per_trade_pct=0)
    errors = s.validate()
    assert any("risk_per_trade_pct" in e for e in errors)


def test_weekly_must_be_at_least_daily():
    s = RiskSettings(max_daily_loss_pct=5.0, max_weekly_loss_pct=3.0)
    assert any("max_weekly_loss_pct" in e for e in s.validate())


def test_position_size_calculation_and_cap():
    engine = RiskEngine(RiskSettings(risk_per_trade_pct=1.0, max_lot_size=1.0))
    # 10,000 * 1% = 100 risk. Stop 100 pts * 1.0/pt = 100 per lot -> 1.0 lot.
    result = engine.position_size(
        account_balance=10_000, stop_distance_points=100, value_per_point_per_lot=1.0
    )
    assert result.risk_amount == pytest.approx(100.0)
    assert result.raw_lots == pytest.approx(1.0)
    assert result.capped_lots == pytest.approx(1.0)
    assert "Lots =" in result.explanation


def test_position_size_respects_max_lot_cap():
    engine = RiskEngine(RiskSettings(risk_per_trade_pct=5.0, max_lot_size=1.0))
    result = engine.position_size(
        account_balance=10_000, stop_distance_points=50, value_per_point_per_lot=1.0
    )
    # raw would be 500/50 = 10 lots, capped to 1.0.
    assert result.raw_lots == pytest.approx(10.0)
    assert result.capped_lots == pytest.approx(1.0)


def test_position_size_rejects_bad_inputs():
    engine = RiskEngine()
    with pytest.raises(ValueError):
        engine.position_size(0, 100, 1.0)
    with pytest.raises(ValueError):
        engine.position_size(10_000, 0, 1.0)
    with pytest.raises(ValueError):
        engine.position_size(10_000, 100, 0)


def test_pre_trade_spread_failsafe():
    engine = RiskEngine(RiskSettings(max_spread_points=50))
    assert engine.pre_trade_check(current_spread_points=40).allowed is True
    blocked = engine.pre_trade_check(current_spread_points=80)
    assert blocked.allowed is False
    assert blocked.reasons
