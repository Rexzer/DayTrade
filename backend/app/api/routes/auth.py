"""Authentication endpoints.

Baseline email/password auth with hashed passwords (never plaintext) and
HS256 JWT access tokens. Registration is open in Phase 1 dev; tighten with
invite/roles in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=True)


def _issue_token(subject: str) -> TokenResponse:
    settings = get_settings()
    if not settings.secret_key:
        raise HTTPException(
            status_code=500,
            detail="Server SECRET_KEY is not configured.",
        )
    token = create_access_token(
        subject=subject,
        secret_key=settings.secret_key,
        expires_in_seconds=settings.access_token_expire_minutes * 60,
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id, email=user.email, display_name=user.display_name, is_active=user.is_active
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        # Generic message — never reveal which factor failed.
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled.")
    return _issue_token(subject=user.email)


@router.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UserResponse:
    settings = get_settings()
    try:
        claims = decode_access_token(credentials.credentials, settings.secret_key)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        ) from exc
    user = db.execute(select(User).where(User.email == claims.get("sub"))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse(
        id=user.id, email=user.email, display_name=user.display_name, is_active=user.is_active
    )
