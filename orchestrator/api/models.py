"""Pydantic request/response models for the Orchestrator API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Projects ──────────────────────────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    key: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    workspace_path: str = Field(..., min_length=1)


class ProjectResponse(BaseModel):
    """Response for project operations."""

    project_key: str
    name: str
    workspace_path: str
    status: str
    minder_agent_id: str | None = None
    created_at: str = ""
    paused_at: str | None = None


class ProjectStatusResponse(BaseModel):
    """Detailed project status with Beads data."""

    project_key: str
    name: str
    status: str
    current_phase: str = "unknown"
    active_agents: int = 0
    pending_reviews: int = 0
    open_questions: int = 0
    ready_issues: list[dict] = []
    in_progress_issues: list[dict] = []


class AgentResponse(BaseModel):
    """Active agent information."""

    agent_id: str
    agent_type: str
    status: str
    current_task: str | None = None
    created_at: str = ""


# ── Chat ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=10000)
    project_key: str | None = None


class ChatResponse(BaseModel):
    """Response from Harmbe."""

    message_id: str
    response: str
    project_key: str | None = None
    actions_taken: list[str] = []
    timestamp: str = ""


class ChatMessage(BaseModel):
    """A single chat message (user or assistant)."""

    message_id: str
    role: str
    content: str
    project_key: str | None = None
    timestamp: str = ""


# ── Review ────────────────────────────────────────────────────────────────


class ReviewGateResponse(BaseModel):
    """Summary of a pending review gate."""

    issue_id: str
    title: str
    project_key: str = ""
    stage_name: str = ""
    artifact_path: str | None = None
    created_at: str = ""
    status: str = "open"


class ReviewDetailResponse(BaseModel):
    """Full review gate detail with artifact content."""

    issue_id: str
    title: str
    project_key: str = ""
    stage_name: str = ""
    artifact_path: str | None = None
    artifact_content: str | None = None
    status: str = "open"
    notes: str | None = None


class ReviewDecision(BaseModel):
    """Human review decision body."""

    feedback: str = ""
    edited_content: str | None = None


class ReviewResultResponse(BaseModel):
    """Result of a review decision."""

    issue_id: str
    decision: str
    next_action: str = ""
    message: str = ""


# ── Notifications ─────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    """A notification for the UI."""

    id: str
    type: str
    title: str
    body: str
    project_key: str
    priority: int = 2
    created_at: str = ""
    read: bool = False
    source_issue: str | None = None


class NotificationCountResponse(BaseModel):
    """Unread notification count."""

    count: int = 0
    by_type: dict[str, int] = {}


# ── Questions ─────────────────────────────────────────────────────────────


class QuestionResponse(BaseModel):
    """Summary of a pending Q&A question."""

    issue_id: str
    title: str
    project_key: str = ""
    description: str = ""
    stage_name: str | None = None
    created_at: str = ""
    status: str = "open"


class QuestionDetailResponse(BaseModel):
    """Full question detail with context."""

    issue_id: str
    title: str
    project_key: str = ""
    description: str = ""
    options: list[str] = []
    stage_name: str | None = None
    blocking_issue: str | None = None
    created_at: str = ""


class AnswerRequest(BaseModel):
    """Answer to a Q&A question."""

    answer: str = Field(..., min_length=1, max_length=5000)


class AnswerResultResponse(BaseModel):
    """Result of answering a question."""

    issue_id: str
    answer: str
    unblocked_stages: list[str] = []
    message: str = ""


# ── System ────────────────────────────────────────────────────────────────


class SystemInfoResponse(BaseModel):
    """System information response."""

    version: str = "0.1.0"
    active_projects: int = 0
    active_agents: int = 0
    pending_notifications: int = 0
    engine_status: str = "running"
