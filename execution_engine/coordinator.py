"""Execution coordinator (pure Python) — the ONLY path to a live order.

Enforces the mandatory pipeline with no shortcuts:

    Strategy/Signal -> AUTHORIZATION -> RISK ENGINE -> ORDER VALIDATION ->
    duplicate check -> EXECUTION (MT5) -> result verification -> log

Every stage is recorded in an execution log. The risk engine is authoritative:
if it does not approve, no order is sent. Success is never assumed — only an
explicit broker DONE result counts as executed. Includes a kill switch.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from execution_engine.authorization import LiveAuthorization
from execution_engine.provider import (
    BrokerConnectionError,
    ExecOrderRequest,
    ExecutionProvider,
    InvalidSymbolError,
    LiveExecutionDisabledError,
    OrderResult,
)
from risk_engine.live_risk import LiveRiskEngine, ProspectiveTrade, RiskContext, RiskDecision


@dataclass
class ExecutionLogEntry:
    epoch: float
    stage: str
    ok: bool
    message: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "epoch": self.epoch,
            "stage": self.stage,
            "ok": self.ok,
            "message": self.message,
            "payload": self.payload,
        }


class ExecutionLog:
    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[ExecutionLogEntry] = []
        self._max = max_entries

    def add(self, stage: str, ok: bool, message: str, payload: dict | None = None) -> None:
        self._entries.append(ExecutionLogEntry(time.time(), stage, ok, message, payload or {}))
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]

    def recent(self, limit: int = 100) -> list[dict]:
        return [e.to_dict() for e in self._entries[-limit:][::-1]]


@dataclass
class ExecutionOutcome:
    executed: bool
    reason: str
    stage: str
    risk_decision: RiskDecision | None = None
    order_result: OrderResult | None = None

    def to_dict(self) -> dict:
        return {
            "executed": self.executed,
            "reason": self.reason,
            "stage": self.stage,
            "risk_decision": self.risk_decision.to_dict() if self.risk_decision else None,
            "order_result": (
                {
                    "ok": self.order_result.ok,
                    "order_id": self.order_result.order_id,
                    "retcode": self.order_result.retcode,
                    "comment": self.order_result.comment,
                }
                if self.order_result
                else None
            ),
        }


class ExecutionCoordinator:
    def __init__(
        self,
        provider: ExecutionProvider,
        risk: LiveRiskEngine,
        authorization: LiveAuthorization,
        *,
        dedup_window_seconds: float = 60.0,
    ) -> None:
        self.provider = provider
        self.risk = risk
        self.authorization = authorization
        self.log = ExecutionLog()
        self._dedup_window = dedup_window_seconds
        self._recent: dict[tuple, float] = {}
        # Ensure the provider's write gate consults this authorization.
        self.provider.authorization = authorization

    # ------------------------------------------------------------- pipeline
    def execute_signal(self, signal: dict, context: RiskContext, spec) -> ExecutionOutcome:
        now = context.now_epoch or time.time()
        strategy_key = signal.get("strategy_key", "unknown")
        self.log.add("signal", True, f"Signal received [{strategy_key}]", {"signal": signal})

        # 1) Authorization (never auto-authorized).
        if not self.authorization.is_authorized():
            return self._reject("authorization", "Live execution is not authorized.")

        # 2) Build the prospective trade from the signal.
        direction = signal.get("direction")
        stop = signal.get("stop_loss")
        tps = signal.get("take_profits") or []
        entry = context.price
        if direction not in ("long", "short") or stop is None or entry is None:
            return self._reject("build", "Signal lacks direction/stop/price for execution.")
        trade = ProspectiveTrade(
            symbol=signal.get("symbol", "XAUUSD"),
            direction=direction,
            entry=float(entry),
            stop_loss=float(stop),
            take_profit=float(tps[0]) if tps else None,
        )

        # 3) Duplicate prevention (don't repeatedly submit the same setup).
        sig = (strategy_key, trade.symbol, direction)
        last = self._recent.get(sig)
        if last is not None and (now - last) < self._dedup_window:
            return self._reject("duplicate", "Duplicate signal within the dedup window; skipped.")

        # 4) Execution failsafe.
        if not self.provider.is_connected():
            return self._reject("execution_failsafe", "MetaTrader 5 is not connected.")

        # 5) RISK ENGINE — authoritative approval (sizing + all hard limits).
        decision = self.risk.evaluate(trade, context, spec)
        self.log.add(
            "risk",
            decision.approved,
            "Risk approved" if decision.approved else "Risk REJECTED",
            {"decision": decision.to_dict()},
        )
        if not decision.approved:
            return self._reject("risk", "; ".join(decision.reasons), risk_decision=decision)

        lots = decision.sizing.lots if decision.sizing else 0.0
        order_req = ExecOrderRequest(
            symbol=trade.symbol,
            side="buy" if direction == "long" else "sell",
            order_type="market",
            volume=lots,
            price=trade.entry,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
        )

        # 6) Order validation (broker order_check dry-run).
        try:
            check = self.provider.check_order(order_req)
        except (InvalidSymbolError, BrokerConnectionError) as exc:
            return self._reject("order_check", f"Order check failed: {exc}", risk_decision=decision)
        self.log.add(
            "order_check",
            check.ok,
            "Order check passed" if check.ok else "Order check FAILED",
            {"check": check.to_dict()},
        )
        if not check.ok:
            return self._reject("order_check", "; ".join(check.reasons), risk_decision=decision)

        # 7) EXECUTION — send the order. Mark dedup BEFORE sending so a crash
        #    mid-send cannot cause a rapid resubmission of the same setup.
        self._recent[sig] = now
        self.log.add("order_request", True, "Submitting order", {"request": order_req.__dict__})
        try:
            result = self.provider.send_order(order_req)
        except LiveExecutionDisabledError as exc:
            return self._reject("execution", f"Execution refused: {exc}", risk_decision=decision)
        except Exception as exc:  # noqa: BLE001
            self.log.add("order_response", False, f"send_order raised: {exc}")
            return self._reject("execution", f"send_order raised: {exc}", risk_decision=decision)

        self.log.add(
            "order_response",
            result.ok,
            "Broker DONE" if result.ok else "Broker did NOT confirm",
            {"retcode": result.retcode, "comment": result.comment, "order_id": result.order_id},
        )

        # 8) Verify — NEVER assume success.
        if not result.ok:
            return ExecutionOutcome(
                executed=False,
                reason=f"Order not confirmed by broker (retcode={result.retcode}).",
                stage="execution",
                risk_decision=decision,
                order_result=result,
            )

        self.risk.record_trade_opened()
        self.log.add(
            "position",
            True,
            f"Order executed: ticket {result.order_id}",
            {"order_id": result.order_id, "lots": lots},
        )
        return ExecutionOutcome(
            executed=True,
            reason="Executed.",
            stage="position",
            risk_decision=decision,
            order_result=result,
        )

    def _reject(
        self, stage: str, reason: str, risk_decision: RiskDecision | None = None
    ) -> ExecutionOutcome:
        self.log.add(stage, False, reason, {})
        return ExecutionOutcome(
            executed=False, reason=reason, stage=stage, risk_decision=risk_decision
        )

    # ------------------------------------------------------------- kill switch
    def kill_switch(self, *, cancel_pending: bool = False, close_positions: bool = False) -> dict:
        """EMERGENCY STOP. Always stops new trades immediately.

        Optionally closes open positions / cancels pending orders FIRST (while
        still authorized), then engages the kill (which disarms live trading).
        """
        result = {"closed": 0, "cancelled": 0, "errors": []}
        if close_positions and self.authorization.is_authorized() and self.provider.is_connected():
            try:
                for pos in self.provider.get_positions():
                    r = self.provider.close_position(pos.ticket)
                    if r.ok:
                        result["closed"] += 1
                    else:
                        result["errors"].append(f"close {pos.ticket}: {r.comment}")
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(str(exc))
        if cancel_pending and self.authorization.is_authorized() and self.provider.is_connected():
            cancel = getattr(self.provider, "cancel_order", None)
            if callable(cancel):
                try:
                    for order in self.provider.get_orders():
                        cancel(order.ticket)
                        result["cancelled"] += 1
                except Exception as exc:  # noqa: BLE001
                    result["errors"].append(str(exc))
        # Engage the kill LAST so protective closes could run while authorized.
        self.authorization.kill()
        self.log.add("kill_switch", True, "EMERGENCY STOP engaged — new trades blocked.", result)
        result["killed"] = True
        return result

    def clear_kill(self) -> None:
        self.authorization.clear_kill()
        self.log.add(
            "kill_switch", True, "Kill switch cleared (live trading still requires arming)."
        )
