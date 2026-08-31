"""Risk engine — position sizing and pre-trade checks (pure Python).

Phase 1 provides a transparent position-size calculator (the calculation is
always shown, per the spec) and a placeholder pre-trade check. Enforcement
against live orders is added in Phase 6 alongside the execution engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_engine.settings import RiskSettings


@dataclass(frozen=True)
class PositionSizeResult:
    """Transparent output of a position-size calculation."""

    account_balance: float
    risk_pct: float
    risk_amount: float
    stop_distance_points: float
    value_per_point_per_lot: float
    raw_lots: float
    capped_lots: float
    explanation: str

    def to_dict(self) -> dict:
        return {
            "account_balance": self.account_balance,
            "risk_pct": self.risk_pct,
            "risk_amount": self.risk_amount,
            "stop_distance_points": self.stop_distance_points,
            "value_per_point_per_lot": self.value_per_point_per_lot,
            "raw_lots": self.raw_lots,
            "capped_lots": self.capped_lots,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class RiskCheckResult:
    """Result of a pre-trade risk check."""

    allowed: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "reasons": list(self.reasons)}


class RiskEngine:
    """Computes position sizes and evaluates risk limits.

    Note: In Phase 1 this engine never actually authorizes a trade because no
    execution engine is active. It exists so sizing/limit logic can be built
    and tested independently of order placement.
    """

    def __init__(self, settings: RiskSettings | None = None) -> None:
        self.settings = settings or RiskSettings()

    def position_size(
        self,
        account_balance: float,
        stop_distance_points: float,
        value_per_point_per_lot: float,
    ) -> PositionSizeResult:
        """Risk-based position sizing using the broker's own point value.

        Args:
            account_balance: Current account balance (account currency).
            stop_distance_points: Distance from entry to stop, in points.
            value_per_point_per_lot: Monetary value of 1 point for 1 lot,
                taken from the broker's XAUUSD contract spec (never assumed).
        """
        if account_balance <= 0:
            raise ValueError("account_balance must be > 0")
        if stop_distance_points <= 0:
            raise ValueError("stop_distance_points must be > 0")
        if value_per_point_per_lot <= 0:
            raise ValueError("value_per_point_per_lot must be > 0")

        risk_pct = self.settings.risk_per_trade_pct
        risk_amount = account_balance * (risk_pct / 100.0)
        risk_per_lot = stop_distance_points * value_per_point_per_lot
        raw_lots = risk_amount / risk_per_lot
        capped_lots = min(raw_lots, self.settings.max_lot_size)

        explanation = (
            f"Account {account_balance:.2f} x {risk_pct:.2f}% = risk {risk_amount:.2f}. "
            f"Risk per lot = {stop_distance_points:.2f} pts x "
            f"{value_per_point_per_lot:.2f}/pt = {risk_per_lot:.2f}. "
            f"Lots = {risk_amount:.2f} / {risk_per_lot:.2f} = {raw_lots:.4f}, "
            f"capped at max {self.settings.max_lot_size:.4f} -> {capped_lots:.4f}."
        )
        return PositionSizeResult(
            account_balance=account_balance,
            risk_pct=risk_pct,
            risk_amount=risk_amount,
            stop_distance_points=stop_distance_points,
            value_per_point_per_lot=value_per_point_per_lot,
            raw_lots=round(raw_lots, 4),
            capped_lots=round(capped_lots, 4),
            explanation=explanation,
        )

    def pre_trade_check(self, current_spread_points: float) -> RiskCheckResult:
        """Minimal Phase 1 pre-trade check (spread failsafe only).

        More checks (daily loss, open positions, consecutive losses, news
        windows) are added in later phases as their data becomes available.
        """
        reasons: list[str] = []
        if current_spread_points > self.settings.max_spread_points:
            reasons.append(
                f"Spread {current_spread_points:.1f} exceeds max "
                f"{self.settings.max_spread_points:.1f} points."
            )
        return RiskCheckResult(allowed=not reasons, reasons=tuple(reasons))
