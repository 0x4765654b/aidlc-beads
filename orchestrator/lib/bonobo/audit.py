"""Shared audit log for all Bonobo guards."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("bonobo.audit")

MAX_RING_BUFFER = 1000


@dataclass
class AuditEntry:
    """A single audit log entry."""

    timestamp: datetime
    guard: str  # "file", "git", "beads"
    operation: str  # "write_file", "commit", "create_issue", etc.
    agent: str  # Which agent requested the operation
    details: dict[str, Any] = field(default_factory=dict)
    result: str = "allowed"  # "allowed", "denied", "error"
    reason: str | None = None


class AuditLog:
    """Append-only audit trail for all privileged operations.

    Stores entries in an in-memory ring buffer. Optionally flushes
    to Agent Mail #ops thread when a mail client is provided.
    """

    def __init__(self, mail_client: Any | None = None, project_key: str = "") -> None:
        self._buffer: deque[AuditEntry] = deque(maxlen=MAX_RING_BUFFER)
        self._mail_client = mail_client
        self._project_key = project_key
        self._pending_flush: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        """Append an entry to the audit log."""
        self._buffer.append(entry)
        logger.info(
            "[%s] %s.%s by %s: %s%s",
            entry.result.upper(),
            entry.guard,
            entry.operation,
            entry.agent,
            entry.details,
            f" -- {entry.reason}" if entry.reason else "",
        )

        # Try to flush to Agent Mail
        if self._mail_client and self._project_key:
            try:
                self._mail_client.send_message(
                    self._project_key,
                    "Bonobo",
                    ["Bonobo"],
                    f"[{entry.result.upper()}] {entry.guard}.{entry.operation}",
                    (
                        f"**Agent**: {entry.agent}\n"
                        f"**Operation**: {entry.guard}.{entry.operation}\n"
                        f"**Result**: {entry.result}\n"
                        f"**Details**: {entry.details}\n"
                        + (f"**Reason**: {entry.reason}\n" if entry.reason else "")
                    ),
                    thread_id="#ops",
                )
                # Flush any pending entries too
                for pending in self._pending_flush:
                    self._mail_client.send_message(
                        self._project_key,
                        "Bonobo",
                        ["Bonobo"],
                        f"[{pending.result.upper()}] {pending.guard}.{pending.operation} (delayed)",
                        f"**Agent**: {pending.agent}\n**Details**: {pending.details}\n",
                        thread_id="#ops",
                    )
                self._pending_flush.clear()
            except Exception:
                # REL-03: Guard operations must not fail because of audit infra
                self._pending_flush.append(entry)
                logger.warning("Agent Mail unreachable, audit entry queued for later flush")

    def log_allowed(
        self, guard: str, operation: str, agent: str, details: dict | None = None
    ) -> None:
        """Convenience: log an allowed operation."""
        self.log(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                guard=guard,
                operation=operation,
                agent=agent,
                details=details or {},
                result="allowed",
            )
        )

    def log_denied(
        self, guard: str, operation: str, agent: str, reason: str, details: dict | None = None
    ) -> None:
        """Convenience: log a denied operation."""
        self.log(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                guard=guard,
                operation=operation,
                agent=agent,
                details=details or {},
                result="denied",
                reason=reason,
            )
        )

    def log_error(
        self, guard: str, operation: str, agent: str, reason: str, details: dict | None = None
    ) -> None:
        """Convenience: log an error."""
        self.log(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                guard=guard,
                operation=operation,
                agent=agent,
                details=details or {},
                result="error",
                reason=reason,
            )
        )

    def recent(self, limit: int = 50) -> list[AuditEntry]:
        """Get recent entries."""
        entries = list(self._buffer)
        return entries[-limit:]

    def filter_by_agent(self, agent: str) -> list[AuditEntry]:
        """Get entries for a specific agent."""
        return [e for e in self._buffer if e.agent == agent]

    def filter_by_result(self, result: str) -> list[AuditEntry]:
        """Get entries by result type."""
        return [e for e in self._buffer if e.result == result]
