"""SQLAlchemy declarative base and common mixins.

All timestamps are stored in UTC (spec requirement). Display-time conversion
happens in the presentation layer, never in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all models."""


class TimestampMixin:
    """Adds created_at / updated_at (UTC) to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
