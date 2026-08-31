"""Shared FastAPI dependencies (Phase 9 hardening)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import get_settings
from backend.app.core.authz import check_operator_authorization

_bearer = HTTPBearer(auto_error=False)


def require_operator(
    x_operator_token: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Guard for dangerous live-trading endpoints (arm/execute/confirm/risk).

    Accepts a matching ``X-Operator-Token`` header or a valid bearer JWT. Fails
    closed with HTTP 401 otherwise.
    """
    settings = get_settings()
    ok, reason = check_operator_authorization(
        x_operator_token,
        credentials.credentials if credentials else None,
        configured_token=settings.live_api_token,
        secret_key=settings.secret_key,
    )
    if not ok:
        raise HTTPException(status_code=401, detail=f"Operator authorization required: {reason}")
    return reason
