"""Trade-journal intelligence (pure Python).

Detects behavioural patterns in a user's trades and presents them NEUTRALLY —
as observations to consider, never as accusations or guarantees. Every
observation cites the evidence (trade ids / counts) behind it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Observation:
    code: str
    title: str
    detail: str
    count: int = 0
    evidence: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "count": self.count,
            "evidence": self.evidence,
        }


def _day(epoch) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d") if epoch else "?"


def _hour(epoch) -> int | None:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).hour if epoch else None


class JournalAnalyzer:
    def __init__(
        self,
        *,
        max_trades_per_day: int = 5,
        consecutive_loss_threshold: int = 3,
        large_impact_pct: float = 0.03,
        preferred_hours: tuple[int, int] | None = None,  # (start, end) UTC
    ) -> None:
        self.max_trades_per_day = max_trades_per_day
        self.consecutive_loss_threshold = consecutive_loss_threshold
        self.large_impact_pct = large_impact_pct
        self.preferred_hours = preferred_hours

    def analyze(self, trades: list[dict]) -> list[Observation]:
        if not trades:
            return []
        ordered = sorted(trades, key=lambda t: t.get("opened_epoch") or 0)
        out: list[Observation] = []
        out += self._overtrading(ordered)
        out += self._after_losses(ordered)
        out += self._excessive_size(ordered)
        out += self._chasing_breakouts(ordered)
        out += self._outside_hours(ordered)
        out += self._news_note(ordered)
        return out

    def _overtrading(self, trades: list[dict]) -> list[Observation]:
        per_day: dict[str, list] = {}
        for t in trades:
            per_day.setdefault(_day(t.get("opened_epoch")), []).append(t.get("id"))
        heavy = {d: ids for d, ids in per_day.items() if len(ids) > self.max_trades_per_day}
        if not heavy:
            return []
        worst = max(heavy.items(), key=lambda kv: len(kv[1]))
        return [
            Observation(
                code="overtrading",
                title="Possible over-trading",
                detail=(
                    f"On {len(heavy)} day(s) the number of trades exceeded your configured "
                    f"limit of {self.max_trades_per_day}. The busiest day ({worst[0]}) had "
                    f"{len(worst[1])} trades."
                ),
                count=len(heavy),
                evidence=[d for d in heavy],
            )
        ]

    def _after_losses(self, trades: list[dict]) -> list[Observation]:
        streak = 0
        flagged = []
        for t in trades:
            if streak >= self.consecutive_loss_threshold:
                flagged.append(t.get("id"))
            if t.get("pnl", 0) > 0:
                streak = 0
            else:
                streak += 1
        if not flagged:
            return []
        return [
            Observation(
                code="trading_after_losses",
                title="Trading after consecutive losses",
                detail=(
                    f"{len(flagged)} trade(s) were opened after {self.consecutive_loss_threshold}+ "
                    "consecutive losses. Consider whether a pause helps after a losing streak."
                ),
                count=len(flagged),
                evidence=flagged,
            )
        ]

    def _excessive_size(self, trades: list[dict]) -> list[Observation]:
        flagged = [
            t.get("id") for t in trades if abs(t.get("return_pct") or 0) > self.large_impact_pct
        ]
        if not flagged:
            return []
        return [
            Observation(
                code="large_position_impact",
                title="Large position impact",
                detail=(
                    f"{len(flagged)} trade(s) moved account equity by more than "
                    f"{self.large_impact_pct * 100:.0f}% each, which may indicate larger position "
                    "sizes than your per-trade risk implies."
                ),
                count=len(flagged),
                evidence=flagged,
            )
        ]

    def _chasing_breakouts(self, trades: list[dict]) -> list[Observation]:
        # Heuristic: breakout trades stopped out very quickly may be chases.
        flagged = [
            t.get("id")
            for t in trades
            if "breakout" in str(t.get("strategy_key", "")).lower()
            and t.get("exit_reason") == "stop_loss"
        ]
        if len(flagged) < 2:
            return []
        return [
            Observation(
                code="chasing_breakouts",
                title="Possible breakout chasing",
                detail=(
                    f"{len(flagged)} breakout trade(s) were stopped out. Repeated quick stop-outs "
                    "on breakouts can indicate entering without waiting for a retest/confirmation."
                ),
                count=len(flagged),
                evidence=flagged,
            )
        ]

    def _outside_hours(self, trades: list[dict]) -> list[Observation]:
        if not self.preferred_hours:
            return []
        start, end = self.preferred_hours
        flagged = []
        for t in trades:
            h = _hour(t.get("opened_epoch"))
            if h is None:
                continue
            inside = (start <= h < end) if start <= end else (h >= start or h < end)
            if not inside:
                flagged.append(t.get("id"))
        if not flagged:
            return []
        return [
            Observation(
                code="outside_preferred_hours",
                title="Trading outside preferred hours",
                detail=(
                    f"{len(flagged)} trade(s) were opened outside your preferred window "
                    f"({start:02d}:00–{end:02d}:00 UTC)."
                ),
                count=len(flagged),
                evidence=flagged,
            )
        ]

    def _news_note(self, trades: list[dict]) -> list[Observation]:
        # We cannot assess "ignoring news" without a news feed correlated to trades.
        return [
            Observation(
                code="news_assessment_unavailable",
                title="News-timing assessment unavailable",
                detail=(
                    "No economic-calendar data is linked to these trades, so trading around "
                    "high-impact news cannot be assessed. Connect a news source to enable this."
                ),
                count=0,
                evidence=[],
            )
        ]
