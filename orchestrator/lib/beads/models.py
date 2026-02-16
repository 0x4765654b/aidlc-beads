"""Data models for the Beads CLI client."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BeadsIssue:
    """Parsed Beads issue from JSON output."""

    id: str
    title: str
    status: str = "open"
    priority: int = 2
    issue_type: str = "task"
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)
    notes: str | None = None
    description: str | None = None
    created_at: str = ""
    updated_at: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> BeadsIssue:
        """Create a BeadsIssue from bd JSON output."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            status=data.get("status", "open"),
            priority=data.get("priority", 2),
            issue_type=data.get("type", data.get("issue_type", "task")),
            assignee=data.get("assignee") or None,
            labels=data.get("labels", []),
            notes=data.get("notes") or None,
            description=data.get("description") or None,
            created_at=data.get("created_at", data.get("created", "")),
            updated_at=data.get("updated_at", data.get("updated")) or None,
        )


@dataclass
class BeadsDependency:
    """A dependency relationship between two Beads issues."""

    from_id: str
    to_id: str
    dep_type: str = "blocks"
