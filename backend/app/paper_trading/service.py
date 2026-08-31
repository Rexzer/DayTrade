"""PaperTradingService — live-data paper trading (Phase 5).

Wires the PaperTradingEngine to the market feed (ticks drive execution; closed
candles drive signal evaluation) and the strategy engine (only CONFIRMED
setups on the primary timeframe are auto-traded). Everything is simulated — no
real order can ever be placed.

Auto-trading only runs while the service is ACTIVE. When inactive it still
tracks prices so equity/positions stay live, but generates no new entries.
"""

from __future__ import annotations

from backend.app.core.logging_config import get_logger
from backend.app.market_data import get_market_service
from backend.app.strategy import get_strategy_service
from paper_trading import PaperAccountConfig, PaperTradingEngine
from strategy_engine.strategy import MarketContext

logger = get_logger("paper")

_PRIMARY_TF = "1h"


class PaperTradingService:
    def __init__(self) -> None:
        self.engine = PaperTradingEngine(PaperAccountConfig())
        self.active = False
        self._wired = False
        self._persist_cursor = 0

    def _flush_to_store(self) -> None:
        """Persist any newly-closed paper trades durably (best-effort)."""
        closed = self.engine.account.closed_trades
        if len(closed) <= self._persist_cursor:
            return
        try:
            from backend.app.persistence import StoredTrade, get_store

            store = get_store()
            for t in closed[self._persist_cursor :]:
                store.save_trade(
                    StoredTrade(
                        strategy_key=t.strategy_key,
                        symbol="XAUUSD",
                        side=t.direction,
                        volume_lots=t.lots,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        pnl=t.pnl,
                        exit_reason=t.exit_reason,
                        regime=t.regime,
                        mode="paper",
                        opened_epoch=t.opened_epoch,
                        closed_epoch=t.closed_epoch,
                    )
                )
            self._persist_cursor = len(closed)
        except Exception:  # noqa: BLE001 - persistence must not break paper trading
            pass

    # ------------------------------------------------------------- wiring
    def wire(self) -> None:
        """Register listeners on the market service (idempotent)."""
        if self._wired:
            return
        market = get_market_service()
        market.add_tick_listener(self._on_tick)
        market.add_candle_listener(self._on_candle)
        self._wired = True

    def _on_tick(self, tick) -> None:
        bid = tick.bid if tick.bid is not None else tick.price
        ask = tick.ask if tick.ask is not None else tick.price
        if bid is None or ask is None:
            return
        self.engine.on_price(float(bid), float(ask), float(tick.timestamp_epoch))
        # SL/TP closes happen on price updates — persist any new closed trades.
        self._flush_to_store()

    def _on_candle(self, timeframe: str, candle) -> None:
        # Auto-trade only on the primary timeframe close, and only when active.
        if not self.active or timeframe != _PRIMARY_TF:
            return
        market = get_market_service()
        if not market.health.signals_allowed():
            return
        ctx = MarketContext(symbol="XAUUSD", candles=market.candles_by_timeframe(300))
        try:
            result = get_strategy_service().engine.evaluate_all(
                ctx, data_status=market.data_status_str(), primary_timeframe=_PRIMARY_TF
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Paper signal eval failed", extra={"context": {"error": str(exc)}})
            return
        if not result.signals_allowed:
            return
        # Feed the single best actionable signal to the engine.
        for sig in result.signals:
            if sig.get("level", 0) >= self.engine.config.min_signal_level:
                self.engine.on_signal(sig, sig.get("strategy_name"))
                break

    # ------------------------------------------------------------- controls
    def start(self, config_overrides: dict | None = None) -> dict:
        self.wire()
        if config_overrides:
            cfg = self._build_config(config_overrides)
            errors = cfg.validate()
            if errors:
                return {"error": "Invalid config", "details": errors}
            self.engine.update_config(cfg)
        self.active = True
        self.engine.account.paused = False
        return {"active": True, **self.engine.state()}

    def _build_config(self, overrides: dict) -> PaperAccountConfig:
        cfg = PaperAccountConfig()
        for k, v in (overrides or {}).items():
            if hasattr(cfg, k) and v is not None:
                setattr(cfg, k, v)
        return cfg

    def pause(self) -> dict:
        self.engine.pause()
        return {"paused": True}

    def resume(self) -> dict:
        self.engine.resume()
        return {"paused": False}

    def stop(self) -> dict:
        self.active = False
        return {"active": False}

    def reset(self) -> dict:
        self.engine.reset()
        self._persist_cursor = 0
        return self.engine.state()

    def close_position(self, position_id: str) -> dict:
        ok = self.engine.close_position(position_id)
        self._flush_to_store()
        return {"closed": ok, "position_id": position_id}

    def close_all(self) -> dict:
        n = self.engine.close_all()
        self._flush_to_store()
        return {"closed_count": n}

    # ------------------------------------------------------------- views
    def state(self) -> dict:
        return {"active": self.active, **self.engine.state()}

    def performance(self) -> dict:
        return self.engine.performance()

    def trades(self, limit: int = 100) -> dict:
        return {"trades": self.engine.closed_trades(limit)}

    def journal(self, limit: int = 50, kind: str | None = None) -> dict:
        return {"journal": self.engine.journal_entries(limit, kind)}


_service: PaperTradingService | None = None


def get_paper_service() -> PaperTradingService:
    global _service
    if _service is None:
        _service = PaperTradingService()
    return _service
