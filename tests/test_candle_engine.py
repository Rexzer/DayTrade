"""Tests: candle aggregation — the core of the market-data engine."""

from market_data.candle_engine import CandleAggregator
from market_data.provider import Candle, Timeframe
from market_data.tick import Tick


def _tick(ts, price, vol=1.0):
    return Tick("XAUUSD", ts, last=price, volume=vol)


def test_single_bucket_ohlc():
    agg = CandleAggregator(Timeframe.M1)
    agg.add_tick(_tick(0, 2400.0))
    agg.add_tick(_tick(10, 2405.0))
    agg.add_tick(_tick(20, 2395.0))
    agg.add_tick(_tick(59, 2402.0))
    c = agg.current()
    assert c is not None
    assert (c.open, c.high, c.low, c.close) == (2400.0, 2405.0, 2395.0, 2402.0)
    assert c.volume == 4.0


def test_new_bucket_closes_previous():
    agg = CandleAggregator(Timeframe.M1)
    agg.add_tick(_tick(0, 2400.0))
    result = agg.add_tick(_tick(60, 2410.0))  # next minute
    assert result.opened_new_bucket is True
    assert result.closed_candle is not None
    assert result.closed_candle.close == 2400.0
    assert len(agg.candles()) == 2


def test_exact_duplicate_ignored():
    agg = CandleAggregator(Timeframe.M1)
    t = _tick(5, 2400.0)
    assert agg.add_tick(t).accepted is True
    assert agg.add_tick(t).accepted is False  # identical -> rejected
    assert agg.duplicate_count == 1


def test_no_price_tick_rejected():
    agg = CandleAggregator(Timeframe.M1)
    res = agg.add_tick(Tick("XAUUSD", 5))  # no bid/ask/last
    assert res.accepted is False
    assert res.reason == "no_price"
    assert agg.no_price_count == 1


def test_out_of_order_updates_prior_bucket_without_moving_open():
    agg = CandleAggregator(Timeframe.M1)
    agg.add_tick(_tick(0, 2400.0))
    agg.add_tick(_tick(60, 2410.0))  # advance to minute 2
    # Late tick for minute 1 with a new high; must widen high, keep open/close.
    res = agg.add_tick(_tick(30, 2450.0))
    assert res.reason == "out_of_order"
    assert agg.out_of_order_count == 1
    first = agg.candles()[0]
    assert first.open == 2400.0  # unchanged
    assert first.high == 2450.0  # widened
    assert first.close == 2400.0  # unchanged


def test_missing_buckets_detects_gaps():
    agg = CandleAggregator(Timeframe.M1)
    agg.add_tick(_tick(0, 2400.0))
    agg.add_tick(_tick(180, 2400.0))  # jump to minute 3, skipping 1 and 2
    missing = agg.missing_buckets(0, 180)
    assert 60 in missing and 120 in missing
    assert 0 not in missing and 180 not in missing


def test_seed_and_closed_candles():
    seed = [
        Candle(Timeframe.M1, 0.0, 1, 2, 0.5, 1.5, 10),
        Candle(Timeframe.M1, 60.0, 1.5, 2.5, 1, 2, 12),
    ]
    agg = CandleAggregator(Timeframe.M1)
    agg.seed(seed)
    assert len(agg.candles()) == 2
    # Current bucket is the newest seeded one; closed excludes it.
    assert len(agg.closed_candles()) == 1
    # A new tick in a later bucket closes the seeded current one.
    res = agg.add_tick(_tick(120, 3.0))
    assert res.closed_candle is not None
    assert res.closed_candle.open_time_epoch == 60.0


def test_seed_rejects_wrong_timeframe():
    agg = CandleAggregator(Timeframe.M5)
    try:
        agg.seed([Candle(Timeframe.M1, 0.0, 1, 1, 1, 1)])
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_midpoint_price_used_when_no_last():
    agg = CandleAggregator(Timeframe.M1)
    agg.add_tick(Tick("XAUUSD", 0, bid=2400.0, ask=2401.0))  # mid 2400.5
    assert agg.current().open == 2400.5
