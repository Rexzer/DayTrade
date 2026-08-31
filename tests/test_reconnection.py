"""Tests: reconnection state machine + backfill planning."""

from market_data.reconnection import (
    ConnectionState,
    ReconnectionController,
    plan_backfill,
)


def test_initial_connect_flow_to_live():
    c = ReconnectionController()
    assert c.state is ConnectionState.DISCONNECTED
    c.begin_connect()
    assert c.state is ConnectionState.CONNECTING
    c.on_connected()  # not a reconnect
    assert c.state is ConnectionState.CONNECTED
    c.mark_live()
    assert c.is_live() is True


def test_reconnect_forces_backfill_before_live():
    c = ReconnectionController()
    c.begin_connect()
    c.on_connected()
    c.mark_live()
    # Drop and reconnect.
    c.on_disconnected()
    assert c.state is ConnectionState.DISCONNECTED
    wait = c.begin_reconnect()
    assert c.state is ConnectionState.RECONNECTING
    assert wait >= 1.0
    c.on_connected()  # was reconnecting -> must go to BACKFILLING, not CONNECTED
    assert c.state is ConnectionState.BACKFILLING
    assert c.accepts_data() is False  # not live until backfill completes
    c.on_backfill_complete()
    assert c.state is ConnectionState.LIVE
    assert c.accepts_data() is True


def test_backoff_is_exponential_and_capped():
    c = ReconnectionController(base_backoff_seconds=1.0, max_backoff_seconds=8.0)
    waits = []
    for _ in range(5):
        waits.append(c.begin_reconnect())
        c.on_disconnected()
    # 1, 2, 4, 8, 8 (capped)
    assert waits[0] == 1.0
    assert waits[1] == 2.0
    assert waits[2] == 4.0
    assert waits[3] == 8.0
    assert waits[4] == 8.0


def test_backoff_resets_after_live():
    c = ReconnectionController()
    c.begin_reconnect()
    c.begin_reconnect()
    assert c.attempt == 2
    c.on_connected()
    c.on_backfill_complete()
    assert c.attempt == 0
    assert c.next_backoff_seconds() == 0.0


def test_plan_backfill_orders_and_dedupes():
    assert plan_backfill([180, 60, 60, 120]) == [60, 120, 180]


def test_not_live_while_disconnected():
    c = ReconnectionController()
    assert c.accepts_data() is False
    c.on_disconnected()
    assert c.accepts_data() is False
