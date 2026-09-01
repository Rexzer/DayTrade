"""Candidate lifecycle + promotion gates (pure Python).

Models the champion/challenger funnel and the hard gates between stages. Each
``record_*`` call attaches that stage's metrics to the candidate and asks the
matching gate whether it may advance; failing a gate REJECTS the candidate with
explicit reasons (so nothing is promoted on hand-wavy evidence). Promotion to
LIVE is a deliberate human action, only allowed from APPROVED.

All metrics are plain dicts (as produced by the backtester / paper journal /
analytics.performance) so this module stays dependency-free and reproducible.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

# ---- lifecycle stages ------------------------------------------------------
STAGE_CANDIDATE = "candidate"
STAGE_BACKTESTED = "backtested"
STAGE_WALK_FORWARD = "walk_forward"
STAGE_SHADOW = "shadow"
STAGE_APPROVED = "approved"
STAGE_LIVE = "live"
STAGE_REJECTED = "rejected"
STAGE_RETIRED = "retired"


@dataclass
class PromotionGates:
    """Thresholds each stage must clear to advance. Conservative by default."""

    # Backtest gate (historical, realistic costs assumed upstream).
    min_backtest_trades: int = 30
    min_backtest_profit_factor: float = 1.2
    min_backtest_expectancy: float = 0.0
    max_backtest_drawdown_pct: float = 25.0

    # Walk-forward gate (out-of-sample robustness).
    min_walk_forward_efficiency: float = 0.5  # OOS / in-sample performance ratio
    min_walk_forward_expectancy: float = 0.0  # OOS expectancy must stay positive

    # Shadow gate (paper trading on the LIVE feed — data it can't be fit to).
    min_shadow_trades: int = 20
    min_shadow_expectancy: float = 0.0
    # A challenger must beat the champion's expectancy by this factor to justify
    # replacing/adding it (ignored when there is no champion yet).
    champion_beat_margin: float = 1.0  # 1.0 => must at least match; >1 => beat by margin

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GateResult:
    passed: bool
    from_stage: str
    to_stage: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    key: str
    name: str
    source: str = "human"  # human | param_sweep | recombination | external
    stage: str = STAGE_CANDIDATE
    backtest: dict | None = None
    walk_forward: dict | None = None
    shadow: dict | None = None
    reasons: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    created_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def _transition(self, to_stage: str, reasons: list[str], now: float | None = None) -> None:
        self.history.append(
            {
                "from": self.stage,
                "to": to_stage,
                "epoch": now if now is not None else time.time(),
                "reasons": list(reasons),
            }
        )
        self.stage = to_stage
        self.reasons = list(reasons)


# ---- gate checks (pure functions) ------------------------------------------
def check_backtest(metrics: dict, gates: PromotionGates) -> GateResult:
    reasons: list[str] = []
    n = metrics.get("num_trades", 0)
    pf = metrics.get("profit_factor")
    exp = metrics.get("expectancy", 0.0)
    dd = metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0.0))
    if n < gates.min_backtest_trades:
        reasons.append(f"Only {n} backtest trades (need {gates.min_backtest_trades}).")
    if pf is not None and pf < gates.min_backtest_profit_factor:
        reasons.append(f"Profit factor {pf} < {gates.min_backtest_profit_factor}.")
    if exp < gates.min_backtest_expectancy:
        reasons.append(f"Expectancy {exp} < {gates.min_backtest_expectancy}.")
    if dd is not None and dd > gates.max_backtest_drawdown_pct:
        reasons.append(f"Max drawdown {dd}% > {gates.max_backtest_drawdown_pct}%.")
    passed = not reasons
    return GateResult(
        passed, STAGE_CANDIDATE, STAGE_WALK_FORWARD if passed else STAGE_REJECTED, reasons
    )


def check_walk_forward(metrics: dict, gates: PromotionGates) -> GateResult:
    reasons: list[str] = []
    eff = metrics.get("efficiency", metrics.get("walk_forward_efficiency"))
    oos_exp = metrics.get("oos_expectancy", metrics.get("expectancy", 0.0))
    if eff is None:
        reasons.append("No walk-forward efficiency reported.")
    elif eff < gates.min_walk_forward_efficiency:
        reasons.append(f"Walk-forward efficiency {eff} < {gates.min_walk_forward_efficiency}.")
    if oos_exp < gates.min_walk_forward_expectancy:
        reasons.append(f"Out-of-sample expectancy {oos_exp} < {gates.min_walk_forward_expectancy}.")
    passed = not reasons
    return GateResult(
        passed, STAGE_WALK_FORWARD, STAGE_SHADOW if passed else STAGE_REJECTED, reasons
    )


def check_shadow(
    metrics: dict, gates: PromotionGates, champion_metrics: dict | None = None
) -> GateResult:
    reasons: list[str] = []
    n = metrics.get("num_trades", 0)
    exp = metrics.get("expectancy", 0.0)
    if n < gates.min_shadow_trades:
        reasons.append(f"Only {n} shadow (paper) trades (need {gates.min_shadow_trades}).")
    if exp < gates.min_shadow_expectancy:
        reasons.append(f"Shadow expectancy {exp} < {gates.min_shadow_expectancy}.")
    if champion_metrics is not None:
        champ_exp = champion_metrics.get("expectancy", 0.0)
        # Must beat (or match) the champion by the configured margin. Guard the
        # sign so a negative champion isn't 'beaten' by a smaller negative.
        required = champ_exp * gates.champion_beat_margin if champ_exp > 0 else 0.0
        if exp <= required:
            reasons.append(
                f"Shadow expectancy {exp} does not beat champion {champ_exp} "
                f"(need > {round(required, 4)})."
            )
    passed = not reasons
    # Passing shadow lands in APPROVED (awaiting explicit human promotion).
    return GateResult(passed, STAGE_SHADOW, STAGE_APPROVED if passed else STAGE_REJECTED, reasons)


# ---- pipeline controller ---------------------------------------------------
class CandidatePipeline:
    """In-memory registry of candidates + guarded stage transitions.

    (Persistence of the funnel is a later increment; the decision logic — the
    valuable part — lives in the pure gate functions above.)
    """

    def __init__(self, gates: PromotionGates | None = None) -> None:
        self.gates = gates or PromotionGates()
        self._candidates: dict[str, Candidate] = {}

    # --- registry ---
    def register(
        self, key: str, name: str, source: str = "human", *, now: float | None = None
    ) -> Candidate:
        if key in self._candidates:
            raise ValueError(f"Candidate '{key}' already registered.")
        cand = Candidate(key=key, name=name, source=source)
        if now is not None:
            cand.created_epoch = now
        self._candidates[key] = cand
        return cand

    def get(self, key: str) -> Candidate | None:
        return self._candidates.get(key)

    def all(self) -> list[Candidate]:
        return list(self._candidates.values())

    def funnel(self) -> dict:
        """Counts per stage + the full candidate list (newest first)."""
        counts: dict[str, int] = {}
        for c in self._candidates.values():
            counts[c.stage] = counts.get(c.stage, 0) + 1
        cands = sorted(self._candidates.values(), key=lambda c: c.created_epoch, reverse=True)
        return {"counts": counts, "candidates": [c.to_dict() for c in cands]}

    # --- guarded transitions ---
    def _require(self, key: str, expected_stage: str) -> Candidate:
        cand = self._candidates.get(key)
        if cand is None:
            raise KeyError(f"Unknown candidate '{key}'.")
        if cand.stage != expected_stage:
            raise ValueError(
                f"Candidate '{key}' is in stage '{cand.stage}', expected '{expected_stage}'."
            )
        return cand

    def record_backtest(self, key: str, metrics: dict, *, now: float | None = None) -> GateResult:
        cand = self._require(key, STAGE_CANDIDATE)
        cand.backtest = metrics
        result = check_backtest(metrics, self.gates)
        cand._transition(result.to_stage, result.reasons, now)
        return result

    def record_walk_forward(
        self, key: str, metrics: dict, *, now: float | None = None
    ) -> GateResult:
        cand = self._require(key, STAGE_WALK_FORWARD)
        cand.walk_forward = metrics
        result = check_walk_forward(metrics, self.gates)
        cand._transition(result.to_stage, result.reasons, now)
        return result

    def record_shadow(
        self,
        key: str,
        metrics: dict,
        champion_metrics: dict | None = None,
        *,
        now: float | None = None,
    ) -> GateResult:
        cand = self._require(key, STAGE_SHADOW)
        cand.shadow = metrics
        result = check_shadow(metrics, self.gates, champion_metrics)
        cand._transition(result.to_stage, result.reasons, now)
        return result

    def promote(self, key: str, *, now: float | None = None) -> Candidate:
        """Human action: APPROVED -> LIVE. Only allowed from APPROVED."""
        cand = self._require(key, STAGE_APPROVED)
        cand._transition(STAGE_LIVE, ["Promoted to live by operator."], now)
        return cand

    def retire(self, key: str, reason: str = "Retired by operator.", *, now=None) -> Candidate:
        cand = self._candidates.get(key)
        if cand is None:
            raise KeyError(f"Unknown candidate '{key}'.")
        cand._transition(STAGE_RETIRED, [reason], now)
        return cand
