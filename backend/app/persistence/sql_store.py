"""SQLAlchemy-backed durable store (runtime; needs a database).

Maps the pure Stored* records onto the existing ORM models (Signal / Order /
Trade). Imported lazily by the service so the pure store module stays
dependency-free. Not exercised in the offline test suite (no DB there); it is
syntax-checked and used when a real PostgreSQL is configured.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Account,
    Order,
    RiskStateSnapshot,
    Signal,
    Strategy,
    Trade,
    User,
)
from backend.app.persistence.store import (
    StoredOrder,
    StoredSignal,
    StoredTrade,
    TradeStore,
)


def _dt(epoch: float | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


class SqlTradeStore(TradeStore):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._account_id: int | None = None

    # --- helpers -------------------------------------------------------------
    def _ensure_account(self, db: Session) -> int:
        if self._account_id is not None:
            return self._account_id
        user = db.execute(select(User).limit(1)).scalar_one_or_none()
        if user is None:
            user = User(email="operator@local", hashed_password="x", display_name="Operator")
            db.add(user)
            db.flush()
        acct = db.execute(
            select(Account).where(Account.user_id == user.id).limit(1)
        ).scalar_one_or_none()
        if acct is None:
            acct = Account(user_id=user.id, label="Live", account_type="live")
            db.add(acct)
            db.flush()
        self._account_id = acct.id
        return acct.id

    def _strategy_id(self, db: Session, key: str | None) -> int | None:
        if not key:
            return None
        row = db.execute(select(Strategy).where(Strategy.key == key)).scalar_one_or_none()
        return row.id if row else None

    # --- writes --------------------------------------------------------------
    def save_signal(self, signal: StoredSignal) -> int:
        db = self._session_factory()
        try:
            row = Signal(
                strategy_id=self._strategy_id(db, signal.strategy_key),
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                level=signal.level,
                regime=signal.regime,
                direction=signal.direction,
                confidence_score=signal.confidence_score,
                reasoning=(
                    signal.reasoning
                    if isinstance(signal.reasoning, str)
                    else json.dumps(signal.reasoning or {})
                ),
                generated_at=_dt(signal.epoch),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id
        finally:
            db.close()

    def save_order(self, order: StoredOrder) -> int:
        db = self._session_factory()
        try:
            account_id = self._ensure_account(db)
            row = Order(
                account_id=account_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                volume_lots=order.volume_lots,
                price=order.price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                status=order.status,
                mode=order.mode,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id
        finally:
            db.close()

    def save_trade(self, trade: StoredTrade) -> int:
        db = self._session_factory()
        try:
            account_id = self._ensure_account(db)
            row = Trade(
                account_id=account_id,
                strategy_id=self._strategy_id(db, trade.strategy_key),
                symbol=trade.symbol,
                regime=trade.regime,
                side=trade.side,
                volume_lots=trade.volume_lots,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                pnl=trade.pnl,
                exit_reason=trade.exit_reason,
                opened_at=_dt(trade.opened_epoch),
                closed_at=_dt(trade.closed_epoch),
                mode=trade.mode,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id
        finally:
            db.close()

    # --- reads ---------------------------------------------------------------
    def recent_signals(self, limit: int = 100) -> list[dict]:
        db = self._session_factory()
        try:
            rows = (
                db.execute(select(Signal).order_by(Signal.id.desc()).limit(limit)).scalars().all()
            )
            return [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "timeframe": r.timeframe,
                    "level": r.level,
                    "direction": r.direction,
                    "regime": r.regime,
                    "confidence_score": r.confidence_score,
                }
                for r in rows
            ]
        finally:
            db.close()

    def recent_orders(self, limit: int = 100) -> list[dict]:
        db = self._session_factory()
        try:
            rows = db.execute(select(Order).order_by(Order.id.desc()).limit(limit)).scalars().all()
            return [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "side": r.side,
                    "order_type": r.order_type,
                    "volume_lots": float(r.volume_lots),
                    "status": r.status,
                    "mode": r.mode,
                }
                for r in rows
            ]
        finally:
            db.close()

    def recent_trades(self, limit: int = 100) -> list[dict]:
        db = self._session_factory()
        try:
            rows = db.execute(select(Trade).order_by(Trade.id.desc()).limit(limit)).scalars().all()
            return [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "side": r.side,
                    "volume_lots": float(r.volume_lots),
                    "entry_price": float(r.entry_price) if r.entry_price is not None else None,
                    "exit_price": float(r.exit_price) if r.exit_price is not None else None,
                    "pnl": float(r.pnl) if r.pnl is not None else None,
                    "exit_reason": r.exit_reason,
                    "mode": r.mode,
                }
                for r in rows
            ]
        finally:
            db.close()

    # --- risk state ----------------------------------------------------------
    def save_risk_state(self, state: dict) -> None:
        db = self._session_factory()
        try:
            row = db.get(RiskStateSnapshot, 1)
            payload = json.dumps(state or {})
            if row is None:
                db.add(RiskStateSnapshot(id=1, payload=payload))
            else:
                row.payload = payload
            db.commit()
        finally:
            db.close()

    def load_risk_state(self) -> dict | None:
        db = self._session_factory()
        try:
            row = db.get(RiskStateSnapshot, 1)
            if row is None or not row.payload:
                return None
            try:
                return json.loads(row.payload)
            except (ValueError, TypeError):
                return None
        finally:
            db.close()
