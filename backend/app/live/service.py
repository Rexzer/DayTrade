"""LiveTradingService — user-initiated, risk-gated live execution (Phase 7).

Wires: strategy signals -> INDEPENDENT risk engine -> execution coordinator ->
MetaTrader 5. Live execution requires an explicit authorization (config flag +
all confirmations + arm + no kill switch) and is only ever triggered by a user
action — the platform never auto-executes trades. The authorization is
in-memory, so a restart disables live trading (post-restart safety).
"""

from __future__ import annotations

import time

from backend.app.config import get_settings
from backend.app.core.logging_config import get_logger
from backend.app.market_data import get_market_service
from backend.app.mt5 import get_mt5_service
from backend.app.strategy import get_strategy_service
from execution_engine import ExecutionCoordinator, LiveAuthorization
from execution_engine.provider import BrokerConnectionError, InvalidSymbolError
from risk_engine import LiveRiskEngine, RiskContext, RiskSettings
from strategy_engine.strategy import MarketContext

logger = get_logger("live")
_PRIMARY_TF = "1h"


class LiveTradingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.symbol = settings.mt5_symbol
        # Authorization starts DISABLED every process start (restart safety).
        self.authorization = LiveAuthorization(config_enabled=settings.live_execution_enabled)
        self.risk = LiveRiskEngine(RiskSettings())
        self.coordinator = ExecutionCoordinator(
            get_mt5_service().provider, self.risk, self.authorization
        )

    # ------------------------------------------------------------- status
    def status(self) -> dict:
        mt5 = get_mt5_service()
        return {
            "authorization": self.authorization.status(),
            "risk_settings": self.risk.settings.to_dict(),
            "risk_state": self.risk.state.to_dict(),
            "broker_connected": mt5.provider.is_connected(),
            "symbol": self.symbol,
            "auto_execute": False,  # the platform NEVER auto-executes
            "note": (
                "Live execution is user-initiated and gated by the independent "
                "risk engine. A restart disables live trading."
            ),
        }

    # ------------------------------------------------------------- authz flow
    def confirm(self, key: str, value: bool) -> dict:
        self.authorization.confirm(key, value)
        return self.authorization.status()

    def set_confirmations(self, confirmations: dict) -> dict:
        self.authorization.set_confirmations(confirmations)
        return self.authorization.status()

    def enable(self) -> dict:
        """Arm live trading (the 'ENABLE LIVE TRADING' action)."""
        try:
            self.authorization.arm()
            logger.info("Live trading ARMED by user.")
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "authorization": self.authorization.status()}
        return {"armed": True, "authorization": self.authorization.status()}

    def disable(self) -> dict:
        self.authorization.disable()
        logger.info("Live trading disarmed by user.")
        return {"armed": False, "authorization": self.authorization.status()}

    # ------------------------------------------------------------- kill switch
    def kill(self, cancel_pending: bool = False, close_positions: bool = False) -> dict:
        logger.info(
            "KILL SWITCH engaged",
            extra={
                "context": {"cancel_pending": cancel_pending, "close_positions": close_positions}
            },
        )
        return self.coordinator.kill_switch(
            cancel_pending=cancel_pending, close_positions=close_positions
        )

    def clear_kill(self) -> dict:
        self.coordinator.clear_kill()
        return self.authorization.status()

    # ------------------------------------------------------------- risk config
    def set_risk(self, settings_dict: dict) -> dict:
        current = self.risk.settings.to_dict()
        current.update({k: v for k, v in (settings_dict or {}).items() if k in current})
        new_settings = RiskSettings(**current)
        errors = new_settings.validate()
        if errors:
            return {"error": "Invalid risk settings", "details": errors}
        self.risk.update_settings(new_settings)
        # Changing risk requires re-confirming that limits were configured.
        self.authorization.confirm("configured_risk_limits", False)
        return {"risk_settings": new_settings.to_dict()}

    def reset_risk_halts(self) -> dict:
        self.risk.manual_reset()
        return {"risk_state": self.risk.state.to_dict()}

    # ------------------------------------------------------------- execution
    def _build_context(self) -> tuple[RiskContext, object] | tuple[None, None]:
        market = get_market_service()
        mt5 = get_mt5_service()
        provider = mt5.provider
        snap = market.snapshot()
        price = snap.get("last") or snap.get("bid")
        try:
            spec = provider.get_symbol_spec(self.symbol)
        except (InvalidSymbolError, BrokerConnectionError):
            spec = None
        equity = 0.0
        try:
            acc = provider.get_account_info()
            equity = float(acc.equity or 0.0)
        except BrokerConnectionError:
            equity = 0.0
        spread_points = None
        if spec is not None and snap.get("spread") is not None and spec.point:
            spread_points = float(snap["spread"]) / float(spec.point)
        positions = []
        try:
            positions = provider.get_positions()
        except BrokerConnectionError:
            positions = []
        xau = sum(1 for p in positions if p.symbol == self.symbol)
        ctx = RiskContext(
            equity=equity,
            spread_points=spread_points if spread_points is not None else 1e9,
            price=price,
            data_status=market.data_status_str(),
            broker_connected=provider.is_connected(),
            now_epoch=time.time(),
            open_positions=len(positions),
            open_xauusd_positions=xau,
        )
        return ctx, spec

    def execute_current_signal(self) -> dict:
        """USER-INITIATED: attempt to execute the best current confirmed signal.

        Runs the full pipeline (authorization -> risk -> validation ->
        execution). Never called automatically.
        """
        if not self.authorization.is_authorized():
            return {"executed": False, "reason": "Live execution is not authorized."}
        ctx, spec = self._build_context()
        if spec is None:
            return {"executed": False, "reason": "Broker symbol spec unavailable (connect MT5)."}
        market = get_market_service()
        result = get_strategy_service().engine.evaluate_all(
            MarketContext(symbol="XAUUSD", candles=market.candles_by_timeframe(300)),
            data_status=market.data_status_str(),
            primary_timeframe=_PRIMARY_TF,
        )
        if not result.signals_allowed:
            return {"executed": False, "reason": result.reason}
        best = next((s for s in result.signals if s.get("level", 0) >= 3), None)
        if best is None:
            return {"executed": False, "reason": "No confirmed setup to execute."}
        outcome = self.coordinator.execute_signal(best, ctx, spec)
        return outcome.to_dict()

    def execution_log(self, limit: int = 100) -> dict:
        return {"log": self.coordinator.log.recent(limit)}


_service: LiveTradingService | None = None


def get_live_service() -> LiveTradingService:
    global _service
    if _service is None:
        _service = LiveTradingService()
    return _service
