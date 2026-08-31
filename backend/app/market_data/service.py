"""MarketDataService — real-time orchestration (Phase 2).

Responsibilities:
    * Build the configured provider (none / simulated / rest).
    * Maintain a CandleAggregator per timeframe (UTC-aligned).
    * Track feed health and gate signals when data is STALE/DISCONNECTED.
    * Drive the reconnection state machine: detect drop -> notify -> reconnect
      with backoff -> backfill missed candles -> resume LIVE.
    * Persist closed candles (best-effort; the platform still works in-memory
      if the DB is unavailable).
    * Broadcast ticks, closed candles and health over a WebSocket manager.

Safety: this is MARKET DATA ONLY. Nothing here can place an order. When no
provider is configured it stays fully disconnected and never fabricates data.
Simulated data is always tagged source="simulated" so the UI can label it.
"""

from __future__ import annotations

import asyncio
import time

from backend.app.config import Settings, get_settings
from backend.app.core.logging_config import get_logger
from backend.app.websocket.manager import ConnectionManager
from market_data import (
    CandleAggregator,
    FeedHealthMonitor,
    MarketDataProvider,
    NullMarketDataProvider,
    ReconnectionController,
    SimulatedMarketDataProvider,
    SymbolMapper,
    Timeframe,
)
from market_data.provider import Candle
from market_data.reconnection import plan_backfill
from market_data.tick import Tick

logger = get_logger("market_data")


class MarketDataService:
    """Owns the live market-data pipeline for one symbol."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.symbol = "XAUUSD"  # canonical
        self.mapper = SymbolMapper()
        self.mapper.set_broker_symbol(self.settings.market_data_symbol)

        self.provider: MarketDataProvider = self._build_provider()
        self.aggregators: dict[Timeframe, CandleAggregator] = {
            tf: CandleAggregator(tf) for tf in Timeframe.ordered()
        }
        self.health = FeedHealthMonitor(
            source=self.provider.name,
            delayed_after_seconds=self.settings.data_delayed_after_seconds,
            stale_after_seconds=self.settings.data_stale_after_seconds,
        )
        self.recon = ReconnectionController()
        self.manager = ConnectionManager()

        self._task: asyncio.Task | None = None
        self._running = False
        self._last_tick: Tick | None = None

    # --------------------------------------------------------------- provider
    def _build_provider(self) -> MarketDataProvider:
        kind = (self.settings.market_data_provider or "none").lower()
        if kind == "simulated":
            logger.info("Using SIMULATED market-data provider (labelled, not real data)")
            return SimulatedMarketDataProvider(broker_symbol=self.settings.market_data_symbol)
        if kind == "rest":
            # Real provider requires network + config; imported lazily.
            from market_data.providers import GenericRestProvider, RestProviderConfig

            logger.info("Using REST market-data provider")
            return GenericRestProvider(
                RestProviderConfig(
                    url="",  # operator must configure this (env-driven wiring TBD)
                    broker_symbol=self.settings.market_data_symbol,
                )
            )
        return NullMarketDataProvider()

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._running:
            return
        if isinstance(self.provider, NullMarketDataProvider):
            logger.info("Market data provider is 'none'; staying disconnected.")
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="market-data-loop")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        try:
            self.provider.disconnect()
        except Exception:  # noqa: BLE001
            pass

    # --------------------------------------------------------------- main loop
    async def _run(self) -> None:
        interval = max(0.05, self.settings.market_tick_interval_seconds)
        try:
            self.recon.begin_connect()
            self.provider.connect()
            self._seed_history()
            self.recon.on_connected()  # initial connect (not a reconnect)
        except Exception as exc:  # noqa: BLE001
            logger.error("Initial connect failed", extra={"context": {"error": str(exc)}})

        while self._running:
            try:
                tick = self._next_tick()
                if tick is not None:
                    await self._on_tick(tick)
                    if not self.recon.is_live():
                        self.recon.mark_live()
                await self._broadcast_health()
            except Exception as exc:  # noqa: BLE001 - any feed error -> reconnect
                logger.error("Feed error; reconnecting", extra={"context": {"error": str(exc)}})
                await self._handle_disconnect()
            await asyncio.sleep(interval)

    def _next_tick(self) -> Tick | None:
        if isinstance(self.provider, SimulatedMarketDataProvider):
            return self.provider.generate_tick(time.time())
        # REST/other providers expose poll(); fall back to get_tick.
        poll = getattr(self.provider, "poll", None)
        if callable(poll):
            return poll()
        return self.provider.get_tick(self.symbol)

    async def _on_tick(self, tick: Tick) -> None:
        self._last_tick = tick
        self.health.mark_update(tick.timestamp_epoch)
        closed: list[tuple[Timeframe, Candle]] = []
        for tf, agg in self.aggregators.items():
            result = agg.add_tick(tick)
            if result.closed_candle is not None:
                closed.append((tf, result.closed_candle))
        # Persist newly-closed candles (best-effort) and announce them.
        for tf, candle in closed:
            self._persist_candle(candle)
            await self.manager.broadcast(
                {"type": "candle_closed", "timeframe": tf.value, "candle": candle.to_dict()}
            )
        await self.manager.broadcast(
            {
                "type": "tick",
                "tick": tick.to_dict(),
                "health": self.health.health().to_dict(),
                "connection_state": self.recon.state.value,
            }
        )

    async def _broadcast_health(self) -> None:
        # Periodic health frame so clients see STALE even without new ticks.
        if not self.health.signals_allowed():
            await self.manager.broadcast(
                {"type": "health", "health": self.health.health().to_dict()}
            )

    # --------------------------------------------------------- reconnection
    async def _handle_disconnect(self) -> None:
        self.recon.on_disconnected()
        self.health.reset()
        await self.manager.broadcast(
            {
                "type": "status",
                "connection_state": self.recon.state.value,
                "market_data": "disconnected",
            }
        )
        wait = self.recon.begin_reconnect()
        await asyncio.sleep(min(wait, 5.0))  # cap sleep so shutdown stays responsive
        try:
            self.provider.connect()
            self.recon.on_connected()  # -> BACKFILLING (was reconnecting)
            self._backfill()
            self.recon.on_backfill_complete()  # -> LIVE
            await self.manager.broadcast(
                {
                    "type": "status",
                    "connection_state": self.recon.state.value,
                    "market_data": "live",
                }
            )
        except Exception as exc:  # noqa: BLE001 - stay disconnected, retry next loop
            logger.error("Reconnect attempt failed", extra={"context": {"error": str(exc)}})
            self.recon.on_disconnected()

    def _backfill(self) -> None:
        """Fetch candles missed while offline; never resume with gaps silently."""
        now = time.time()
        for tf, agg in self.aggregators.items():
            window_start = now - 3600  # look back one hour for gaps
            missing = agg.missing_buckets(window_start, now)
            if not missing:
                continue
            ordered = plan_backfill(missing)
            fetched = self.provider.get_historical_candles(
                self.mapper.spec.broker_symbol, tf, limit=len(ordered) + 5, end_epoch=now
            )
            wanted = set(ordered)
            for c in fetched:
                if int(c.open_time_epoch) in wanted:
                    agg.add_price(c.close, c.open_time_epoch, c.volume)
                    self._persist_candle(c)
            logger.info(
                "Backfilled candles",
                extra={"context": {"timeframe": tf.value, "count": len(fetched)}},
            )

    # --------------------------------------------------------------- history
    def _seed_history(self) -> None:
        limit = self.settings.market_history_candles
        broker_symbol = self.mapper.spec.broker_symbol
        for tf, agg in self.aggregators.items():
            try:
                history = self.provider.get_historical_candles(
                    broker_symbol, tf, limit=limit, end_epoch=time.time()
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "History load failed",
                    extra={"context": {"timeframe": tf.value, "error": str(exc)}},
                )
                continue
            if history:
                agg.seed(history)
                self._persist_candles(history)

    # --------------------------------------------------------------- storage
    def _persist_candle(self, candle: Candle) -> None:
        self._persist_candles([candle])

    def _persist_candles(self, candles: list[Candle]) -> None:
        """Best-effort persistence; failures never break the live pipeline."""
        if not candles:
            return
        try:
            from backend.app.db.candle_repository import CandleRepository
            from backend.app.db.session import SessionLocal

            db = SessionLocal()
            try:
                repo = CandleRepository(db)
                repo.bulk_upsert(self.symbol, candles, source=self.provider.name)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 - DB optional for live analysis
            logger.debug("Candle persistence skipped", extra={"context": {"error": str(exc)}})

    # ---------------------------------------------------------------- queries
    def status(self) -> dict:
        connected = self.provider.is_connected()
        return {
            "symbol": self.symbol,
            "broker_symbol": self.mapper.spec.broker_symbol,
            "source": self.provider.name,
            "provider_kind": self.settings.market_data_provider,
            "connected": connected,
            "connection_state": self.recon.state.value,
            "health": self.health.health().to_dict(),
            "last_update_epoch": self.health.health().last_update_epoch,
            "simulated": self.provider.name == "simulated",
        }

    def snapshot(self) -> dict:
        snap = self.provider.get_snapshot(self.mapper.spec.broker_symbol)
        d = snap.to_dict()
        d["symbol"] = self.symbol
        d["data_status"] = self.health.status().value
        d["connection_state"] = self.recon.state.value
        d["simulated"] = self.provider.name == "simulated"
        return d

    def get_candles(self, timeframe: Timeframe, limit: int = 300) -> list[dict]:
        agg = self.aggregators.get(timeframe)
        if agg is None:
            return []
        return [c.to_dict() for c in agg.latest(limit)]

    def symbols(self) -> dict:
        return {
            "canonical": self.symbol,
            "active_broker_symbol": self.mapper.spec.broker_symbol,
            "known_aliases": self.mapper.known_aliases(),
        }

    def set_symbol(self, broker_symbol: str) -> dict:
        self.mapper.set_broker_symbol(broker_symbol)
        return self.symbols()


_service: MarketDataService | None = None


def get_market_service() -> MarketDataService:
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
