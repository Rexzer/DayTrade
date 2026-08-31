"""Tests: password hashing and HS256 JWT (pure stdlib implementation)."""

import pytest

from backend.app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-key-not-for-production"


def test_password_hash_is_not_plaintext():
    hashed = hash_password("hunter2password")
    assert "hunter2password" not in hashed
    assert hashed.startswith("pbkdf2_sha256$")


def test_password_verifies():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_hashes_are_salted_and_unique():
    a = hash_password("samepassword123")
    b = hash_password("samepassword123")
    assert a != b  # different salt each time
    assert verify_password("samepassword123", a)
    assert verify_password("samepassword123", b)


def test_verify_handles_malformed_hash():
    assert verify_password("x", "not-a-valid-hash") is False


def test_jwt_round_trip():
    token = create_access_token("user@example.com", SECRET, expires_in_seconds=60)
    claims = decode_access_token(token, SECRET)
    assert claims["sub"] == "user@example.com"
    assert "exp" in claims and "iat" in claims


def test_jwt_rejects_wrong_secret():
    token = create_access_token("user@example.com", SECRET)
    with pytest.raises(TokenError):
        decode_access_token(token, "different-secret")


def test_jwt_rejects_expired():
    # Issue a token that expired in the past using injected clock.
    token = create_access_token("user@example.com", SECRET, expires_in_seconds=10, now_epoch=1000)
    with pytest.raises(TokenError):
        decode_access_token(token, SECRET, now_epoch=2000)


def test_jwt_rejects_malformed():
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt.token", SECRET)


def test_create_token_requires_secret():
    with pytest.raises(ValueError):
        create_access_token("x", "")
