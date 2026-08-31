"""Tests: feed health monitoring + signal gating on stale data."""

from backend.app.core.status import DataStatus
from market_data.health import FeedHealthMonitor


def test_no_data_is_disconnected_and_signals_blocked():
    m = FeedHealthMonitor()
    assert m.status(now_epoch=1000) is DataStatus.DISCONNECTED
    assert m.signals_allowed(now_epoch=1000) is False


def test_fresh_data_is_live_and_signals_allowed():
    m = FeedHealthMonitor(delayed_after_seconds=3, stale_after_seconds=10)
    m.mark_update(1000)
    assert m.status(now_epoch=1001) is DataStatus.LIVE
    assert m.signals_allowed(now_epoch=1001) is True


def test_delayed_still_allows_signals():
    m = FeedHealthMonitor(delayed_after_seconds=3, stale_after_seconds=10)
    m.mark_update(1000)
    assert m.status(now_epoch=1005) is DataStatus.DELAYED
    assert m.signals_allowed(now_epoch=1005) is True


def test_stale_blocks_signals():
    m = FeedHealthMonitor(delayed_after_seconds=3, stale_after_seconds=10)
    m.mark_update(1000)
    assert m.status(now_epoch=1020) is DataStatus.STALE
    assert m.signals_allowed(now_epoch=1020) is False


def test_reset_forgets_last_update():
    m = FeedHealthMonitor()
    m.mark_update(1000)
    m.reset()
    assert m.status(now_epoch=1001) is DataStatus.DISCONNECTED


def test_out_of_order_update_does_not_look_fresher():
    m = FeedHealthMonitor(stale_after_seconds=10)
    m.mark_update(1000)
    m.mark_update(990)  # older; must be ignored
    assert m.age_seconds(now_epoch=1005) == 5


def test_health_dict_shape():
    m = FeedHealthMonitor(source="simulated")
    m.mark_update(1000)
    d = m.health(now_epoch=1001).to_dict()
    for key in ("status", "last_update_epoch", "age_seconds", "signals_allowed", "source"):
        assert key in d
    assert d["source"] == "simulated"
