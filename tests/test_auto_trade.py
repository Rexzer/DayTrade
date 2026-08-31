"""Tests: auto-trade scheduling helpers (pure)."""

from execution_engine import (
    SCAN_INTERVAL_SECONDS,
    AutoTradeConfig,
    interval_options,
    interval_seconds,
    is_valid_interval_seconds,
    label_for_seconds,
    recommend_for_strategy,
    should_scan,
)


def test_interval_lookups_roundtrip():
    assert interval_seconds("15m") == 900
    assert interval_seconds("1h") == 3600
    assert interval_seconds("nope") is None
    assert label_for_seconds(900) == "15m"
    assert label_for_seconds(12345) is None
    assert is_valid_interval_seconds(3600) is True
    assert is_valid_interval_seconds(999) is False


def test_interval_options_shape():
    opts = interval_options()
    assert {o["label"] for o in opts} == set(SCAN_INTERVAL_SECONDS)
    assert all(o["seconds"] == SCAN_INTERVAL_SECONDS[o["label"]] for o in opts)


def test_should_scan_first_scan_always_allowed():
    assert should_scan(now=1000.0, last_scan_epoch=None, interval_seconds=900) is True


def test_should_scan_respects_interval():
    # Not enough time elapsed.
    assert should_scan(now=1000.0, last_scan_epoch=900.0, interval_seconds=900) is False
    # Exactly the interval elapsed -> allowed.
    assert should_scan(now=1800.0, last_scan_epoch=900.0, interval_seconds=900) is True
    # Well past the interval.
    assert should_scan(now=5000.0, last_scan_epoch=900.0, interval_seconds=900) is True


def test_recommend_for_each_builtin_strategy():
    expected = {
        "trend_following": "1h",
        "ema_pullback": "15m",
        "breakout_retest": "15m",
        "sr_reversal": "15m",
        "mtf_confluence": "5m",
    }
    for key, rec_label in expected.items():
        rec = recommend_for_strategy(key)
        assert rec["recommended"] == rec_label
        assert rec["recommended_seconds"] == interval_seconds(rec_label)
        assert rec["rationale"]  # non-empty explanation


def test_recommend_fallback_uses_smallest_suitable_timeframe():
    # Unknown/custom strategy -> smallest offered suitable timeframe wins.
    rec = recommend_for_strategy("my_custom", suitable_timeframes=("1h", "15m"))
    assert rec["recommended"] == "15m"
    # No hint at all -> safe default.
    rec2 = recommend_for_strategy("bare_custom")
    assert rec2["recommended"] == "15m"


def test_auto_trade_config_defaults_and_serialisation():
    cfg = AutoTradeConfig()
    assert cfg.enabled is False  # disabled by default (restart-safe)
    assert cfg.strategy_key is None  # None = best across all strategies
    d = cfg.to_dict()
    assert d["interval_label"] == label_for_seconds(cfg.interval_seconds)
    assert d["enabled"] is False
