"""Initial database models (Phase 1).

Kept intentionally lean but extensible. Later phases add columns/relations
(indicator params, backtest artefacts, MT5 mapping, etc.). Enumerated fields
are stored as strings for forward-compatibility.

All monetary/price columns use Numeric to avoid float rounding in financial
data. Timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    accounts: Mapped[list[Account]] = relationship(back_populates="user")
    risk_settings: Mapped[list[RiskSetting]] = relationship(back_populates="user")


class Account(Base, TimestampMixin):
    """A trading account snapshot. Phase 1: never populated with real money."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="Primary")
    # analysis_only | paper | live  — Phase 1 only ever "analysis_only".
    account_type: Mapped[str] = mapped_column(String(32), default="analysis_only", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    balance: Mapped[float | None] = mapped_column(Numeric(18, 2))
    equity: Mapped[float | None] = mapped_column(Numeric(18, 2))
    margin: Mapped[float | None] = mapped_column(Numeric(18, 2))
    free_margin: Mapped[float | None] = mapped_column(Numeric(18, 2))
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="accounts")
    broker_connection: Mapped[BrokerConnection | None] = relationship(
        back_populates="account", uselist=False
    )


class BrokerConnection(Base, TimestampMixin):
    """Broker/MetaTrader connection metadata.

    SECURITY: credentials are NEVER stored here in plaintext. Phase 1 stores
    only non-secret metadata; secret material is referenced by an external
    secret-store key added in Phase 5.
    """

    __tablename__ = "broker_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="metatrader5", nullable=False)
    server: Mapped[str | None] = mapped_column(String(255))
    login_hint: Mapped[str | None] = mapped_column(String(64))  # non-secret display hint only
    secret_ref: Mapped[str | None] = mapped_column(String(255))  # pointer to secret store
    status: Mapped[str] = mapped_column(String(32), default="disconnected", nullable=False)

    account: Mapped[Account] = relationship(back_populates="broker_connection")


class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    parameters: Mapped[list[StrategyParameter]] = relationship(back_populates="strategy")
    signals: Mapped[list[Signal]] = relationship(back_populates="strategy")


class StrategyParameter(Base, TimestampMixin):
    __tablename__ = "strategy_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)  # serialized value
    value_type: Mapped[str] = mapped_column(String(16), default="str", nullable=False)

    strategy: Mapped[Strategy] = relationship(back_populates="parameters")

    __table_args__ = (UniqueConstraint("strategy_id", "name", name="uq_strategy_param"),)


class Signal(Base, TimestampMixin):
    """A generated (explainable) signal. Levels 0-4 per the spec."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"))
    symbol: Mapped[str] = mapped_column(String(24), default="XAUUSD", nullable=False)
    timeframe: Mapped[str | None] = mapped_column(String(8))
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regime: Mapped[str | None] = mapped_column(String(32))
    direction: Mapped[str | None] = mapped_column(String(8))
    entry_low: Mapped[float | None] = mapped_column(Numeric(18, 5))
    entry_high: Mapped[float | None] = mapped_column(Numeric(18, 5))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 5))
    take_profit_1: Mapped[float | None] = mapped_column(Numeric(18, 5))
    take_profit_2: Mapped[float | None] = mapped_column(Numeric(18, 5))
    risk_reward: Mapped[float | None] = mapped_column(Numeric(8, 3))
    confidence_score: Mapped[int | None] = mapped_column(Integer)
    reasoning: Mapped[str | None] = mapped_column(Text)  # JSON-serialized explanation
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    strategy: Mapped[Strategy | None] = relationship(back_populates="signals")


class Order(Base, TimestampMixin):
    """Order record. Phase 1: no orders are ever created (execution disabled)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"))
    symbol: Mapped[str] = mapped_column(String(24), default="XAUUSD", nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy | sell
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    volume_lots: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(18, 5))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 5))
    take_profit: Mapped[float | None] = mapped_column(Numeric(18, 5))
    status: Mapped[str] = mapped_column(String(24), default="simulated", nullable=False)
    # execution mode this order belongs to; never "live" in Phase 1
    mode: Mapped[str] = mapped_column(String(16), default="analysis_only", nullable=False)


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(24), default="XAUUSD", nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    volume_lots: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Numeric(18, 5))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 5))
    take_profit: Mapped[float | None] = mapped_column(Numeric(18, 5))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), default="analysis_only", nullable=False)


class Trade(Base, TimestampMixin):
    """Closed trade record + journal fields (spec section 21)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"))
    symbol: Mapped[str] = mapped_column(String(24), default="XAUUSD", nullable=False)
    timeframe: Mapped[str | None] = mapped_column(String(8))
    regime: Mapped[str | None] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    volume_lots: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Numeric(18, 5))
    exit_price: Mapped[float | None] = mapped_column(Numeric(18, 5))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 5))
    take_profit: Mapped[float | None] = mapped_column(Numeric(18, 5))
    pnl: Mapped[float | None] = mapped_column(Numeric(18, 2))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_reason: Mapped[str | None] = mapped_column(Text)
    exit_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="analysis_only", nullable=False)


class RiskSetting(Base, TimestampMixin):
    __tablename__ = "risk_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    risk_per_trade_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=1.0, nullable=False)
    max_daily_loss_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=3.0, nullable=False)
    max_weekly_loss_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=6.0, nullable=False)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    max_lot_size: Mapped[float] = mapped_column(Numeric(12, 4), default=1.0, nullable=False)
    max_spread_points: Mapped[float] = mapped_column(Numeric(10, 2), default=50.0, nullable=False)

    user: Mapped[User] = relationship(back_populates="risk_settings")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(24), default="browser", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class NewsEvent(Base, TimestampMixin):
    """Economic calendar event. Phase 1: table empty (no source connected)."""

    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8))
    impact: Mapped[str | None] = mapped_column(String(16))  # low | medium | high
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(120))


class SystemLog(Base, TimestampMixin):
    """Structured decision/audit log (also emitted to stdout)."""

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO", nullable=False)
    category: Mapped[str] = mapped_column(String(48), default="general", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)  # JSON-serialized
