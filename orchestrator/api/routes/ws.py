"""WebSocket route -- connects the WebSocket endpoint to the app."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orchestrator.api.websocket import ConnectionManager

router = APIRouter(tags=["websocket"])


# We store a reference to the manager; it's set from app.state at request time.
# Since WebSocket endpoints don't support Depends() the same way, we access
# app.state directly.


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time event streaming.

    Query parameters:
        project_key: Filter events by project ("all" = receive everything).
    """
    manager: ConnectionManager = websocket.app.state.ws_manager
    project_key = websocket.query_params.get("project_key", "all")

    await manager.connect(websocket, project_key)
    try:
        while True:
            # Keep connection alive; we only read to detect disconnects.
            _data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
