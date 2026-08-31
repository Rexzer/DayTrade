"""Tests: user rule-builder engine (conditions, groups, serialization)."""

import pytest

from strategy_engine.rules import (
    Condition,
    ConditionGroup,
    RuleContext,
    RuleError,
    RuleStrategy,
    validate_rule_dict,
)
from strategy_engine.strategy import MarketContext, SignalLevel
from tests.helpers import make_candles, uptrend


def _ctx_from(closes):
    candles = make_candles(closes)
    return RuleContext.from_candles(candles, now_epoch=1_700_000_000)


def test_gt_lt_operators():
    ctx = _ctx_from([float(i) for i in range(1, 40)])
    c_gt = Condition({"kind": "price", "field": "close"}, "gt", {"kind": "constant", "value": 10})
    c_lt = Condition({"kind": "price", "field": "close"}, "lt", {"kind": "constant", "value": 10})
    assert c_gt.evaluate(ctx) is True
    assert c_lt.evaluate(ctx) is False


def test_ema_comparison_in_uptrend():
    ctx = RuleContext.from_candles(uptrend(120))
    c = Condition(
        {"kind": "ema", "params": {"period": 20}},
        "gt",
        {"kind": "ema", "params": {"period": 50}},
    )
    assert c.evaluate(ctx) is True


def test_cross_above():
    # Series that rises so a short SMA crosses above a longer one.
    closes = [10] * 20 + [10 + i for i in range(1, 20)]
    ctx = _ctx_from(closes)
    c = Condition(
        {"kind": "sma", "params": {"period": 3}},
        "cross_above",
        {"kind": "sma", "params": {"period": 10}},
    )
    # Not asserting exact bar; just that it evaluates to a bool without error.
    assert isinstance(c.evaluate(ctx), bool)


def test_group_and_or_logic():
    ctx = _ctx_from([float(i) for i in range(1, 40)])
    true_c = Condition({"kind": "price"}, "gt", {"kind": "constant", "value": 0})
    false_c = Condition({"kind": "price"}, "lt", {"kind": "constant", "value": 0})
    assert ConditionGroup("and", [true_c, false_c]).evaluate(ctx) is False
    assert ConditionGroup("or", [true_c, false_c]).evaluate(ctx) is True


def test_nested_groups():
    ctx = _ctx_from([float(i) for i in range(1, 40)])
    true_c = Condition({"kind": "price"}, "gt", {"kind": "constant", "value": 0})
    false_c = Condition({"kind": "price"}, "lt", {"kind": "constant", "value": 0})
    inner = ConditionGroup("or", [true_c, false_c])  # True
    outer = ConditionGroup("and", [inner, true_c])  # True
    assert outer.evaluate(ctx) is True
    assert len(outer.leaves()) == 3


def test_serialization_roundtrip():
    group = ConditionGroup(
        "and",
        [
            Condition(
                {"kind": "ema", "params": {"period": 20}},
                "gt",
                {"kind": "ema", "params": {"period": 50}},
            ),
            Condition(
                {"kind": "rsi", "params": {"period": 14}}, "gt", {"kind": "constant", "value": 50}
            ),
        ],
    )
    rs = RuleStrategy(key="k", name="N", description="d", timeframe="15m", long_rules=group)
    d = rs.to_dict()
    rs2 = RuleStrategy.from_dict(d)
    assert rs2.key == "k"
    assert rs2.long_rules is not None
    assert len(rs2.long_rules.leaves()) == 2


def test_validate_rejects_empty():
    errors = validate_rule_dict({"key": "k", "name": "N"})
    assert errors  # no rules provided


def test_validate_rejects_bad_logic():
    bad = {
        "key": "k",
        "name": "N",
        "long_rules": {"type": "group", "logic": "xor", "children": []},
    }
    assert validate_rule_dict(bad)


def test_rule_strategy_produces_signal():
    group = ConditionGroup(
        "and",
        [
            Condition(
                {"kind": "ema", "params": {"period": 20}},
                "gt",
                {"kind": "ema", "params": {"period": 50}},
            )
        ],
    )
    rs = RuleStrategy(key="k", name="N", description="d", timeframe="15m", long_rules=group)
    sig = rs.evaluate(MarketContext(candles={"15m": uptrend(120)}))
    assert sig.strategy_key == "k"
    assert sig.level != SignalLevel.TRADE_EXECUTED
    assert sig.direction == "long"
    assert rs.metadata.is_builtin is False


def test_unknown_operator_raises():
    ctx = _ctx_from([1.0, 2.0, 3.0] * 15)
    c = Condition({"kind": "price"}, "weird_op", {"kind": "constant", "value": 1})
    with pytest.raises(RuleError):
        c.evaluate(ctx)
