"""WebSocket listener for real-time events."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("rafiki.client.ws")

class WebSocketListener:
    """Connects to the Gorilla Troop WebSocket and feeds events into an asyncio Queue."""
    
    def __init__(self):
        self.event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._ws: Any = None  # websockets connection
        self._task: asyncio.Task | None = None
        self._running = False

    async def connect(self, ws_url: str) -> None:
        """Open a WebSocket connection and start listening."""
        try:
            import websockets
        except ImportError:
            logger.warning("websockets package not installed; WebSocket listener disabled")
            return

        try:
            self._ws = await websockets.connect(ws_url)
            self._running = True
            self._task = asyncio.create_task(self._listen())
            logger.info("WebSocket connected to %s", ws_url)
        except Exception as exc:
            logger.warning("WebSocket connection failed: %s", exc)
            self._ws = None

    async def _listen(self) -> None:
        """Read messages from the WebSocket and enqueue them."""
        try:
            async for message in self._ws:
                try:
                    event = json.loads(message) if isinstance(message, str) else message
                    await self.event_queue.put(event)
                except json.JSONDecodeError:
                    logger.warning("Ignoring non-JSON WebSocket message: %s", message[:100])
        except Exception as exc:
            if self._running:
                logger.warning("WebSocket listener error: %s", exc)
        finally:
            self._running = False

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._running

    async def close(self) -> None:
        """Disconnect and stop listening."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def drain(self, max_events: int = 100) -> list[dict[str, Any]]:
        """Drain up to max_events from the queue without blocking."""
        events = []
        for _ in range(max_events):
            try:
                event = self.event_queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break
        return events
