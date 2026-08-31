"""Tests: operator authorization for dangerous live endpoints."""

from backend.app.core.authz import check_operator_authorization
from backend.app.core.security import create_access_token

SECRET = "test-secret-not-for-production"


def test_operator_token_match():
    ok, reason = check_operator_authorization(
        "s3cr3t", None, configured_token="s3cr3t", secret_key=SECRET
    )
    assert ok and reason == "operator-token"


def test_operator_token_mismatch_denied():
    ok, _ = check_operator_authorization("wrong", None, configured_token="s3cr3t", secret_key=None)
    assert ok is False


def test_valid_jwt_accepted():
    token = create_access_token("operator@local", SECRET, expires_in_seconds=60)
    ok, reason = check_operator_authorization(None, token, configured_token=None, secret_key=SECRET)
    assert ok and reason == "jwt"


def test_invalid_jwt_denied():
    ok, _ = check_operator_authorization(
        None, "not.a.jwt", configured_token=None, secret_key=SECRET
    )
    assert ok is False


def test_fails_closed_when_nothing_configured():
    ok, reason = check_operator_authorization(
        "anything", "anything", configured_token=None, secret_key=None
    )
    assert ok is False
    assert "locked" in reason


def test_token_falls_back_to_jwt_when_token_wrong():
    token = create_access_token("op", SECRET)
    ok, reason = check_operator_authorization(
        "wrong-token", token, configured_token="right-token", secret_key=SECRET
    )
    assert ok and reason == "jwt"
