"""Tests: live-execution authorization (explicit, restart-safe)."""

import pytest

from execution_engine import REQUIRED_CONFIRMATIONS, AuthorizationError, LiveAuthorization


def _confirm_all(auth: LiveAuthorization) -> None:
    for key in REQUIRED_CONFIRMATIONS:
        auth.confirm(key, True)


def test_default_is_not_authorized():
    auth = LiveAuthorization()
    assert auth.is_authorized() is False
    assert auth.config_enabled is False


def test_arm_fails_without_config_enabled():
    auth = LiveAuthorization(config_enabled=False)
    _confirm_all(auth)
    with pytest.raises(AuthorizationError):
        auth.arm()
    assert auth.is_authorized() is False


def test_arm_fails_with_missing_confirmations():
    auth = LiveAuthorization(config_enabled=True)
    auth.confirm("understand_losses", True)  # only one
    with pytest.raises(AuthorizationError):
        auth.arm()


def test_full_flow_authorizes():
    auth = LiveAuthorization(config_enabled=True)
    _confirm_all(auth)
    auth.arm()
    assert auth.is_authorized() is True


def test_unticking_confirmation_disarms():
    auth = LiveAuthorization(config_enabled=True)
    _confirm_all(auth)
    auth.arm()
    assert auth.is_authorized()
    auth.confirm("verified_mt5_account", False)
    assert auth.is_authorized() is False


def test_kill_switch_disarms_and_blocks_arm():
    auth = LiveAuthorization(config_enabled=True)
    _confirm_all(auth)
    auth.arm()
    auth.kill()
    assert auth.is_authorized() is False
    with pytest.raises(AuthorizationError):
        auth.arm()  # cannot re-arm while killed
    auth.clear_kill()
    auth.arm()
    assert auth.is_authorized() is True


def test_disabling_config_revokes_authorization():
    auth = LiveAuthorization(config_enabled=True)
    _confirm_all(auth)
    auth.arm()
    auth.set_config_enabled(False)
    assert auth.is_authorized() is False


def test_restart_safety_fresh_instance_is_disabled():
    # A new process => a new LiveAuthorization => disabled by default.
    assert LiveAuthorization(config_enabled=True).is_authorized() is False


def test_status_reports_all_fields():
    auth = LiveAuthorization(config_enabled=True)
    st = auth.status()
    for key in (
        "config_enabled",
        "confirmations",
        "all_confirmed",
        "armed",
        "killed",
        "authorized",
    ):
        assert key in st
    assert len(st["confirmations"]) == len(REQUIRED_CONFIRMATIONS)
