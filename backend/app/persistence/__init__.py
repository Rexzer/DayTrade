"""Durable persistence for live signals/orders/trades (Phase 9 hardening).

Exposes the pure store contract + records + in-memory implementation. The
SQLAlchemy-backed ``SqlTradeStore`` is imported lazily via ``build_store`` so
this package has no hard database dependency.
"""

from backend.app.persistence.store import (
    InMemoryTradeStore,
    StoredOrder,
    StoredSignal,
    StoredTrade,
    TradeStore,
)

_store: TradeStore | None = None


def get_store() -> TradeStore:
    """Process-wide store singleton (SQL when a DB is reachable, else memory)."""
    global _store
    if _store is None:
        _store = build_store()
    return _store


def build_store() -> TradeStore:
    """Return a SqlTradeStore when a DB is reachable, else an in-memory store."""
    try:
        # Verify the connection is actually usable before choosing SQL.
        from sqlalchemy import text

        from backend.app.db.session import SessionLocal, engine
        from backend.app.persistence.sql_store import SqlTradeStore

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return SqlTradeStore(SessionLocal)
    except Exception:  # noqa: BLE001 - no/unavailable DB -> safe in-memory fallback
        return InMemoryTradeStore()


__all__ = [
    "TradeStore",
    "InMemoryTradeStore",
    "StoredSignal",
    "StoredOrder",
    "StoredTrade",
    "build_store",
    "get_store",
]
