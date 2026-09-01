"""Independent, authoritative live risk engine (pure Python).

This engine is the SOLE authority on whether a prospective live order may be
placed. The strategy/signal engines cannot bypass it — the execution
coordinator must obtain an approving :class:`RiskDecision` before sending any
order. It enforces position sizing from the broker's real contract spec and
all hard limits, and it latches HALTS (daily loss / drawdown) that require a
manual reset.

Nothing here can place an order; it only approves or rejects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from risk_engine.settings import RiskSettings


def _day_key(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")


def _week_key(epoch: float) -> str:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).isocalendar()
    return f"{dt[0]}-W{dt[1]}"


@dataclass
class SizingResult:
    lots: float
    risk_amount: float
    stop_distance_price: float
    money_per_lot: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            "lots": round(self.lots, 4),
            "risk_amount": round(self.risk_amount, 2),
            "stop_distance_price": round(self.stop_distance_price, 5),
            "money_per_lot": round(self.money_per_lot, 4),
            "explanation": self.explanation,
        }


@dataclass
class RiskCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...] = ()
    sizing: SizingResult | None = None
    checks: list[RiskCheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "reasons": list(self.reasons),
            "sizing": self.sizing.to_dict() if self.sizing else None,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class ProspectiveTrade:
    symbol: str
    direction: str  # "long" | "short"
    entry: float
    stop_loss: float
    take_profit: float | None = None


@dataclass
class RiskContext:
    equity: float
    spread_points: float
    price: float | None = None  # current mid/reference price (entry for sizing)
    data_status: str = "disconnected"  # live | delayed | stale | disconnected | invalid
    broker_connected: bool = False
    now_epoch: float = 0.0
    open_positions: int = 0
    open_xauusd_positions: int = 0
    # High-impact news events as (time_epoch, impact) tuples.
    news_events: tuple[tuple[float, str], ...] = ()


@dataclass
class RiskState:
    day_key: str | None = None
    week_key: str | None = None
    peak_equity: float = 0.0
    realized_daily_pnl: float = 0.0
    realized_weekly_pnl: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_loss_halt: bool = False
    weekly_loss_halt: bool = False
    drawdown_halt: bool = False
    current_drawdown_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "day_key": self.day_key,
            "week_key": self.week_key,
            "peak_equity": round(self.peak_equity, 2),
            "realized_daily_pnl": round(self.realized_daily_pnl, 2),
            "realized_weekly_pnl": round(self.realized_weekly_pnl, 2),
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "daily_loss_halt": self.daily_loss_halt,
            "weekly_loss_halt": self.weekly_loss_halt,
            "drawdown_halt": self.drawdown_halt,
            "current_drawdown_pct": round(self.current_drawdown_pct, 4),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> RiskState:
        """Rebuild a RiskState from a persisted dict (tolerant of missing keys).

        Unknown keys are ignored and missing keys keep their defaults, so the
        schema can evolve without breaking restore.
        """
        state = cls()
        if not data:
            return state
        for f in (
            "day_key",
            "week_key",
            "peak_equity",
            "realized_daily_pnl",
            "realized_weekly_pnl",
            "trades_today",
            "consecutive_losses",
            "daily_loss_halt",
            "weekly_loss_halt",
            "drawdown_halt",
            "current_drawdown_pct",
        ):
            if f in data and data[f] is not None:
                setattr(state, f, data[f])
        return state


_STALE_DATA = {"stale", "disconnected", "invalid"}
_XAU = "XAUUSD"


class LiveRiskEngine:
    """Authoritative pre-trade risk checks + broker-spec position sizing."""

    def __init__(self, settings: RiskSettings | None = None) -> None:
        self.settings = settings or RiskSettings()
        self.state = RiskState()

    def update_settings(self, settings: RiskSettings) -> None:
        self.settings = settings

    def restore_state(self, data: dict | None) -> None:
        """Restore persisted risk state after a restart (crash/deploy safety).

        Latched halts and running loss counters survive the restart so a bad
        day cannot be silently reset by bouncing the process. Period rollover
        (new day/week) is still handled normally on the next ``evaluate``.
        """
        self.state = RiskState.from_dict(data)

    # ----------------------------------------------------------- accounting
    def roll_periods(self, now_epoch: float, equity: float) -> None:
        dk, wk = _day_key(now_epoch), _week_key(now_epoch)
        if self.state.day_key != dk:
            self.state.day_key = dk
            self.state.realized_daily_pnl = 0.0
            self.state.trades_today = 0
        if self.state.week_key != wk:
            self.state.week_key = wk
            self.state.realized_weekly_pnl = 0.0
        if self.state.peak_equity <= 0:
            self.state.peak_equity = equity

    def update_equity(self, equity: float) -> None:
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        if self.state.peak_equity > 0:
            dd = (self.state.peak_equity - equity) / self.state.peak_equity
            self.state.current_drawdown_pct = max(0.0, dd)
            if dd >= self.settings.max_drawdown_pct / 100.0:
                self.state.drawdown_halt = True

    def record_trade_opened(self) -> None:
        self.state.trades_today += 1

    def record_trade_closed(self, pnl: float, equity: float) -> None:
        self.state.realized_daily_pnl += pnl
        self.state.realized_weekly_pnl += pnl
        self.state.consecutive_losses = 0 if pnl > 0 else self.state.consecutive_losses + 1
        self.update_equity(equity)
        start = self.settings  # readability
        if self.state.realized_daily_pnl <= -(start.max_daily_loss_pct / 100.0) * self._base_equity(
            equity
        ):
            self.state.daily_loss_halt = True
        if self.state.realized_weekly_pnl <= -(
            start.max_weekly_loss_pct / 100.0
        ) * self._base_equity(equity):
            self.state.weekly_loss_halt = True

    def _base_equity(self, equity: float) -> float:
        # Use the day's peak as the reference for percentage loss limits.
        return self.state.peak_equity if self.state.peak_equity > 0 else equity

    # ------------------------------------------------------------- resets
    def manual_reset(self) -> None:
        """Clear latched halts (daily/weekly/drawdown). Consecutive losses too."""
        self.state.daily_loss_halt = False
        self.state.weekly_loss_halt = False
        self.state.drawdown_halt = False
        self.state.consecutive_losses = 0

    # ------------------------------------------------------------- sizing
    def position_size(self, equity: float, trade: ProspectiveTrade, spec) -> SizingResult:
        """Compute lots from the broker's real contract spec.

        ``spec`` must expose ``tick_size``, ``tick_value``, ``volume_min``,
        ``volume_max`` and ``volume_step`` (e.g. a BrokerSymbolSpec).
        """
        risk_amount = equity * (self.settings.risk_per_trade_pct / 100.0)
        stop_distance = abs(trade.entry - trade.stop_loss)
        tick_size = getattr(spec, "tick_size", 0.0) or 0.0
        tick_value = getattr(spec, "tick_value", 0.0) or 0.0
        if stop_distance <= 0 or tick_size <= 0 or tick_value <= 0 or equity <= 0:
            return SizingResult(0.0, risk_amount, stop_distance, 0.0, "Invalid inputs for sizing.")
        ticks = stop_distance / tick_size
        money_per_lot = ticks * tick_value
        raw_lots = risk_amount / money_per_lot if money_per_lot > 0 else 0.0

        step = getattr(spec, "volume_step", 0.0) or 0.0
        vmax = getattr(spec, "volume_max", raw_lots) or raw_lots
        capped = min(raw_lots, self.settings.max_lot_size, vmax)
        if step > 0:
            capped = (int(capped / step)) * step  # floor to step
        capped = round(capped, 4)
        explanation = (
            f"Equity {equity:.2f} x {self.settings.risk_per_trade_pct:.2f}% = "
            f"risk {risk_amount:.2f}. Stop {stop_distance:.5f} price / tick {tick_size} = "
            f"{ticks:.1f} ticks x {tick_value}/tick = {money_per_lot:.2f}/lot. "
            f"Lots = {raw_lots:.4f} -> stepped/capped {capped:.4f}."
        )
        return SizingResult(capped, risk_amount, stop_distance, money_per_lot, explanation)

    # ------------------------------------------------------------- evaluate
    def evaluate(self, trade: ProspectiveTrade, context: RiskContext, spec) -> RiskDecision:
        """The single authoritative gate. Approves only if EVERY check passes."""
        self.roll_periods(context.now_epoch, context.equity)
        self.update_equity(context.equity)

        checks: list[RiskCheck] = []
        reasons: list[str] = []

        def check(name: str, passed: bool, fail_detail: str, ok_detail: str = "ok") -> None:
            checks.append(RiskCheck(name, passed, ok_detail if passed else fail_detail))
            if not passed:
                reasons.append(f"{name}: {fail_detail}")

        s = self.settings

        # Latched halts (require manual reset).
        check(
            "drawdown_halt",
            not self.state.drawdown_halt,
            "Max drawdown reached — trading halted (manual reset required).",
        )
        check(
            "daily_loss_halt",
            not self.state.daily_loss_halt,
            "Daily loss limit reached — new trades blocked (manual reset).",
        )
        check(
            "weekly_loss_halt",
            not self.state.weekly_loss_halt,
            "Weekly loss limit reached — new trades blocked (manual reset).",
        )

        # Data failsafe.
        check(
            "data_feed",
            context.data_status not in _STALE_DATA,
            f"Market data is {context.data_status.upper()}.",
            f"data {context.data_status}",
        )
        # Execution failsafe.
        check("broker_connection", context.broker_connected, "MetaTrader 5 is not connected.")

        # Spread filter.
        check(
            "spread",
            context.spread_points <= s.max_spread_points,
            f"Spread {context.spread_points:.1f} > max {s.max_spread_points:.1f}.",
            f"spread {context.spread_points:.1f} <= {s.max_spread_points:.1f}",
        )

        # News blackout.
        in_blackout, ev = self._in_news_blackout(context)
        check(
            "news_blackout",
            not in_blackout,
            f"High-impact news within blackout window (event at {ev}).",
        )

        # Position / trade-count limits.
        check(
            "max_open_positions",
            context.open_positions < s.max_open_positions,
            f"Open positions {context.open_positions} >= max {s.max_open_positions}.",
            f"{context.open_positions}/{s.max_open_positions} open",
        )
        if trade.symbol == _XAU:
            check(
                "max_xauusd_positions",
                context.open_xauusd_positions < s.max_xauusd_positions,
                f"XAUUSD positions {context.open_xauusd_positions} >= "
                f"max {s.max_xauusd_positions}.",
                f"{context.open_xauusd_positions}/{s.max_xauusd_positions} XAUUSD",
            )
        check(
            "max_trades_per_day",
            self.state.trades_today < s.max_trades_per_day,
            f"Trades today {self.state.trades_today} >= max {s.max_trades_per_day}.",
            f"{self.state.trades_today}/{s.max_trades_per_day} today",
        )
        check(
            "max_consecutive_losses",
            self.state.consecutive_losses < s.max_consecutive_losses,
            f"Consecutive losses {self.state.consecutive_losses} >= "
            f"max {s.max_consecutive_losses}.",
            f"{self.state.consecutive_losses}/{s.max_consecutive_losses} losses",
        )

        # Running loss limits (also latch a halt if breached).
        base = self._base_equity(context.equity)
        daily_limit = -(s.max_daily_loss_pct / 100.0) * base
        weekly_limit = -(s.max_weekly_loss_pct / 100.0) * base
        if self.state.realized_daily_pnl <= daily_limit:
            self.state.daily_loss_halt = True
            check("daily_loss", False, "Daily loss limit already reached.")
        if self.state.realized_weekly_pnl <= weekly_limit:
            self.state.weekly_loss_halt = True
            check("weekly_loss", False, "Weekly loss limit already reached.")

        # Geometry sanity.
        geo_ok = (trade.direction == "long" and trade.stop_loss < trade.entry) or (
            trade.direction == "short" and trade.stop_loss > trade.entry
        )
        check("stop_geometry", geo_ok, "Stop-loss is on the wrong side of entry.", "ok")

        # Position sizing (only meaningful if geometry is valid).
        sizing = self.position_size(context.equity, trade, spec) if geo_ok else None
        vmin = getattr(spec, "volume_min", 0.0) or 0.0
        if sizing is None or sizing.lots <= 0:
            check("position_size", False, "Computed position size is zero.")
        elif sizing.lots < vmin:
            check(
                "position_size", False, f"Computed lots {sizing.lots} below broker minimum {vmin}."
            )
        else:
            check("position_size", True, "", f"{sizing.lots} lots")

        approved = not reasons
        return RiskDecision(approved=approved, reasons=tuple(reasons), sizing=sizing, checks=checks)

    def _in_news_blackout(self, context: RiskContext):
        before = self.settings.news_blackout_before_min * 60.0
        after = self.settings.news_blackout_after_min * 60.0
        now = context.now_epoch
        for t, impact in context.news_events:
            if str(impact).lower() != "high":
                continue
            if (t - before) <= now <= (t + after):
                return True, t
        return False, None
