"""In-memory ring buffer for capturing orchestrator log records."""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

# Best-effort regex to extract a project_key from log messages.
# Matches patterns like [project:sci-calc] or project_key=sci-calc or project=sci-calc
_PROJECT_KEY_RE = re.compile(
    r"(?:\[project[_:]?|project_key=|project=)([a-zA-Z0-9_-]+)"
)

_LEVEL_PRIORITY = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def _extract_project_key(message: str) -> str | None:
    """Try to extract a project key from a log message."""
    m = _PROJECT_KEY_RE.search(message)
    return m.group(1) if m else None


@dataclass(slots=True)
class LogEntry:
    """A single captured log record."""

    timestamp: str
    level: str
    logger_name: str
    message: str
    project_key: str | None = None


class LogBuffer:
    """Thread-safe ring buffer that stores recent log entries."""

    def __init__(self, maxlen: int = 2000) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, entry: LogEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def query(
        self,
        *,
        project_key: str | None = None,
        level: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Return matching entries, newest first.

        Args:
            project_key: Filter to entries associated with this project.
            level: Minimum log level (e.g. "WARNING" returns WARNING+ERROR+CRITICAL).
            since: Only return entries after this timestamp.
            limit: Maximum number of entries to return.
        """
        min_priority = _LEVEL_PRIORITY.get((level or "").upper(), 0)
        since_iso = since.isoformat() if since else None

        results: list[LogEntry] = []
        with self._lock:
            for entry in reversed(self._entries):
                if project_key and entry.project_key != project_key:
                    continue
                if min_priority and _LEVEL_PRIORITY.get(entry.level, 0) < min_priority:
                    continue
                if since_iso and entry.timestamp < since_iso:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break

        return results


class BufferHandler(logging.Handler):
    """A logging.Handler that appends formatted records to a LogBuffer."""

    def __init__(self, buffer: LogBuffer, level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                level=record.levelname,
                logger_name=record.name,
                message=message,
                project_key=_extract_project_key(message),
            )
            self.buffer.append(entry)
        except Exception:
            self.handleError(record)
