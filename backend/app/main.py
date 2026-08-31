"""FastAPI application entrypoint (Phase 1 — analysis only).

Wires together routers, CORS, structured logging, and a status WebSocket.
Enforces the Phase 1 invariant at startup: the app refuses to boot if live
trading has been enabled via configuration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import (
    account,
    auth,
    health,
    market,
    mode,
    news,
    strategies,
)
from backend.app.api.routes import (
    settings as settings_route,
)
from backend.app.config import get_settings
from backend.app.core.logging_config import configure_logging, get_logger
from backend.app.market_data import get_market_service
from backend.app.websocket.manager import manager

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging("DEBUG" if settings.app_debug else "INFO")

    problems = settings.validate()
    if problems:
        # Fail closed on any Phase 1 safety violation (e.g. live trading on).
        for p in problems:
            logger.error("Configuration problem", extra={"context": {"problem": p}})
        if settings.enable_live_trading:
            raise RuntimeError(
                "Refusing to start: ENABLE_LIVE_TRADING is true but live trading "
                "is not implemented in Phase 1."
            )
    logger.info(
        "Application starting",
        extra={
            "context": {
                "phase": 2,
                "mode": "analysis_only",
                "env": settings.app_env,
                "market_data_provider": settings.market_data_provider,
            }
        },
    )

    # Start the real-time market-data pipeline (no-op if provider is "none").
    market = get_market_service()
    await market.start()
    try:
        yield
    finally:
        await market.stop()
        logger.info("Application shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "XAUUSD trading intelligence platform — Phase 2 "
            "(real-time market data; analysis only, no trading)."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_routers = [
        health.router,
        auth.router,
        mode.router,
        market.router,
        account.router,
        strategies.router,
        news.router,
        settings_route.router,
    ]
    for r in api_routers:
        app.include_router(r, prefix="/api")

    @app.get("/")
    def root() -> dict:
        return {
            "app": settings.app_name,
            "phase": 2,
            "mode": "analysis_only",
            "live_trading_implemented": False,
            "market_data_provider": settings.market_data_provider,
            "docs": "/docs",
        }

    @app.websocket("/ws/status")
    async def ws_status(websocket: WebSocket) -> None:
        """Push honest connection status frames. No prices in Phase 1."""
        await manager.connect(websocket)
        try:
            await websocket.send_json(
                {
                    "type": "status",
                    "market_data": "disconnected",
                    "account": "disconnected",
                    "mode": "analysis_only",
                    "note": "No live market data connected in Phase 1.",
                }
            )
            while True:
                # Echo/keepalive; real snapshots are pushed in later phases.
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(websocket)

    @app.websocket("/ws/market")
    async def ws_market(websocket: WebSocket) -> None:
        """Stream real-time ticks, closed candles and feed health.

        The MarketDataService broadcasts to all connected clients. On connect
        we send the current status so the UI can render immediately (honestly
        "disconnected" if no provider is configured).
        """
        market = get_market_service()
        await market.manager.connect(websocket)
        try:
            await websocket.send_json({"type": "status", **market.status()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await market.manager.disconnect(websocket)

    return app


app = create_app()
