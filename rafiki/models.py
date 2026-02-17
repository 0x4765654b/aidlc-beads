"""Pydantic models for Rafiki state, events, and reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Lifecycle States ──────────────────────────────────────────────────

class LifecycleState(str, Enum):
    INITIALIZING = "INITIALIZING"
    CREATING_PROJECT = "CREATING_PROJECT"
    MONITORING = "MONITORING"
    HANDLING_REVIEW = "HANDLING_REVIEW"
    HANDLING_QUESTION = "HANDLING_QUESTION"
    CHATTING = "CHATTING"
    STALLED = "STALLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VERIFYING = "VERIFYING"
    REPORTING = "REPORTING"
    CLEANING_UP = "CLEANING_UP"
    DONE = "DONE"


# ── Events ────────────────────────────────────────────────────────────

class EventType(str, Enum):
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    REVIEW_DECISION = "review_decision"
    QUESTION_ANSWERED = "question_answered"
    CHAT_INTERACTION = "chat_interaction"
    STALL_DETECTED = "stall_detected"
    VERIFICATION_CHECK = "verification_check"
    CLEANUP_STEP = "cleanup_step"
    ISSUE_FILED = "issue_filed"
    RUN_COMPLETE = "run_complete"


class RafikiEvent(BaseModel):
    """A single event emitted during a Rafiki run."""

    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    state: str = ""
    event: EventType
    detail: str = ""
    extra: dict[str, Any] = {}


# ── API Response Mirrors ──────────────────────────────────────────────

class ProjectInfo(BaseModel):
    project_key: str
    name: str
    workspace_path: str
    status: str
    created_at: str = ""


class ReviewGate(BaseModel):
    issue_id: str
    title: str
    stage_name: str = ""
    artifact_path: str | None = None
    artifact_content: str | None = None
    status: str = "open"
    notes: str | None = None


class Question(BaseModel):
    issue_id: str
    title: str
    description: str = ""
    options: list[str] = []
    stage_name: str | None = None


class ChatMessage(BaseModel):
    message_id: str = ""
    role: str = ""
    content: str = ""
    project_key: str | None = None
    timestamp: str = ""


class Notification(BaseModel):
    id: str
    type: str
    title: str
    body: str
    project_key: str = ""
    priority: int = 2
    read: bool = False


# ── Decision Records ─────────────────────────────────────────────────

class ReviewDecisionRecord(BaseModel):
    issue_id: str
    decision: str  # "approved" or "rejected"
    feedback: str = ""
    strategy: str = ""  # "rules", "llm", "auto_approve"
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class QuestionAnswerRecord(BaseModel):
    issue_id: str
    answer: str
    rationale: str = ""
    strategy: str = ""  # "context_match", "llm", "fallback"
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatRecord(BaseModel):
    prompt: str
    response: str = ""
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FiledIssue(BaseModel):
    issue_id: str
    title: str
    type: str = "bug"
    priority: int = 1
    source: str = ""
    filed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Verification ─────────────────────────────────────────────────────

class VerificationResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""
    duration_ms: int = 0


class VerificationReport(BaseModel):
    overall: str = "PASS"  # "PASS" or "FAIL"
    checks: list[VerificationResult] = []


# ── State Transitions ────────────────────────────────────────────────

class StateTransition(BaseModel):
    state: str
    entered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: int = 0


# ── Run Report ───────────────────────────────────────────────────────

class RunReport(BaseModel):
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    project_key: str = ""
    outcome: str = "PASS"  # "PASS" or "FAIL"
    lifecycle_states: list[StateTransition] = []
    reviews_handled: list[ReviewDecisionRecord] = []
    questions_answered: list[QuestionAnswerRecord] = []
    chat_interactions: list[ChatRecord] = []
    stalls_detected: int = 0
    issues_filed: list[FiledIssue] = []
    issues_filed_count: int = 0
    verification: VerificationReport = Field(default_factory=VerificationReport)


# ── Persisted State ──────────────────────────────────────────────────

class RafikiState(BaseModel):
    """Persisted state for resume-after-crash."""

    run_id: str = ""
    current_state: str = LifecycleState.INITIALIZING
    project_key: str = ""
    reviews: list[ReviewDecisionRecord] = []
    questions: list[QuestionAnswerRecord] = []
    chats: list[ChatRecord] = []
    issues_filed: list[FiledIssue] = []
    stall_count: int = 0
    artifact_paths_seen: list[str] = []
    state_transitions: list[StateTransition] = []
    failed: bool = False
    started_at: str = ""
