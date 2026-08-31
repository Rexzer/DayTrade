"""Transparent, configurable signal scoring (pure Python).

The score is NOT a probability of profit. It is a deterministic sum of points
awarded for objective criteria (trend alignment, structure, momentum, S/R,
entry trigger, risk/reward, news environment). Every awarded/withheld point
carries a human-readable reason so the number is always explainable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Default rubric — configurable. Values are the MAX points per component.
DEFAULT_WEIGHTS: dict[str, int] = {
    "trend": 20,
    "structure": 20,
    "momentum": 15,
    "support_resistance": 15,
    "entry_trigger": 15,
    "risk_reward": 10,
    "news": 5,
}


@dataclass
class ScoreComponent:
    name: str
    max_points: int
    awarded: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_points": self.max_points,
            "awarded": round(self.awarded, 2),
            "reason": self.reason,
        }


@dataclass
class ScoreCard:
    """Accumulates component scores and reports a transparent total."""

    weights: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    components: list[ScoreComponent] = field(default_factory=list)

    def award(self, name: str, fraction: float, reason: str) -> None:
        """Award ``fraction`` (0..1) of the component's max points.

        Unknown component names default to a max of 0 so a typo can never
        inflate the score beyond the configured rubric.
        """
        frac = max(0.0, min(1.0, fraction))
        max_points = self.weights.get(name, 0)
        self.components.append(
            ScoreComponent(
                name=name, max_points=max_points, awarded=max_points * frac, reason=reason
            )
        )

    @property
    def total(self) -> int:
        raw = sum(c.awarded for c in self.components)
        return int(round(min(raw, 100.0)))

    @property
    def max_total(self) -> int:
        return sum(self.weights.values())

    def band(self) -> str:
        t = self.total
        if t < 40:
            return "weak"
        if t < 60:
            return "developing"
        if t < 75:
            return "moderate"
        if t < 90:
            return "strong"
        return "very_strong"

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "max_total": self.max_total,
            "band": self.band(),
            "components": [c.to_dict() for c in self.components],
            "disclaimer": "Score is a transparent rubric, NOT a probability of profit.",
        }
