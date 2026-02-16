"""Notification management routes."""

from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.api.deps import get_notifications, get_ws_manager
from orchestrator.api.models import NotificationResponse, NotificationCountResponse
from orchestrator.engine.notification_manager import NotificationManager, Notification
from orchestrator.api.websocket import ConnectionManager

logger = logging.getLogger("api.notifications")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _notification_to_response(n: Notification) -> NotificationResponse:
    """Convert internal Notification to API response."""
    return NotificationResponse(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        project_key=n.project_key,
        priority=n.priority,
        created_at=n.created_at.isoformat(),
        read=n.read,
        source_issue=n.source_issue,
    )


@router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    project_key: str | None = None,
    limit: int = 20,
    notifications: NotificationManager = Depends(get_notifications),
) -> list[NotificationResponse]:
    """Get notifications, highest priority first.

    Args:
        project_key: Filter by project (omit for all).
        limit: Maximum notifications to return.
    """
    unread = notifications.get_unread(project_key=project_key, limit=limit)
    return [_notification_to_response(n) for n in unread]


@router.get("/count", response_model=NotificationCountResponse)
async def notification_count(
    project_key: str | None = None,
    notifications: NotificationManager = Depends(get_notifications),
) -> NotificationCountResponse:
    """Get unread notification count with breakdown by type."""
    unread = notifications.get_unread(project_key=project_key, limit=1000)
    count = len(unread)
    by_type = dict(Counter(n.type for n in unread))
    return NotificationCountResponse(count=count, by_type=by_type)


@router.post("/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: str,
    notifications: NotificationManager = Depends(get_notifications),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> None:
    """Mark a single notification as read."""
    # Check if notification exists
    notif = notifications._by_id.get(notification_id)
    if not notif:
        raise HTTPException(
            status_code=404, detail=f"Notification '{notification_id}' not found"
        )

    notifications.mark_read(notification_id)
    await ws.broadcast(
        "notification_read", notif.project_key, {"id": notification_id}
    )


@router.post("/read-all")
async def mark_all_read(
    project_key: str | None = None,
    notifications: NotificationManager = Depends(get_notifications),
) -> dict:
    """Mark all notifications as read."""
    count = notifications.mark_all_read(project_key=project_key)
    return {"marked": count}
