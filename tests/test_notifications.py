"""Tests: notification config + dispatcher."""

from notifications import NotificationConfig, NotificationDispatcher


def test_default_config_events():
    cfg = NotificationConfig()
    assert cfg.is_event_enabled("confirmed") is True
    assert cfg.is_event_enabled("risk_shutdown") is True
    assert cfg.is_event_enabled("watch") is False  # off by default


def test_default_channels():
    cfg = NotificationConfig()
    channels = cfg.enabled_channels()
    assert "browser" in channels and "sound" in channels
    assert "email" not in channels  # external channels off by default


def test_dispatch_skips_disabled_events():
    d = NotificationDispatcher(NotificationConfig())
    assert d.notify("watch", "t", "b") is None  # disabled by default


def test_dispatch_records_enabled_event():
    d = NotificationDispatcher(NotificationConfig())
    rec = d.notify("confirmed", "XAUUSD LONG", "confirmed setup")
    assert rec is not None
    assert "browser" in rec.channels
    assert d.recent()[0]["event_type"] == "confirmed"


def test_update_config_toggles():
    cfg = NotificationConfig()
    cfg.update(channels={"email": True}, events={"watch": True})
    assert "email" in cfg.enabled_channels()
    assert cfg.is_event_enabled("watch") is True


def test_registered_adapter_is_called():
    calls = []
    d = NotificationDispatcher(NotificationConfig())
    d.config.set_channel("email", True)
    d.register_adapter("email", lambda rec: calls.append(rec.event_type))
    d.notify("executed", "t", "b")
    assert calls == ["executed"]
