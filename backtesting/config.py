"""Backtest configuration (pure Python).

Prices are handled in absolute price units. ``value_per_unit`` is the P&L in
account currency for a 1.0-unit price move on 1.0 lot, taken from the broker's
contract spec (never assumed). Costs (spread/slippage) are expressed in price
units; commission is per lot per round turn.

Nothing here guarantees profitability — this only defines how a hypothesis is
tested against historical data.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_engine.strategy import SignalLevel


@dataclass
class TradingSession:
    """Optional UTC trading-hours window (inclusive start, exclusive end)."""

    start_hour: int = 0
    end_hour: int = 24

    def allows(self, hour_utc: int) -> bool:
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour_utc < self.end_hour
        # Wrap-around window (e.g. 22 -> 6).
        return hour_utc >= self.start_hour or hour_utc < self.end_hour


@dataclass
class BacktestConfig:
    starting_capital: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    primary_timeframe: str = "1h"

    # Execution costs (price units, except commission which is per lot).
    spread: float = 0.30
    slippage: float = 0.10
    commission_per_lot: float = 7.0
    value_per_unit: float = 1.0  # account-currency P&L per 1.0 price move per lot
    max_lot_size: float = 100.0

    # Trade rules.
    min_signal_level: int = SignalLevel.CONFIRMED_SETUP.value
    allow_long: bool = True
    allow_short: bool = True
    max_positions: int = 1  # Phase 4 supports a single concurrent position

    # Optional filters.
    session: TradingSession | None = None
    news_blackout_epochs: tuple[tuple[float, float], ...] = ()  # (start, end) windows

    # Date range (epoch seconds); None = full history.
    start_epoch: float | None = None
    end_epoch: float | None = None

    # Risk-free rate per year for Sharpe (kept 0 by default; transparent).
    risk_free_rate: float = 0.0

    warmup_bars: int = 60

    def to_dict(self) -> dict:
        return {
            "starting_capital": self.starting_capital,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "primary_timeframe": self.primary_timeframe,
            "spread": self.spread,
            "slippage": self.slippage,
            "commission_per_lot": self.commission_per_lot,
            "value_per_unit": self.value_per_unit,
            "max_lot_size": self.max_lot_size,
            "min_signal_level": self.min_signal_level,
            "allow_long": self.allow_long,
            "allow_short": self.allow_short,
            "max_positions": self.max_positions,
            "session": (
                {"start_hour": self.session.start_hour, "end_hour": self.session.end_hour}
                if self.session
                else None
            ),
            "start_epoch": self.start_epoch,
            "end_epoch": self.end_epoch,
            "warmup_bars": self.warmup_bars,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.starting_capital <= 0:
            errors.append("starting_capital must be > 0")
        if not (0 < self.risk_per_trade_pct <= 100):
            errors.append("risk_per_trade_pct must be in (0, 100]")
        if self.spread < 0 or self.slippage < 0 or self.commission_per_lot < 0:
            errors.append("costs (spread/slippage/commission) must be >= 0")
        if self.value_per_unit <= 0:
            errors.append("value_per_unit must be > 0")
        return errors
