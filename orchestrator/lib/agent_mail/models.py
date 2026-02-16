"""Data models for the Agent Mail HTTP client."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentMailConfig:
    """Configuration for connecting to the Agent Mail server."""

    base_url: str = "http://localhost:8765"
    bearer_token: str | None = None
    timeout: float = 30.0


@dataclass
class MailMessage:
    """A message in the Agent Mail system."""

    id: str
    subject: str
    body: str
    from_agent: str
    to_agents: list[str] = field(default_factory=list)
    cc_agents: list[str] = field(default_factory=list)
    thread_id: str | None = None
    importance: str = "normal"
    created_at: str = ""
    acknowledged: bool = False

    @classmethod
    def from_json(cls, data: dict) -> MailMessage:
        """Create a MailMessage from API JSON response."""
        return cls(
            id=data.get("id", data.get("message_id", "")),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            from_agent=data.get("from_agent", data.get("sender", "")),
            to_agents=data.get("to_agents", data.get("recipients", [])),
            cc_agents=data.get("cc_agents", data.get("cc", [])),
            thread_id=data.get("thread_id"),
            importance=data.get("importance", "normal"),
            created_at=data.get("created_at", data.get("created", "")),
            acknowledged=data.get("acknowledged", False),
        )


@dataclass
class FileReservation:
    """An advisory file reservation (lease)."""

    id: str
    agent_name: str
    paths: list[str] = field(default_factory=list)
    exclusive: bool = True
    reason: str | None = None
    ttl_seconds: int = 3600
    created_at: str = ""
    expires_at: str = ""

    @classmethod
    def from_json(cls, data: dict) -> FileReservation:
        """Create a FileReservation from API JSON response."""
        return cls(
            id=data.get("id", data.get("reservation_id", "")),
            agent_name=data.get("agent_name", data.get("agent", "")),
            paths=data.get("paths", data.get("patterns", [])),
            exclusive=data.get("exclusive", True),
            reason=data.get("reason"),
            ttl_seconds=data.get("ttl_seconds", 3600),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
        )


@dataclass
class AgentInfo:
    """A registered agent in the Agent Mail directory."""

    name: str
    project_key: str = ""
    model: str | None = None
    program: str | None = None
    registered_at: str = ""

    @classmethod
    def from_json(cls, data: dict) -> AgentInfo:
        """Create an AgentInfo from API JSON response."""
        return cls(
            name=data.get("name", data.get("agent_name", "")),
            project_key=data.get("project_key", data.get("project", "")),
            model=data.get("model"),
            program=data.get("program"),
            registered_at=data.get("registered_at", data.get("created", "")),
        )
