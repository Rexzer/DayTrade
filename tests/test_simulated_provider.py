"""Tests: simulated provider is labelled, deterministic, and honest offline."""

from market_data.provider import Timeframe
from market_data.simulated_provider import SimulatedMarketDataProvider


def test_name_and_source_are_labelled_simulated():
    p = SimulatedMarketDataProvider()
    assert p.name == "simulated"
    p.connect()
    tick = p.generate_tick(1000.0)
    assert tick.source == "simulated"
    assert p.get_snapshot("XAUUSD").source == "simulated"


def test_disconnected_snapshot_has_no_prices():
    p = SimulatedMarketDataProvider()
    snap = p.get_snapshot("XAUUSD")  # not connected yet
    assert snap.connected is False
    assert snap.bid is None and snap.ask is None and snap.last is None


def test_no_history_when_disconnected():
    p = SimulatedMarketDataProvider()
    assert p.get_historical_candles("XAUUSD", Timeframe.M5, limit=10) == []


def test_history_is_contiguous_and_deterministic():
    a = SimulatedMarketDataProvider(seed=42)
    a.connect()
    b = SimulatedMarketDataProvider(seed=42)
    b.connect()
    ha = a.get_historical_candles("XAUUSD", Timeframe.M5, limit=20)
    hb = b.get_historical_candles("XAUUSD", Timeframe.M5, limit=20)
    assert len(ha) == 20
    # Deterministic given the same seed/params.
    assert [c.close for c in ha] == [c.close for c in hb]
    # Each candle opens at the previous candle's close (contiguous series).
    assert all(abs(ha[i].close - ha[i + 1].open) < 1e-9 for i in range(len(ha) - 1))


def test_history_buckets_are_utc_aligned():
    p = SimulatedMarketDataProvider()
    p.connect()
    h = p.get_historical_candles("XAUUSD", Timeframe.M15, limit=5, end_epoch=1_700_000_000)
    dur = 15 * 60
    assert all(int(c.open_time_epoch) % dur == 0 for c in h)


def test_ticks_have_bid_ask_spread():
    p = SimulatedMarketDataProvider(spread=0.4)
    p.connect()
    t = p.generate_tick(1000.0)
    assert t.bid is not None and t.ask is not None
    assert t.ask > t.bid
    assert abs(t.spread - 0.4) < 0.05
