"""LiveTradingService — risk-gated live execution, manual or automatic (Phase 7+).

Wires: strategy signals -> INDEPENDENT risk engine -> execution coordinator ->
MetaTrader 5. Live execution requires an explicit authorization (config flag +
all confirmations + arm + no kill switch). It can be triggered manually (one
click per trade) OR by the opt-in Auto Trade loop, which runs the SAME pipeline
on a chosen scan interval. Auto Trade still requires full authorization, still
passes every trade through the risk engine, and is stopped instantly by the
kill switch. The authorization and the Auto Trade flag are in-memory, so a
restart disables both (post-restart safety).
"""

from __future__ import annotations

import asyncio
import time
import time as _time

from backend.app.config import get_settings
from backend.app.core.logging_config import get_logger
from backend.app.market_data import get_market_service
from backend.app.mt5 import get_mt5_service
from backend.app.strategy import get_strategy_service
from execution_engine import (
    AutoTradeConfig,
    ExecutionCoordinator,
    LiveAuthorization,
    PositionSynchronizer,
    is_valid_interval_seconds,
    should_scan,
)
from execution_engine.provider import BrokerConnectionError, InvalidSymbolError
from risk_engine import LiveRiskEngine, RiskContext, RiskSettings
from strategy_engine.strategy import MarketContext

logger = get_logger("live")
_PRIMARY_TF = "1h"
# Granularity of the auto-trade loop's wake-ups. The real scan cadence is the
# operator-selected interval; this just bounds how promptly the loop reacts to
# a disarm/kill and to the interval elapsing.
_AUTO_TICK_SECONDS = 1.0


class LiveTradingService:
    def __init__(self) -> None:
        settings = get_settings()
        self.symbol = settings.mt5_symbol
        # Authorization starts DISABLED every process start (restart safety).
        self.authorization = LiveAuthorization(config_enabled=settings.live_execution_enabled)
        self.risk = LiveRiskEngine(RiskSettings())
        # Dry-run defaults ON: the first real-account run validates the full
        # chain (incl. the broker's order_check) but places ZERO orders until
        # the operator explicitly turns it off.
        self.coordinator = ExecutionCoordinator(
            get_mt5_service().provider, self.risk, self.authorization, dry_run=True
        )
        # Tracks open positions so closes (incl. manual closes in the MT5
        # terminal) are journaled as round-trip live trades.
        self._pos_sync = PositionSynchronizer()
        # Auto Trade — OFF by default, resets on restart. When enabled, a
        # background loop runs the SAME risk-gated execution pipeline on the
        # chosen scan interval. It never bypasses authorization or the risk
        # engine and stops the moment live trading is no longer authorized.
        self.auto = AutoTradeConfig()
        self._auto_task: asyncio.Task | None = None
        self._auto_running = False
        self._last_scan_epoch: float | None = None
        self._last_auto_result: dict | None = None
        # False until the first broker sync adopts the positions that already
        # existed at (re)start, so leftover trades aren't misreported as new.
        self._reconciled = False
        # Restore latched halts + running counters so a crash/redeploy cannot
        # silently reset a bad day's loss limits.
        self._load_risk_state()

    # ------------------------------------------------------------- status
    def status(self) -> dict:
        mt5 = get_mt5_service()
        connected = mt5.provider.is_connected()
        last_sync = None
        if connected:
            # Opportunistically reconcile positions so manual closes in the MT5
            # terminal are journaled without a dedicated background loop. Never
            # let a sync failure break the status response.
            try:
                last_sync = self.sync_positions()
            except Exception as exc:  # noqa: BLE001
                logger.debug("opportunistic sync skipped", extra={"context": {"error": str(exc)}})
        return {
            "authorization": self.authorization.status(),
            "risk_settings": self.risk.settings.to_dict(),
            "risk_state": self.risk.state.to_dict(),
            "broker_connected": connected,
            "last_sync": last_sync,
            "symbol": self.symbol,
            "dry_run": self.coordinator.dry_run,
            "auto_execute": self.auto.enabled and self._auto_running,
            "auto_trade": self.auto_status(),
            "disabled_strategies": self.disabled_strategy_keys(),
            "note": (
                "Live execution is gated by the independent risk engine and "
                "requires explicit authorization. Auto Trade (when ON) runs the "
                "same pipeline automatically; the kill switch stops it and a "
                "restart disables it."
            ),
        }

    def auto_status(self) -> dict:
        """Current Auto Trade configuration + runtime state."""
        return {
            **self.auto.to_dict(),
            "running": self._auto_running,
            "last_scan_epoch": self._last_scan_epoch,
            "last_result": self._last_auto_result,
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

    def set_dry_run(self, enabled: bool) -> dict:
        self.coordinator.dry_run = bool(enabled)
        logger.info("Dry-run mode set", extra={"context": {"dry_run": self.coordinator.dry_run}})
        return {"dry_run": self.coordinator.dry_run}

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
        self._persist_risk_state()
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

    def execute_current_signal(self, strategy_key: str | None = None) -> dict:
        """Attempt to execute the best current confirmed signal.

        Runs the full pipeline (authorization -> risk -> validation ->
        execution). Called by a user click OR by the Auto Trade loop; the
        pipeline is identical either way. When ``strategy_key`` is given, only
        that strategy's signals are considered.
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
        # Skip strategies the decay monitor has auto-disabled (edge decayed).
        disabled = set(self.disabled_strategy_keys())
        if strategy_key and strategy_key in disabled:
            return {
                "executed": False,
                "reason": (
                    f"Strategy '{strategy_key}' is auto-disabled due to recent "
                    f"performance decay; not trading it."
                ),
            }
        candidates = result.signals
        if strategy_key:
            candidates = [s for s in candidates if s.get("strategy_key") == strategy_key]
        else:
            candidates = [s for s in candidates if s.get("strategy_key") not in disabled]
        best = next((s for s in candidates if s.get("level", 0) >= 3), None)
        if best is None:
            scope = f" for strategy '{strategy_key}'" if strategy_key else ""
            return {"executed": False, "reason": f"No confirmed setup to execute{scope}."}
        outcome = self.coordinator.execute_signal(best, ctx, spec)
        self._persist(best, outcome)
        if outcome.executed:
            # The coordinator bumped trades_today; persist so the count (and any
            # limit it trips) survives a restart.
            self._persist_risk_state()
        return outcome.to_dict()

    def _persist(self, signal: dict, outcome) -> None:
        """Durably record the evaluated signal and, if executed, the order."""
        try:
            import json

            from backend.app.persistence import StoredOrder, StoredSignal, get_store

            store = get_store()
            store.save_signal(
                StoredSignal(
                    strategy_key=signal.get("strategy_key", "unknown"),
                    symbol=signal.get("symbol", self.symbol),
                    timeframe=signal.get("timeframe"),
                    level=int(signal.get("level", 0)),
                    direction=signal.get("direction"),
                    regime=signal.get("regime"),
                    confidence_score=signal.get("confidence_score"),
                    reasoning=json.dumps(
                        {
                            "confirmations": signal.get("confirmations"),
                            "missing": signal.get("missing_confirmations"),
                            "invalidation": signal.get("invalidation"),
                        }
                    ),
                )
            )
            if outcome.executed and outcome.order_result is not None:
                sizing = outcome.risk_decision.sizing if outcome.risk_decision else None
                store.save_order(
                    StoredOrder(
                        account_label="Live",
                        symbol=signal.get("symbol", self.symbol),
                        side="buy" if signal.get("direction") == "long" else "sell",
                        order_type="market",
                        volume_lots=sizing.lots if sizing else 0.0,
                        price=outcome.order_result.price,
                        stop_loss=signal.get("stop_loss"),
                        take_profit=(signal.get("take_profits") or [None])[0],
                        status="filled",
                        mode="live",
                        broker_order_id=outcome.order_result.order_id,
                        retcode=outcome.order_result.retcode,
                        comment=outcome.order_result.comment,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - persistence must never block execution
            logger.debug("live persistence skipped", extra={"context": {"error": str(exc)}})

    def history(self, limit: int = 100) -> dict:
        try:
            from backend.app.persistence import get_store

            store = get_store()
            return {
                "signals": store.recent_signals(limit),
                "orders": store.recent_orders(limit),
                "trades": store.recent_trades(limit),
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "signals": [], "orders": [], "trades": []}

    def execution_log(self, limit: int = 100) -> dict:
        return {"log": self.coordinator.log.recent(limit)}

    # ------------------------------------------------------------- position sync
    def sync_positions(self) -> dict:
        """Reconcile broker positions; journal any that closed (incl. manual).

        Detects opened / modified / closed positions vs the last snapshot. Each
        CLOSED position is persisted as a round-trip live trade with its P&L,
        so trades you close directly in MetaTrader are reflected here too.
        """
        provider = get_mt5_service().provider
        if not provider.is_connected():
            return {"synced": False, "reason": "MetaTrader 5 is not connected."}
        try:
            positions = provider.get_positions()
        except BrokerConnectionError as exc:
            return {"synced": False, "reason": str(exc)}

        # First sync after (re)start: ADOPT the positions that already existed
        # as the baseline instead of reporting them as brand-new opens. This is
        # startup reconciliation — leftover/manual positions are accounted for,
        # and the risk engine's equity peak is (re)seeded from the account.
        if not self._reconciled:
            self._pos_sync.diff(positions)  # seed baseline silently
            self._reconciled = True
            equity = self._broker_equity()
            if equity is not None:
                self.risk.roll_periods(_time.time(), equity)
                self.risk.update_equity(equity)
                self._persist_risk_state()
            self.coordinator.log.add(
                "reconcile",
                True,
                f"Startup reconciliation: adopted {len(positions)} open position(s).",
                {"open_positions": len(positions), "equity": equity},
            )
            return {"synced": True, "reconciled": True, "adopted": len(positions)}

        diff = self._pos_sync.diff(positions)
        if diff.closed:
            self._persist_closed(diff.closed)
            self._record_closed_pnl(diff.closed)
        for pos in diff.opened:
            self.coordinator.log.add(
                "position_synced",
                True,
                f"Position opened: {pos.side} {pos.volume} {pos.symbol}",
                {"ticket": pos.ticket},
            )
        for pos in diff.closed:
            self.coordinator.log.add(
                "position_closed",
                True,
                f"Position closed: {pos.side} {pos.volume} {pos.symbol} (P&L {pos.profit})",
                {"ticket": pos.ticket, "pnl": pos.profit},
            )
        return {"synced": True, **diff.to_dict()}

    def _broker_equity(self) -> float | None:
        """Best-effort current account equity from the broker, or None."""
        try:
            acc = get_mt5_service().provider.get_account_info()
            return float(acc.equity or 0.0)
        except Exception:  # noqa: BLE001
            return None

    def _record_closed_pnl(self, closed_positions) -> None:
        """Feed realized P&L from closed positions into the risk engine.

        This is what makes the daily/weekly loss limits actually track live
        results (previously nothing called ``record_trade_closed`` in the live
        path). Persists the updated risk state so the halts survive a restart.
        """
        equity = self._broker_equity()
        # If the account read failed, fall back to the known peak equity so we
        # don't fabricate a ~100% drawdown (which would falsely trip the halt).
        safe_equity = equity if equity is not None else self.risk.state.peak_equity
        for pos in closed_positions:
            pnl = getattr(pos, "profit", None)
            if pnl is None:
                continue
            self.risk.record_trade_closed(float(pnl), safe_equity)
        self._persist_risk_state()

    def _persist_closed(self, closed_positions) -> None:
        try:
            from backend.app.persistence import get_store
            from backend.app.persistence.store import stored_trade_from_position

            store = get_store()
            now = _time.time()
            for pos in closed_positions:
                store.save_trade(stored_trade_from_position(pos, mode="live", closed_epoch=now))
        except Exception as exc:  # noqa: BLE001 - persistence must never break sync
            logger.debug(
                "closed-position persistence skipped", extra={"context": {"error": str(exc)}}
            )

    # ------------------------------------------------------------- risk state
    def _load_risk_state(self) -> None:
        """Restore persisted risk state on startup (best-effort)."""
        try:
            from backend.app.persistence import get_store

            saved = get_store().load_risk_state()
            if saved:
                self.risk.restore_state(saved)
                logger.info(
                    "Restored risk state",
                    extra={"context": {"state": self.risk.state.to_dict()}},
                )
        except Exception as exc:  # noqa: BLE001 - never block startup
            logger.debug("risk-state restore skipped", extra={"context": {"error": str(exc)}})

    def _persist_risk_state(self) -> None:
        """Durably save the current risk state (best-effort)."""
        try:
            from backend.app.persistence import get_store

            get_store().save_risk_state(self.risk.state.to_dict())
        except Exception as exc:  # noqa: BLE001 - persistence must never block trading
            logger.debug("risk-state persist skipped", extra={"context": {"error": str(exc)}})

    # ------------------------------------------------------------- decay monitor
    def strategy_health(self, limit: int = 500) -> dict:
        """Per-strategy health from recent realized trades (decay monitoring).

        Strategies whose edge has decayed are flagged ``degraded`` and are
        automatically skipped by live execution / Auto Trade until they recover
        or are re-validated. Never judges on a tiny sample.
        """
        try:
            from analytics import monitor_strategies
            from backend.app.persistence import get_store

            # recent_trades is newest-first; the monitor needs chronological
            # order so trailing losing streaks and the recency window are right.
            trades = list(reversed(get_store().recent_trades(limit)))
            return {"strategies": monitor_strategies(trades)}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "strategies": {}}

    def disabled_strategy_keys(self) -> list[str]:
        """Strategy keys currently auto-disabled by the decay monitor."""
        try:
            from analytics import disabled_keys

            return disabled_keys(self.strategy_health().get("strategies", {}))
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------- auto trade
    async def set_auto_trade(
        self,
        *,
        enabled: bool,
        interval_seconds: int | None = None,
        strategy_key: str | None = None,
    ) -> dict:
        """Turn Auto Trade on/off and configure its scan interval + strategy.

        Enabling requires live trading to already be authorized (armed with all
        confirmations, config enabled, no kill). This is the SAME bar as a
        manual execution — Auto Trade just repeats it automatically.
        """
        if enabled:
            if not self.authorization.is_authorized():
                return {
                    "error": (
                        "Arm live trading (complete confirmations + ENABLE) "
                        "before turning Auto Trade on."
                    ),
                    "auto_trade": self.auto_status(),
                }
            if interval_seconds is not None:
                if not is_valid_interval_seconds(int(interval_seconds)):
                    return {
                        "error": "Invalid scan interval.",
                        "auto_trade": self.auto_status(),
                    }
                self.auto.interval_seconds = int(interval_seconds)
            self.auto.strategy_key = strategy_key
            self.auto.enabled = True
            self._last_scan_epoch = None  # scan promptly on enable
            await self._start_auto()
            self.coordinator.log.add(
                "auto_trade",
                True,
                (
                    f"Auto Trade ENABLED (every "
                    f"{self.auto.to_dict()['interval_label']}, strategy="
                    f"{strategy_key or 'best-of-all'}). Dry-run="
                    f"{self.coordinator.dry_run}."
                ),
                self.auto.to_dict(),
            )
        else:
            self.auto.enabled = False
            await self._stop_auto()
            self.coordinator.log.add("auto_trade", True, "Auto Trade DISABLED by user.")
        return {"auto_trade": self.auto_status()}

    async def _start_auto(self) -> None:
        if self._auto_running:
            return
        self._auto_running = True
        self._auto_task = asyncio.create_task(self._auto_loop(), name="auto-trade-loop")

    async def _stop_auto(self) -> None:
        self._auto_running = False
        task = self._auto_task
        self._auto_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _auto_loop(self) -> None:
        """Background loop: on each due scan, run the full execution pipeline.

        Non-blocking: the (synchronous, I/O-bound) scan runs in a thread so the
        event loop stays responsive. The loop self-terminates the instant live
        trading is no longer authorized (kill switch, disarm or restart).
        """
        loop = asyncio.get_event_loop()
        while self._auto_running:
            try:
                if not self.authorization.is_authorized():
                    self.coordinator.log.add(
                        "auto_trade",
                        False,
                        "Auto Trade stopped: live trading is no longer authorized.",
                    )
                    self._auto_running = False
                    self.auto.enabled = False
                    break
                now = _time.time()
                if should_scan(now, self._last_scan_epoch, self.auto.interval_seconds):
                    self._last_scan_epoch = now
                    result = await loop.run_in_executor(None, self._auto_scan_once)
                    self._last_auto_result = result
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a scan error must not kill the loop
                logger.error("Auto-trade loop error", extra={"context": {"error": str(exc)}})
            await asyncio.sleep(_AUTO_TICK_SECONDS)

    def _auto_scan_once(self) -> dict:
        """One automatic scan+execute cycle (runs in a worker thread)."""
        result = self.execute_current_signal(strategy_key=self.auto.strategy_key)
        if not result.get("executed"):
            # Log only the non-trivial outcomes to keep the log readable.
            reason = result.get("reason", "")
            self.coordinator.log.add("auto_scan", True, f"Auto scan: {reason}", {"result": result})
        return result


_service: LiveTradingService | None = None


def get_live_service() -> LiveTradingService:
    global _service
    if _service is None:
        _service = LiveTradingService()
    return _service
