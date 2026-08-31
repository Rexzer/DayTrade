"""Persistence for user-created (rule-based) strategies (Phase 3)."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import UserStrategy


class UserStrategyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, enabled_only: bool = False) -> list[UserStrategy]:
        stmt = select(UserStrategy)
        if enabled_only:
            stmt = stmt.where(UserStrategy.is_enabled.is_(True))
        return list(self.db.execute(stmt).scalars().all())

    def get(self, key: str) -> UserStrategy | None:
        return self.db.execute(
            select(UserStrategy).where(UserStrategy.key == key)
        ).scalar_one_or_none()

    def create(self, definition: dict) -> UserStrategy:
        row = UserStrategy(
            key=definition["key"],
            name=definition["name"],
            description=definition.get("description", ""),
            timeframe=definition.get("timeframe", "15m"),
            definition=json.dumps(definition),
            is_enabled=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, key: str) -> bool:
        row = self.get(key)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
