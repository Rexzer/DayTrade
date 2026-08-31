"""WebSocket connection manager (real-time infrastructure).

Phase 1 provides the plumbing for real-time updates. Since no live market
data is connected yet, the server periodically broadcasts an honest status
frame ("disconnected") rather than any price. Phase 2+ pushes real snapshots.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON frames."""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message, default=str)
        stale: list[WebSocket] = []
        async with self._lock:
            targets = list(self._active)
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001 - client vanished mid-send
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._active.discard(ws)

    @property
    def count(self) -> int:
        return len(self._active)


manager = ConnectionManager()
