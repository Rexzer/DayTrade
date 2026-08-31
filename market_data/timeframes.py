"""Timeframe helpers (pure Python).

Bucketing is always computed in UTC. Because the Unix epoch (0) is UTC
midnight and every supported timeframe divides a UTC day evenly, flooring an
epoch to a timeframe bucket is a simple integer operation that yields
UTC-aligned candle open times.
"""

from __future__ import annotations

from market_data.provider import Timeframe

# Duration of each timeframe in seconds.
_DURATIONS: dict[Timeframe, int] = {
    Timeframe.M1: 60,
    Timeframe.M5: 5 * 60,
    Timeframe.M15: 15 * 60,
    Timeframe.M30: 30 * 60,
    Timeframe.H1: 60 * 60,
    Timeframe.H4: 4 * 60 * 60,
    Timeframe.D1: 24 * 60 * 60,
}


def duration_seconds(timeframe: Timeframe) -> int:
    """Return the length of one candle of ``timeframe`` in seconds."""
    return _DURATIONS[timeframe]


def floor_to_bucket(epoch: float, timeframe: Timeframe) -> int:
    """Return the UTC-aligned open time (epoch seconds) of the bucket holding ``epoch``.

    Example: an epoch at 10:07:33 UTC on a 5-minute timeframe floors to
    10:05:00 UTC.
    """
    dur = _DURATIONS[timeframe]
    return int(epoch // dur) * dur


def next_bucket(epoch: float, timeframe: Timeframe) -> int:
    """Return the open time of the bucket immediately after the one holding ``epoch``."""
    return floor_to_bucket(epoch, timeframe) + _DURATIONS[timeframe]


def bucket_close_epoch(bucket_open_epoch: int, timeframe: Timeframe) -> int:
    """Return the (exclusive) close time of the bucket that opened at ``bucket_open_epoch``."""
    return int(bucket_open_epoch) + _DURATIONS[timeframe]


def expected_bucket_starts(start_epoch: float, end_epoch: float, timeframe: Timeframe) -> list[int]:
    """Return every bucket open time in ``[start, end]`` inclusive (UTC-aligned).

    Used for gap detection / backfill: compare against the buckets actually
    present to find which candles are missing.
    """
    dur = _DURATIONS[timeframe]
    first = floor_to_bucket(start_epoch, timeframe)
    last = floor_to_bucket(end_epoch, timeframe)
    return list(range(first, last + 1, dur))
