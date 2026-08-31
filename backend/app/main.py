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
        extra={"context": {"phase": 1, "mode": "analysis_only", "env": settings.app_env}},
    )
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="XAUUSD trading intelligence platform — Phase 1 (analysis only).",
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
            "phase": 1,
            "mode": "analysis_only",
            "live_trading_implemented": False,
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

    return app


app = create_app()
