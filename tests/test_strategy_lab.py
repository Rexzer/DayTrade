"""Tests: champion/challenger candidate lifecycle + promotion gates (pure)."""

import pytest

from strategy_lab import (
    STAGE_APPROVED,
    STAGE_BACKTESTED,
    STAGE_CANDIDATE,
    STAGE_LIVE,
    STAGE_REJECTED,
    STAGE_SHADOW,
    STAGE_WALK_FORWARD,
    CandidatePipeline,
    PromotionGates,
)
from strategy_lab.lifecycle import check_backtest, check_shadow, check_walk_forward

GATES = PromotionGates(
    min_backtest_trades=30,
    min_backtest_profit_factor=1.2,
    min_walk_forward_efficiency=0.5,
    min_shadow_trades=20,
)

GOOD_BT = {"num_trades": 50, "profit_factor": 1.5, "expectancy": 3.0, "max_drawdown_pct": 12.0}
GOOD_WF = {"efficiency": 0.7, "oos_expectancy": 2.0}
GOOD_SHADOW = {"num_trades": 30, "expectancy": 2.5}


# ---- gate unit checks ------------------------------------------------------
def test_backtest_gate_rejects_small_sample():
    r = check_backtest({"num_trades": 5, "profit_factor": 2.0, "expectancy": 5.0}, GATES)
    assert r.passed is False
    assert any("backtest trades" in x for x in r.reasons)


def test_backtest_gate_rejects_weak_profit_factor_and_drawdown():
    r = check_backtest(
        {"num_trades": 40, "profit_factor": 1.0, "expectancy": -1.0, "max_drawdown_pct": 40.0},
        GATES,
    )
    assert r.passed is False
    assert len(r.reasons) >= 2  # PF + expectancy + drawdown all fail


def test_backtest_gate_passes_and_targets_walk_forward():
    r = check_backtest(GOOD_BT, GATES)
    assert r.passed is True and r.to_stage == STAGE_WALK_FORWARD


def test_walk_forward_gate_needs_efficiency_and_positive_oos():
    assert check_walk_forward({"efficiency": 0.2, "oos_expectancy": 1.0}, GATES).passed is False
    assert check_walk_forward({"efficiency": 0.8, "oos_expectancy": -1.0}, GATES).passed is False
    assert check_walk_forward(GOOD_WF, GATES).passed is True


def test_shadow_gate_must_beat_champion():
    champ = {"expectancy": 3.0}
    # Challenger worse than champion -> rejected.
    worse = check_shadow({"num_trades": 30, "expectancy": 2.0}, GATES, champ)
    assert worse.passed is False and any("champion" in x for x in worse.reasons)
    # Challenger better than champion -> approved.
    better = check_shadow({"num_trades": 30, "expectancy": 4.0}, GATES, champ)
    assert better.passed is True and better.to_stage == STAGE_APPROVED


def test_shadow_gate_no_champion_just_needs_positive_expectancy():
    r = check_shadow(GOOD_SHADOW, GATES, champion_metrics=None)
    assert r.passed is True


# ---- pipeline transitions --------------------------------------------------
def test_full_happy_path_to_live_requires_human_promote():
    pipe = CandidatePipeline(GATES)
    pipe.register("london_breakout", "London Breakout", source="human")
    assert pipe.get("london_breakout").stage == STAGE_CANDIDATE

    assert pipe.record_backtest("london_breakout", GOOD_BT).passed
    assert pipe.get("london_breakout").stage == STAGE_WALK_FORWARD

    assert pipe.record_walk_forward("london_breakout", GOOD_WF).passed
    assert pipe.get("london_breakout").stage == STAGE_SHADOW

    assert pipe.record_shadow("london_breakout", GOOD_SHADOW, {"expectancy": 1.0}).passed
    # Passing shadow only reaches APPROVED — never auto-live.
    assert pipe.get("london_breakout").stage == STAGE_APPROVED

    pipe.promote("london_breakout")
    assert pipe.get("london_breakout").stage == STAGE_LIVE


def test_failing_a_gate_rejects_and_records_reasons():
    pipe = CandidatePipeline(GATES)
    pipe.register("weak", "Weak Idea")
    r = pipe.record_backtest("weak", {"num_trades": 3, "profit_factor": 0.8, "expectancy": -2.0})
    assert r.passed is False
    cand = pipe.get("weak")
    assert cand.stage == STAGE_REJECTED
    assert cand.reasons  # explains why
    assert cand.history[-1]["to"] == STAGE_REJECTED


def test_cannot_promote_before_approved():
    pipe = CandidatePipeline(GATES)
    pipe.register("x", "X")
    with pytest.raises(ValueError):
        pipe.promote("x")  # still a candidate, not approved


def test_cannot_record_out_of_order():
    pipe = CandidatePipeline(GATES)
    pipe.register("x", "X")
    with pytest.raises(ValueError):
        pipe.record_walk_forward("x", GOOD_WF)  # backtest not done yet


def test_duplicate_registration_rejected():
    pipe = CandidatePipeline(GATES)
    pipe.register("x", "X")
    with pytest.raises(ValueError):
        pipe.register("x", "X again")


def test_funnel_counts_by_stage():
    pipe = CandidatePipeline(GATES)
    pipe.register("a", "A")
    pipe.register("b", "B")
    pipe.record_backtest("a", GOOD_BT)  # -> walk_forward
    pipe.record_backtest("b", {"num_trades": 1})  # -> rejected
    funnel = pipe.funnel()
    assert funnel["counts"].get(STAGE_WALK_FORWARD) == 1
    assert funnel["counts"].get(STAGE_REJECTED) == 1
    assert len(funnel["candidates"]) == 2


def test_retire_from_any_stage():
    pipe = CandidatePipeline(GATES)
    pipe.register("a", "A")
    pipe.record_backtest("a", GOOD_BT)
    pipe.retire("a", "No longer relevant")
    assert pipe.get("a").stage == "retired"


def test_backtested_stage_constant_available():
    # Sanity: exported stage constants are wired (guards against typos).
    assert STAGE_BACKTESTED == "backtested"
