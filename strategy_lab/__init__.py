"""Strategy laboratory — the champion/challenger promotion pipeline (pure).

New strategy candidates are never trusted on sight. They walk a funnel of hard,
out-of-sample gates before any real capital:

    CANDIDATE -> BACKTESTED -> WALK_FORWARD -> SHADOW (paper, live feed)
              -> APPROVED (human) -> LIVE        (any stage -> REJECTED/RETIRED)

The decision logic here is pure and dependency-free so it is fully testable and
reproducible. The automated shadow-paper *runner* (executing challengers in the
paper engine on the live feed) plugs into this lifecycle as a later increment.

Honesty guardrails: gates REJECT by default and only advance on genuinely
robust, out-of-sample evidence; the SHADOW stage judges a candidate on live-
forward data it could not have been fitted to, and a human must approve the
final promotion to live.
"""

from strategy_lab.lifecycle import (
    STAGE_APPROVED,
    STAGE_BACKTESTED,
    STAGE_CANDIDATE,
    STAGE_LIVE,
    STAGE_REJECTED,
    STAGE_RETIRED,
    STAGE_SHADOW,
    STAGE_WALK_FORWARD,
    Candidate,
    CandidatePipeline,
    GateResult,
    PromotionGates,
)

__all__ = [
    "Candidate",
    "CandidatePipeline",
    "GateResult",
    "PromotionGates",
    "STAGE_CANDIDATE",
    "STAGE_BACKTESTED",
    "STAGE_WALK_FORWARD",
    "STAGE_SHADOW",
    "STAGE_APPROVED",
    "STAGE_LIVE",
    "STAGE_REJECTED",
    "STAGE_RETIRED",
]
