"""Progress monitor — tracks pipeline state, detects stalls, dispatches events."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from rafiki.client.notifications import NotificationClient
from rafiki.client.reviews import ReviewClient
from rafiki.client.questions import QuestionClient
from rafiki.client.logs import LogsClient
from rafiki.client.websocket import WebSocketListener
from rafiki.issues import IssueFiler
from rafiki.models import RafikiEvent, EventType

logger = logging.getLogger("rafiki.monitor")


class PipelineEvent:
    """A normalized event from either WebSocket push or REST polling."""

    def __init__(self, type: str, data: dict[str, Any]):
        self.type = type
        self.data = data

    def __repr__(self) -> str:
        return f"PipelineEvent({self.type}, {self.data.get('issue_id', '')})"


class Monitor:
    """Monitors the pipeline via WebSocket + REST polling and detects stalls."""

    def __init__(
        self,
        *,
        project_key: str,
        review_client: ReviewClient,
        question_client: QuestionClient,
        notification_client: NotificationClient,
        ws_listener: WebSocketListener | None,
        issue_filer: IssueFiler,
        poll_interval: float = 5.0,
        stall_threshold: float = 300.0,
        logs_client: LogsClient | None = None,
    ):
        self.project_key = project_key
        self.review_client = review_client
        self.question_client = question_client
        self.notification_client = notification_client
        self.ws_listener = ws_listener
        self.issue_filer = issue_filer
        self.poll_interval = poll_interval
        self.stall_threshold = stall_threshold
        self.logs_client = logs_client

        self._last_event_time: float = time.monotonic()
        self._handled_reviews: set[str] = set()
        self._handled_questions: set[str] = set()
        self._last_notification_count: int = 0
        self.stall_count: int = 0
        self.total_events_received: int = 0
        self._events_at_last_stall: int = 0

    def record_activity(self) -> None:
        """Mark that meaningful activity occurred (resets stall timer)."""
        self._last_event_time = time.monotonic()

    @property
    def seconds_since_activity(self) -> float:
        return time.monotonic() - self._last_event_time

    @property
    def is_stalled(self) -> bool:
        return self.seconds_since_activity >= self.stall_threshold

    @property
    def stall_minutes(self) -> float:
        return self.seconds_since_activity / 60.0

    async def poll(self) -> list[PipelineEvent]:
        """Check for new events via WebSocket drain + REST polling."""
        events: list[PipelineEvent] = []

        # Drain WebSocket events
        if self.ws_listener and self.ws_listener.connected:
            ws_events = await self.ws_listener.drain()
            for ws_event in ws_events:
                event = self._normalize_ws_event(ws_event)
                if event:
                    events.append(event)

        # Poll REST endpoints for new review gates
        try:
            reviews = await self.review_client.list(self.project_key)
            for review in reviews:
                rid = review.get("issue_id", "")
                status = review.get("status", "")
                if rid and rid not in self._handled_reviews and status == "open":
                    events.append(PipelineEvent("review_gate", review))
        except Exception as exc:
            logger.warning("Failed to poll reviews: %s", exc)

        # Poll for new questions
        try:
            questions = await self.question_client.list(self.project_key)
            for q in questions:
                qid = q.get("issue_id", "")
                status = q.get("status", "")
                if qid and qid not in self._handled_questions and status == "open":
                    events.append(PipelineEvent("question", q))
        except Exception as exc:
            logger.warning("Failed to poll questions: %s", exc)

        # Check notifications for stage transitions
        try:
            notifs = await self.notification_client.list(self.project_key, unread_only=True)
            for notif in notifs:
                ntype = notif.get("type", "")
                if ntype in ("stage_started", "stage_completed", "error"):
                    events.append(PipelineEvent(ntype, notif))
        except Exception as exc:
            logger.warning("Failed to poll notifications: %s", exc)

        if events:
            self.total_events_received += len(events)
            self.record_activity()

        return events

    def mark_review_handled(self, issue_id: str) -> None:
        self._handled_reviews.add(issue_id)

    def mark_question_handled(self, issue_id: str) -> None:
        self._handled_questions.add(issue_id)

    async def _fetch_recent_logs(self) -> str:
        """Fetch recent WARNING+ logs from the orchestrator."""
        if not self.logs_client:
            return ""
        try:
            entries = await self.logs_client.list(level="WARNING", limit=20)
            if not entries:
                return ""
            lines = []
            for e in entries:
                ts = e.get("timestamp", "")
                lvl = e.get("level", "")
                msg = e.get("message", "")
                lines.append(f"[{ts}] {lvl}: {msg}")
            return (
                "\n\n## Recent Orchestrator Logs\n\n```\n"
                + "\n".join(lines)
                + "\n```"
            )
        except Exception as exc:
            logger.debug("Could not fetch orchestrator logs: %s", exc)
            return ""

    async def handle_stall(self) -> str:
        """File a Beads bug for the stall. Returns the issue ID."""
        self.stall_count += 1
        self._events_at_last_stall = self.total_events_received
        minutes = self.stall_minutes
        log_section = await self._fetch_recent_logs()
        issue_id = await self.issue_filer.file_bug(
            f"Pipeline stalled for {minutes:.0f} minutes",
            f"No progress detected for {minutes:.1f} minutes.\n\n"
            f"Handled reviews: {len(self._handled_reviews)}\n"
            f"Handled questions: {len(self._handled_questions)}\n"
            f"Stall count: {self.stall_count}"
            + log_section,
            priority=0,
            source="monitoring",
        )
        self.record_activity()
        return issue_id

    def should_fast_fail(self, active_agents: int) -> str | None:
        """Check if the pipeline is clearly dead and should fast-fail.

        Returns a reason string if fast-fail is warranted, None otherwise.
        """
        # No agents assigned and no events ever seen — nothing will happen
        if active_agents == 0 and self.total_events_received == 0:
            return (
                f"No active agents for project and no pipeline events received. "
                f"The orchestrator has no work assigned for this project."
            )

        # Consecutive stalls with zero new events between them — stuck
        if self.stall_count >= 2 and self.total_events_received == self._events_at_last_stall:
            return (
                f"Consecutive stalls ({self.stall_count}) with no new events between them. "
                f"Total events ever received: {self.total_events_received}."
            )

        return None

    def _normalize_ws_event(self, raw: dict) -> PipelineEvent | None:
        """Convert a raw WebSocket message to a PipelineEvent."""
        event_type = raw.get("type", raw.get("event", ""))
        if not event_type:
            return None
        return PipelineEvent(event_type, raw)
