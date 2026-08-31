"""Tests: the execution engine is hard-disabled in Phase 1."""

import pytest

from execution_engine import ExecutionDisabledError, ExecutionEngine, OrderRequest
from execution_engine.engine import OrderType


def _engine():
    return ExecutionEngine()


def test_engine_is_disabled_by_default():
    assert _engine().enabled is False


def test_submit_order_raises():
    engine = _engine()
    req = OrderRequest(symbol="XAUUSD", side="buy", order_type=OrderType.MARKET, volume_lots=0.1)
    with pytest.raises(ExecutionDisabledError):
        engine.submit_order(req)


def test_modify_position_raises():
    with pytest.raises(ExecutionDisabledError):
        _engine().modify_position("pos-1", stop_loss=1000.0)


def test_close_position_raises():
    with pytest.raises(ExecutionDisabledError):
        _engine().close_position("pos-1")


def test_cancel_order_raises():
    with pytest.raises(ExecutionDisabledError):
        _engine().cancel_order("ord-1")


def test_kill_switch_is_safe_noop():
    # Kill switch must never raise; it asserts the disabled invariant.
    _engine().kill_switch()


def test_no_public_way_to_enable():
    engine = _engine()
    # There is intentionally no setter; the attribute stays False.
    assert not hasattr(type(engine), "enable")
    assert engine.enabled is False
