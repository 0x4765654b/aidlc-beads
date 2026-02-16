"""WebSocket event stream -- real-time push to connected dashboard clients."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("api.websocket")


class ConnectionManager:
    """Manages WebSocket connections and event broadcasting.

    Clients connect with an optional project_key filter.
    "all" (or omitted) receives events from all projects.
    """

    def __init__(self) -> None:
        # Maps websocket -> subscribed project_key ("all" = everything)
        self._connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, project_key: str = "all") -> None:
        """Accept a new WebSocket connection and register it.

        Args:
            websocket: The incoming WebSocket connection.
            project_key: Project filter ("all" receives everything).
        """
        await websocket.accept()
        self._connections[websocket] = project_key
        logger.info(
            "WebSocket connected (project=%s, total=%d)",
            project_key,
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self._connections.pop(websocket, None)
        logger.info(
            "WebSocket disconnected (total=%d)", len(self._connections)
        )

    @property
    def active_connections(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)

    async def broadcast(
        self, event: str, project_key: str, data: dict
    ) -> None:
        """Send an event to all connected clients that match the project filter.

        Args:
            event: Event type name (e.g., "stage_completed").
            project_key: Project this event belongs to.
            data: Event payload dict.
        """
        message = json.dumps(
            {
                "event": event,
                "project_key": project_key,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        dead_connections: list[WebSocket] = []

        for ws, subscribed_key in self._connections.items():
            # Send to clients subscribed to this project or to "all"
            if subscribed_key == "all" or subscribed_key == project_key:
                try:
                    await ws.send_text(message)
                except Exception:
                    logger.warning("Failed to send to WebSocket, marking for cleanup")
                    dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self._connections.pop(ws, None)

    async def send_personal(
        self, websocket: WebSocket, event: str, data: dict
    ) -> None:
        """Send an event to a specific client.

        Args:
            websocket: Target WebSocket connection.
            event: Event type name.
            data: Event payload dict.
        """
        message = json.dumps(
            {
                "event": event,
                "project_key": "",
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        await websocket.send_text(message)


async def websocket_endpoint(websocket: WebSocket, manager: ConnectionManager) -> None:
    """WebSocket endpoint handler.

    Connects the client, keeps the connection alive, and handles disconnects.
    The project_key is extracted from the query parameter.

    Args:
        websocket: The incoming WebSocket.
        manager: The ConnectionManager instance.
    """
    project_key = websocket.query_params.get("project_key", "all")
    await manager.connect(websocket, project_key)
    try:
        while True:
            # Keep connection alive; clients don't send data, but we must
            # read to detect disconnects.
            _data = await websocket.receive_text()
            # Client messages are ignored (ping/keepalive only)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
