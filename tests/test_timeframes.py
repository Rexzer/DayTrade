"""Tests: UTC-aligned timeframe bucketing."""

from datetime import datetime, timezone

from market_data.provider import Timeframe
from market_data.timeframes import (
    bucket_close_epoch,
    duration_seconds,
    expected_bucket_starts,
    floor_to_bucket,
    next_bucket,
)


def _epoch(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp()


def test_durations():
    assert duration_seconds(Timeframe.M1) == 60
    assert duration_seconds(Timeframe.M15) == 900
    assert duration_seconds(Timeframe.H1) == 3600
    assert duration_seconds(Timeframe.H4) == 14400
    assert duration_seconds(Timeframe.D1) == 86400


def test_floor_aligns_to_utc_5m():
    # 10:07:33 UTC on a 5-minute frame -> 10:05:00 UTC
    ts = _epoch(2026, 1, 15, 10, 7, 33)
    floored = floor_to_bucket(ts, Timeframe.M15)
    dt = datetime.fromtimestamp(floored, tz=timezone.utc)
    assert (dt.hour, dt.minute, dt.second) == (10, 0, 0)


def test_floor_daily_aligns_to_utc_midnight():
    ts = _epoch(2026, 3, 9, 14, 30, 0)
    floored = floor_to_bucket(ts, Timeframe.D1)
    dt = datetime.fromtimestamp(floored, tz=timezone.utc)
    assert (dt.hour, dt.minute, dt.second) == (0, 0, 0)
    assert (dt.year, dt.month, dt.day) == (2026, 3, 9)


def test_h4_buckets_align_to_0_4_8():
    ts = _epoch(2026, 1, 1, 9, 15, 0)  # 09:15 -> bucket 08:00
    dt = datetime.fromtimestamp(floor_to_bucket(ts, Timeframe.H4), tz=timezone.utc)
    assert dt.hour == 8


def test_next_and_close():
    ts = _epoch(2026, 1, 1, 0, 0, 30)
    assert next_bucket(ts, Timeframe.M1) == floor_to_bucket(ts, Timeframe.M1) + 60
    b = floor_to_bucket(ts, Timeframe.M5)
    assert bucket_close_epoch(b, Timeframe.M5) == b + 300


def test_expected_bucket_starts_contiguous():
    start = _epoch(2026, 1, 1, 0, 0, 0)
    end = _epoch(2026, 1, 1, 0, 4, 0)  # inclusive of 00:04 bucket
    buckets = expected_bucket_starts(start, end, Timeframe.M1)
    assert len(buckets) == 5
    assert all(buckets[i + 1] - buckets[i] == 60 for i in range(len(buckets) - 1))
