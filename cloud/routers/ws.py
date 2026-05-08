"""WebSocket endpoint for real-time push notifications."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from config import get_settings
from connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

HEARTBEAT_INTERVAL = 30.0


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str = Query(..., description="API Key for authentication"),
):
    """Establish a WebSocket connection for real-time updates.

    Authentication is done via query parameter `?api_key=...`.
    The server sends heartbeat pings every 30s; clients should reply with pong.
    Messages are JSON: {"type": "event_name", "payload": {...}}.
    """
    # Authenticate
    settings = get_settings()
    if api_key != settings.API_KEY:
        await websocket.close(code=1008, reason="Invalid API Key")
        return

    await manager.connect(websocket)
    try:
        while True:
            # Wait for message with heartbeat timeout
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=HEARTBEAT_INTERVAL
                )
                # Simple protocol: client can send "pong" to keep alive
                # or subscribe to specific rooms later
                if data == "pong":
                    continue
            except asyncio.TimeoutError:
                # Send heartbeat ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
