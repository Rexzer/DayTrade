"""Operator authorization for state-changing endpoints (pure Python).

The dangerous live-trading endpoints (arm / execute / confirm / risk-config)
must not be callable by just anyone who can reach the API. This module holds
the pure decision function so it is unit-testable without FastAPI:

Accepts EITHER a matching ``X-Operator-Token`` (constant-time compared) OR a
valid HS256 bearer JWT issued by ``/auth/login``. Fails CLOSED — if neither a
LIVE_API_TOKEN nor a SECRET_KEY is configured, access is denied.
"""

from __future__ import annotations

import hmac

from backend.app.core.security import TokenError, decode_access_token


def check_operator_authorization(
    operator_token: str | None,
    bearer_token: str | None,
    *,
    configured_token: str | None,
    secret_key: str | None,
    now_epoch: float | None = None,
) -> tuple[bool, str]:
    """Return (authorized, reason)."""
    # 1) Explicit operator token (shared secret) — constant-time comparison.
    if configured_token:
        if operator_token and hmac.compare_digest(str(operator_token), str(configured_token)):
            return True, "operator-token"

    # 2) Valid bearer JWT from /auth/login.
    if bearer_token and secret_key:
        try:
            decode_access_token(bearer_token, secret_key, now_epoch=now_epoch)
            return True, "jwt"
        except TokenError:
            pass

    # 3) Fail closed.
    if not configured_token and not secret_key:
        return (
            False,
            "live endpoints are locked: configure LIVE_API_TOKEN or SECRET_KEY on the backend",
        )
    return False, "missing or invalid operator token / bearer JWT"
