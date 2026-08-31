"""Security primitives (pure standard library).

Provides password hashing (PBKDF2-HMAC-SHA256) and minimal HS256 JWT
encode/verify without third-party dependencies, so the auth architecture is
testable in any environment. Secrets are never logged or embedded in code.

NOTE: This is a solid, dependency-free baseline suitable for Phase 1. In
production you may swap in argon2/bcrypt and a vetted JWT library; the
interface here is intentionally small to make that swap easy.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

# --- Password hashing --------------------------------------------------------

_PBKDF2_ROUNDS = 200_000
_SALT_BYTES = 16


def hash_password(password: str, *, rounds: int = _PBKDF2_ROUNDS) -> str:
    """Return a self-describing password hash: ``pbkdf2_sha256$rounds$salt$hash``."""
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return "pbkdf2_sha256${}${}${}".format(
        rounds,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a password against a stored hash."""
    try:
        scheme, rounds_s, salt_b64, hash_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(dk, expected)


# --- Minimal HS256 JWT -------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


class TokenError(Exception):
    """Raised when a token is invalid or expired."""


def create_access_token(
    subject: str,
    secret_key: str,
    *,
    expires_in_seconds: int = 3600,
    now_epoch: float | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Create a signed HS256 JWT for ``subject``."""
    if not secret_key:
        raise ValueError("secret_key must not be empty")
    now = int(time.time() if now_epoch is None else now_epoch)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "iat": now, "exp": now + expires_in_seconds}
    if extra_claims:
        payload.update(extra_claims)
    header_seg = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_seg = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_seg}.{payload_seg}".encode("ascii")
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_seg}.{payload_seg}.{_b64url_encode(signature)}"


def decode_access_token(
    token: str,
    secret_key: str,
    *,
    now_epoch: float | None = None,
) -> dict:
    """Verify signature and expiry; return the claims or raise ``TokenError``."""
    try:
        header_seg, payload_seg, signature_seg = token.split(".")
    except ValueError as exc:
        raise TokenError("Malformed token") from exc

    signing_input = f"{header_seg}.{payload_seg}".encode("ascii")
    expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        provided_sig = _b64url_decode(signature_seg)
    except Exception as exc:  # noqa: BLE001 - any decode failure is an invalid token
        raise TokenError("Invalid signature encoding") from exc
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise TokenError("Signature mismatch")

    try:
        payload = json.loads(_b64url_decode(payload_seg))
    except Exception as exc:  # noqa: BLE001
        raise TokenError("Invalid payload") from exc

    now = int(time.time() if now_epoch is None else now_epoch)
    if "exp" in payload and now >= int(payload["exp"]):
        raise TokenError("Token expired")
    return payload
