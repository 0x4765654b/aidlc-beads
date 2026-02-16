"""Notification Manager -- priority-ordered notification queue."""

from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Notification:
    """A notification for a human user."""

    id: str
    type: str  # "review_gate", "escalation", "status_update", "info", "qa"
    title: str
    body: str
    project_key: str
    priority: int = 2  # 0 (critical) - 4 (info)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False
    source_issue: str | None = None

    def __lt__(self, other: Notification) -> bool:
        """Sort by priority (lower = higher priority), then by creation time."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class NotificationManager:
    """Priority-ordered notification queue for human users.

    Uses a heap for efficient priority ordering.
    """

    def __init__(self) -> None:
        self._heap: list[Notification] = []
        self._by_id: dict[str, Notification] = {}

    def add(self, notification: Notification) -> None:
        """Add a notification to the queue."""
        if not notification.id:
            notification.id = f"notif-{uuid.uuid4().hex[:8]}"
        self._by_id[notification.id] = notification
        heapq.heappush(self._heap, notification)

    def create(
        self,
        type: str,
        title: str,
        body: str,
        project_key: str,
        priority: int = 2,
        source_issue: str | None = None,
    ) -> Notification:
        """Create and add a notification in one step.

        Returns:
            The created Notification.
        """
        notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:8]}",
            type=type,
            title=title,
            body=body,
            project_key=project_key,
            priority=priority,
            source_issue=source_issue,
        )
        self.add(notif)
        return notif

    def get_unread(
        self, project_key: str | None = None, limit: int = 20
    ) -> list[Notification]:
        """Get unread notifications, highest priority first.

        Args:
            project_key: Filter by project (None = all projects).
            limit: Maximum notifications to return.

        Returns:
            List of unread notifications sorted by priority.
        """
        unread = [
            n
            for n in sorted(self._by_id.values())
            if not n.read
            and (project_key is None or n.project_key == project_key)
        ]
        return unread[:limit]

    def mark_read(self, notification_id: str) -> None:
        """Mark a notification as read.

        Args:
            notification_id: The notification to mark.
        """
        notif = self._by_id.get(notification_id)
        if notif:
            notif.read = True

    def mark_all_read(self, project_key: str | None = None) -> int:
        """Mark all notifications as read.

        Args:
            project_key: Filter by project (None = all).

        Returns:
            Number of notifications marked.
        """
        count = 0
        for notif in self._by_id.values():
            if not notif.read and (project_key is None or notif.project_key == project_key):
                notif.read = True
                count += 1
        return count

    def clear_project(self, project_key: str) -> None:
        """Clear all notifications for a project."""
        to_remove = [
            nid for nid, n in self._by_id.items() if n.project_key == project_key
        ]
        for nid in to_remove:
            del self._by_id[nid]
        # Rebuild heap
        self._heap = [n for n in self._heap if n.project_key != project_key]
        heapq.heapify(self._heap)

    def count_unread(self, project_key: str | None = None) -> int:
        """Count unread notifications."""
        return sum(
            1
            for n in self._by_id.values()
            if not n.read
            and (project_key is None or n.project_key == project_key)
        )
