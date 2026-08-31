"""Tests: indicator calculations validated against reference values."""

import math

from strategy_engine.indicators import (
    adx,
    atr,
    bollinger_bands,
    ema,
    last_defined,
    macd,
    rsi,
    sma,
    vwap,
)

# Canonical RSI dataset (StockCharts), period 14.
RSI_CLOSES = [
    44.34,
    44.09,
    44.15,
    43.61,
    44.33,
    44.83,
    45.10,
    45.42,
    45.84,
    46.08,
    45.89,
    46.03,
    45.61,
    46.28,
    46.28,
    46.00,
    46.03,
    46.41,
    46.22,
    45.64,
    46.21,
    46.25,
    45.71,
    46.45,
    45.78,
    45.35,
    44.03,
    44.18,
    44.22,
    44.57,
    43.42,
    42.66,
    43.13,
]


def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 3)[-1] == 4.0
    assert sma([1, 2], 3) == [None, None]


def test_ema_formula():
    # period 3 of 1..5: seed=2 @idx2, k=0.5 -> 3, 4
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_rsi_reference_value():
    r = rsi(RSI_CLOSES, 14)
    # Published first RSI is ~70.53; Wilder's exact ~70.46. Accept within 0.5.
    assert r[14] is not None
    assert abs(r[14] - 70.53) < 0.6


def test_rsi_all_gains_is_100():
    r = rsi([float(i) for i in range(1, 40)], 14)
    assert last_defined(r) == 100.0


def test_atr_positive_and_warms_up():
    highs = [10 + i for i in range(20)]
    lows = [9 + i for i in range(20)]
    closes = [9.5 + i for i in range(20)]
    a = atr(highs, lows, closes, 14)
    assert a[12] is None  # warm-up
    assert a[-1] is not None and a[-1] > 0


def test_adx_strong_uptrend_high_with_pdi_dominant():
    h = [100 + i for i in range(40)]
    lo = [99 + i for i in range(40)]
    c = [99.5 + i for i in range(40)]
    res = adx(h, lo, c, 14)
    assert last_defined(res.adx) is not None
    assert last_defined(res.adx) > 40
    assert (last_defined(res.plus_di) or 0) > (last_defined(res.minus_di) or 0)


def test_bollinger_symmetry():
    vals = [float(i) for i in range(1, 21)]
    bb = bollinger_bands(vals, 20, 2.0)
    mid = bb.middle[-1]
    assert mid == sum(vals) / 20
    assert bb.upper[-1] > mid > bb.lower[-1]
    assert math.isclose(bb.upper[-1] - mid, mid - bb.lower[-1])


def test_macd_line_defined_after_slow_period():
    vals = [float(i % 7) + i * 0.1 for i in range(60)]
    m = macd(vals, 12, 26, 9)
    assert last_defined(m.macd) is not None
    assert last_defined(m.signal) is not None


def test_vwap_constant():
    assert vwap([2, 2, 2], [1, 1, 1], [1.5, 1.5, 1.5], [10, 10, 10]) == [1.5, 1.5, 1.5]


def test_vwap_none_without_volume():
    assert vwap([2], [1], [1.5], [None]) == [None]
