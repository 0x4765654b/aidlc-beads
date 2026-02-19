"""Log access routes — exposes the in-memory log ring buffer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from orchestrator.api.deps import get_log_buffer
from orchestrator.api.models import LogEntryResponse
from orchestrator.engine.log_buffer import LogBuffer

logger = logging.getLogger("api.logs")

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/", response_model=list[LogEntryResponse])
async def list_logs(
    project_key: str | None = None,
    level: str | None = None,
    limit: int = Query(default=100, ge=1, le=2000),
    since: str | None = None,
    log_buffer: LogBuffer = Depends(get_log_buffer),
) -> list[LogEntryResponse]:
    """Query recent orchestrator log entries from the in-memory ring buffer.

    Args:
        project_key: Filter to logs associated with this project.
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        limit: Maximum entries to return (default 100, max 2000).
        since: ISO-8601 timestamp — only return entries after this time.
    """
    since_dt: datetime | None = None
    if since:
        since_dt = datetime.fromisoformat(since)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)

    entries = log_buffer.query(
        project_key=project_key,
        level=level,
        since=since_dt,
        limit=limit,
    )

    return [
        LogEntryResponse(
            timestamp=e.timestamp,
            level=e.level,
            logger_name=e.logger_name,
            message=e.message,
            project_key=e.project_key,
        )
        for e in entries
    ]
