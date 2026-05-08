from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict
from typing import Callable

from loguru import logger


class HealthServer:
    """Local HTTP health endpoint for bridge monitoring and graceful shutdown.

    Inspired by Multica's daemon health server:
    - /health returns runtime status, PID, uptime, active tasks
    - /shutdown triggers graceful shutdown via POST
    - Port-in-use detection prevents duplicate bridge instances
    """

    def __init__(
        self,
        health_port: int = 19514,
        get_status: Callable[[], dict] | None = None,
        on_shutdown: Callable[[], None] | None = None,
    ):
        self.health_port = health_port
        self.get_status = get_status or (lambda: {})
        self.on_shutdown = on_shutdown
        self._started_at = time.time()
        self._server: asyncio.Server | None = None

    async def start(self) -> bool:
        """Start the health server. Returns False if port is already in use."""
        try:
            self._server = await asyncio.start_server(
                self._handle_request,
                "127.0.0.1",
                self.health_port,
            )
            logger.info(f"Health server listening on http://127.0.0.1:{self.health_port}")
            return True
        except OSError as e:
            logger.error(f"Another bridge may already be running on port {self.health_port}: {e}")
            return False

    async def stop(self):
        """Stop the health server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Health server stopped")

    async def _handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single HTTP request."""
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not request_line:
                return

            # Parse request line
            parts = request_line.decode("utf-8").strip().split()
            if len(parts) < 2:
                return
            method, path = parts[0], parts[1]

            # Drain headers
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if line == b"\r\n" or line == b"\n" or not line:
                    break

            if path == "/health" and method == "GET":
                await self._send_json(writer, self._build_health_response())
            elif path == "/shutdown" and method == "POST":
                await self._send_json(writer, {"status": "shutting down"})
                if self.on_shutdown:
                    # Trigger shutdown asynchronously so response flushes first
                    asyncio.get_event_loop().call_later(0.5, self.on_shutdown)
            else:
                await self._send_error(writer, 404, "Not Found")
        except Exception as e:
            logger.debug(f"Health server request error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _build_health_response(self) -> dict:
        """Build the /health response payload."""
        status = self.get_status()
        return {
            "status": "running",
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - self._started_at, 1),
            "uptime": self._format_duration(time.time() - self._started_at),
            **status,
        }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            return f"{int(seconds // 60)}m{int(seconds % 60)}s"
        return f"{int(seconds // 3600)}h{int((seconds % 3600) // 60)}m"

    async def _send_json(self, writer: asyncio.StreamWriter, data: dict):
        """Send a JSON HTTP response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        writer.write(headers + body)
        await writer.drain()

    async def _send_error(self, writer: asyncio.StreamWriter, code: int, message: str):
        """Send an HTTP error response."""
        body = json.dumps({"error": message}).encode("utf-8")
        headers = (
            f"HTTP/1.1 {code} {message}\r\n".encode()
            + b"Content-Type: application/json\r\n"
            + b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            + b"Connection: close\r\n"
            + b"\r\n"
        )
        writer.write(headers + body)
        await writer.drain()
