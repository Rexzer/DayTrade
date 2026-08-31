"""Tests: Tick price/spread derivation (no fabricated values)."""

from market_data.tick import Tick


def test_spread_from_bid_ask():
    t = Tick("XAUUSD", 100.0, bid=2400.0, ask=2400.5)
    assert t.spread == 0.5


def test_spread_none_when_incomplete():
    assert Tick("XAUUSD", 100.0, bid=2400.0).spread is None
    assert Tick("XAUUSD", 100.0, ask=2400.0).spread is None


def test_price_prefers_last():
    t = Tick("XAUUSD", 100.0, bid=2400.0, ask=2401.0, last=2400.7)
    assert t.price == 2400.7


def test_price_midpoint_when_no_last():
    t = Tick("XAUUSD", 100.0, bid=2400.0, ask=2401.0)
    assert t.price == 2400.5


def test_price_single_side_fallback():
    assert Tick("XAUUSD", 100.0, bid=2400.0).price == 2400.0
    assert Tick("XAUUSD", 100.0, ask=2401.0).price == 2401.0


def test_price_none_when_empty():
    assert Tick("XAUUSD", 100.0).price is None


def test_to_dict_shape():
    d = Tick("XAUUSD", 100.0, bid=1.0, ask=2.0, source="simulated").to_dict()
    for key in ("symbol", "timestamp_epoch", "bid", "ask", "spread", "price", "source"):
        assert key in d
    assert d["source"] == "simulated"
