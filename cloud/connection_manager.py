"""WebSocket connection manager for broadcasting real-time events.

Broadcasts task/machine/issue status changes to connected frontend clients.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self):
        # Map: room_name -> set of websockets
        self._rooms: dict[str, set[WebSocket]] = {}
        self._global: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, room: str | None = None) -> None:
        await websocket.accept()
        self._global.add(websocket)
        if room:
            self._rooms.setdefault(room, set()).add(websocket)
        logger.info(f"WebSocket connected. Global={len(self._global)}, Room={room}")

    def disconnect(self, websocket: WebSocket, room: str | None = None) -> None:
        self._global.discard(websocket)
        if room and room in self._rooms:
            self._rooms[room].discard(websocket)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.info(f"WebSocket disconnected. Global={len(self._global)}")

    async def broadcast(
        self, event_type: str, payload: dict[str, Any], room: str | None = None
    ) -> None:
        """Broadcast an event to all connected clients (or a specific room)."""
        message = {"type": event_type, "payload": payload}
        targets = self._rooms.get(room, self._global) if room else self._global
        if not targets:
            return

        # Send concurrently; catch disconnects
        coros = [self._send_safe(ws, message) for ws in list(targets)]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for ws, result in zip(list(targets), results):
            if isinstance(result, Exception):
                targets.discard(ws)
                self._global.discard(ws)

    async def _send_safe(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)


# Global singleton
manager = ConnectionManager()
