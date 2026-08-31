"""Tests: market-regime detection and structure analysis."""

from strategy_engine.regime import RegimeDetector
from strategy_engine.strategy import MarketRegime
from strategy_engine.structure import analyze_structure, support_resistance, swing_points
from tests.helpers import downtrend, flat, make_candles, uptrend


def test_insufficient_data_is_unknown():
    r = RegimeDetector().detect(make_candles([2000, 2001, 2002]))
    assert r.regime is MarketRegime.UNKNOWN


def test_strong_uptrend_classified_bullish():
    r = RegimeDetector().detect(uptrend(120, step=3.0))
    assert r.trend == "bullish"
    assert r.regime in (
        MarketRegime.STRONG_BULLISH,
        MarketRegime.BREAKOUT,
        MarketRegime.WEAK_BULLISH,
    )


def test_strong_downtrend_classified_bearish():
    r = RegimeDetector().detect(downtrend(120, step=3.0))
    assert r.trend == "bearish"
    assert r.regime in (
        MarketRegime.STRONG_BEARISH,
        MarketRegime.BREAKOUT,
        MarketRegime.WEAK_BEARISH,
    )


def test_flat_market_not_a_strong_trend():
    r = RegimeDetector().detect(flat(120, wobble=0.5))
    # A choppy flat market must not be classified as a strong trend/breakout.
    assert r.regime not in (
        MarketRegime.STRONG_BULLISH,
        MarketRegime.STRONG_BEARISH,
        MarketRegime.BREAKOUT,
    )


def test_regime_details_are_transparent():
    r = RegimeDetector().detect(uptrend(120))
    for key in ("ema20", "ema50", "adx", "atr", "structure_trend"):
        assert key in r.details


def test_swing_points_detected():
    # Distinct zig-zag highs and lows so fractals are unambiguous.
    highs = [10, 13, 11, 15, 12, 17, 10]
    lows = [8, 9, 6, 10, 7, 12, 5]
    pts = swing_points(highs, lows, 1, 1)
    assert any(p.kind == "high" for p in pts)
    assert any(p.kind == "low" for p in pts)


def test_structure_bullish_when_hh_hl():
    highs = [10, 12, 11, 14, 13, 16, 15]
    lows = [8, 9, 8.5, 11, 10.5, 13, 12]
    s = analyze_structure(highs, lows, 1, 1)
    assert s.trend == "bullish"


def test_support_resistance_clusters():
    # Highs peak at odd indices, lows trough at even indices (distinct bars).
    highs = [10, 12, 10, 12, 10, 12, 10]
    lows = [7, 9, 6, 9, 6, 9, 7]
    levels = support_resistance(highs, lows, left=1, right=1)
    kinds = {level.kind for level in levels}
    assert "resistance" in kinds and "support" in kinds
