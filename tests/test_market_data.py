"""Tests: null market-data provider never fabricates prices."""

from market_data import NullMarketDataProvider, Timeframe
from market_data.provider import PriceSnapshot


def test_provider_reports_disconnected():
    p = NullMarketDataProvider()
    assert p.is_connected() is False


def test_snapshot_has_no_prices():
    p = NullMarketDataProvider()
    snap = p.get_snapshot("XAUUSD")
    assert snap.connected is False
    assert snap.bid is None
    assert snap.ask is None
    assert snap.last is None
    assert snap.spread is None


def test_no_candles_when_disconnected():
    p = NullMarketDataProvider()
    assert p.get_candles("XAUUSD", Timeframe.M15) == []


def test_supported_timeframes_full_set():
    p = NullMarketDataProvider()
    tfs = {tf.value for tf in p.supported_timeframes()}
    assert tfs == {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


def test_spread_computed_only_with_both_sides():
    with_prices = PriceSnapshot(symbol="XAUUSD", connected=True, bid=2000.0, ask=2000.5)
    assert with_prices.spread == 0.5
    missing = PriceSnapshot(symbol="XAUUSD", connected=True, bid=2000.0, ask=None)
    assert missing.spread is None


def test_snapshot_dict_shape():
    d = NullMarketDataProvider().get_snapshot("XAUUSD").to_dict()
    for key in ("symbol", "connected", "bid", "ask", "last", "spread", "source"):
        assert key in d
