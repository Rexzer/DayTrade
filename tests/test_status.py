"""Tests for connection/data status classification."""

from backend.app.core.status import (
    ConnectionHealth,
    ConnectionStatus,
    DataStatus,
    classify_data_freshness,
)


def test_no_update_is_disconnected():
    assert classify_data_freshness(None) is DataStatus.DISCONNECTED


def test_recent_update_is_live():
    now = 1000.0
    assert classify_data_freshness(now - 1.0, now) is DataStatus.LIVE


def test_slightly_old_is_delayed():
    now = 1000.0
    assert classify_data_freshness(now - 5.0, now) is DataStatus.DELAYED


def test_old_is_stale():
    now = 1000.0
    assert classify_data_freshness(now - 60.0, now) is DataStatus.STALE


def test_boundaries_are_inclusive_for_live_and_delayed():
    now = 1000.0
    assert classify_data_freshness(now - 2.0, now, delayed_after_seconds=2.0) is DataStatus.LIVE
    assert classify_data_freshness(now - 10.0, now, stale_after_seconds=10.0) is DataStatus.DELAYED


def test_future_timestamp_is_treated_conservatively():
    now = 1000.0
    assert classify_data_freshness(now + 5.0, now) is DataStatus.DELAYED


def test_connection_health_serializes():
    health = ConnectionHealth(name="market_data", status=ConnectionStatus.DISCONNECTED)
    d = health.to_dict()
    assert d["name"] == "market_data"
    assert d["status"] == "disconnected"


def test_connection_status_values():
    assert ConnectionStatus.CONNECTED.value == "connected"
    assert {s.value for s in ConnectionStatus} == {
        "connected",
        "connecting",
        "disconnected",
        "stale",
        "error",
    }
