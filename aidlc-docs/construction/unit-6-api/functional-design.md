<!-- beads-issue: gt-57 -->
<!-- beads-review: gt-58 -->
# Unit 6: Orchestrator API -- Functional Design

## Overview

The Orchestrator API is a **FastAPI** application that serves as the HTTP/WebSocket backend for the Harmbe Dashboard and CLI. It bridges human interfaces (browser, command-line) to the agent engine, project registry, and notification system.

All state mutations flow through the appropriate engine components (ProjectRegistry, NotificationManager, AgentEngine). The API layer itself is stateless -- it delegates to those components and translates between HTTP/JSON and internal Python objects.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Harmbe Dashboard                      │
│              (React / Next.js -- Unit 7)                 │
└──────────┬──────────────────────────────┬───────────────┘
           │ REST (JSON)                  │ WebSocket
           ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Application                    │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐  │
│  │ projects │ │   chat   │ │  review   │ │ questions │  │
│  │  routes  │ │  routes  │ │  routes   │ │  routes   │  │
│  └────┬─────┘ └────┬─────┘ └────┬──────┘ └────┬──────┘  │
│       │             │            │              │         │
│  ┌────┴─────┐  ┌────┴────┐ ┌────┴──────┐               │
│  │ notific. │  │websocket│ │   health  │               │
│  │  routes  │  │ manager │ │  routes   │               │
│  └────┬─────┘  └────┬────┘ └───────────┘               │
└───────┼─────────────┼───────────────────────────────────┘
        │             │
        ▼             ▼
┌──────────────────────────────────────────────────────────┐
│              Engine Layer (Unit 4 + Unit 5)               │
│  ProjectRegistry │ AgentEngine │ NotificationManager     │
└──────────────────────────────────────────────────────────┘
```

---

## Module Specifications

### 1. `api/app.py` -- Application Factory

**Purpose**: Create and configure the FastAPI application instance, wire up all routers, middleware, and shared dependencies.

**Function**: `create_app`

```python
def create_app(
    project_registry: ProjectRegistry | None = None,
    agent_engine: AgentEngine | None = None,
    notification_manager: NotificationManager | None = None,
) -> FastAPI:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_registry` | `ProjectRegistry \| None` | `None` | Injected project registry (creates default if None) |
| `agent_engine` | `AgentEngine \| None` | `None` | Injected agent engine (creates default if None) |
| `notification_manager` | `NotificationManager \| None` | `None` | Injected notification manager (creates default if None) |

**Returns**: Configured `FastAPI` instance.

**Behavior**:
1. Create default instances for any `None` dependency.
2. Store dependencies in `app.state` for access by route handlers.
3. Include all route routers with appropriate prefixes.
4. Add CORS middleware (configurable origins, defaults to `localhost:3000`).
5. Add a lifespan handler that shuts down the AgentEngine on app shutdown.
6. Configure logging.

**Dependency injection pattern**:
```python
# Route handlers access shared state via:
def get_registry(request: Request) -> ProjectRegistry:
    return request.app.state.registry

def get_engine(request: Request) -> AgentEngine:
    return request.app.state.engine

def get_notifications(request: Request) -> NotificationManager:
    return request.app.state.notifications
```

---

### 2. `api/routes/projects.py` -- Project Management

**Prefix**: `/api/projects`

#### Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| `POST` | `/` | Create a new project | `CreateProjectRequest` | `ProjectResponse` (201) |
| `GET` | `/` | List all projects | Query: `?status=active` | `list[ProjectResponse]` |
| `GET` | `/{project_key}` | Get project details | -- | `ProjectResponse` |
| `POST` | `/{project_key}/pause` | Pause a project | -- | `ProjectResponse` |
| `POST` | `/{project_key}/resume` | Resume a project | -- | `ProjectResponse` |
| `DELETE` | `/{project_key}` | Delete a project | -- | 204 No Content |
| `GET` | `/{project_key}/status` | Get detailed project status | -- | `ProjectStatusResponse` |
| `GET` | `/{project_key}/agents` | List active agents for project | -- | `list[AgentResponse]` |

#### Data Models

```python
class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""
    key: str                    # Unique project key (e.g., "my-app")
    name: str                   # Human-readable name
    workspace_path: str         # Absolute path to project workspace

class ProjectResponse(BaseModel):
    """Response for project operations."""
    project_key: str
    name: str
    workspace_path: str
    status: str                 # "active", "paused", "completed"
    minder_agent_id: str | None
    created_at: str
    paused_at: str | None

class ProjectStatusResponse(BaseModel):
    """Detailed project status with Beads data."""
    project_key: str
    name: str
    status: str
    current_phase: str          # "inception", "construction", "operations"
    active_agents: int
    pending_reviews: int
    open_questions: int
    ready_issues: list[dict]    # From bd ready --json
    in_progress_issues: list[dict]

class AgentResponse(BaseModel):
    """Response for active agent info."""
    agent_id: str
    agent_type: str
    status: str
    current_task: str | None
    created_at: str
```

#### Behavior Notes

- `POST /` creates the project in `ProjectRegistry` and broadcasts a `project_created` event via WebSocket.
- `GET /{project_key}/status` runs `bd ready --json` and `bd list --status in_progress --json` against the project workspace to provide real-time Beads state.
- `GET /{project_key}/agents` queries `AgentEngine.list_active()` filtered by `project_key`.
- `POST /{project_key}/pause` calls `ProjectRegistry.pause_project()` and stops active agents for that project.
- `DELETE /{project_key}` returns 404 if not found, broadcasts `project_deleted` event.

**Error responses**: All endpoints return `{"detail": "..."}` with appropriate HTTP status codes (400, 404, 409, 500).

---

### 3. `api/routes/chat.py` -- Chat Message Handler

**Prefix**: `/api/chat`

#### Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| `POST` | `/` | Send a chat message to Harmbe | `ChatRequest` | `ChatResponse` |
| `GET` | `/history` | Get chat history | Query: `?project_key=...&limit=50` | `list[ChatMessage]` |

#### Data Models

```python
class ChatRequest(BaseModel):
    """Request body for sending a chat message."""
    message: str                # User's message text
    project_key: str | None = None  # Optional project context

class ChatResponse(BaseModel):
    """Response from Harmbe."""
    message_id: str
    response: str               # Harmbe's text response
    project_key: str | None
    actions_taken: list[str]    # e.g., ["dispatched_stage", "created_project"]
    timestamp: str

class ChatMessage(BaseModel):
    """A single chat message (user or assistant)."""
    message_id: str
    role: str                   # "user" or "assistant"
    content: str
    project_key: str | None
    timestamp: str
```

#### Behavior

1. The chat endpoint receives the user's message and optional project context.
2. It dispatches to the Harmbe agent via the AgentEngine (or directly if Harmbe runs in-process).
3. Harmbe interprets the message, potentially:
   - Querying Beads for status
   - Routing approvals to Project Minder
   - Creating projects
   - Answering questions from context
4. The response is returned synchronously.
5. Side effects (stage dispatches, notifications) are emitted as WebSocket events.
6. Chat history is stored in-memory with a configurable max length (default 1000 messages per project, plus a global channel).

---

### 4. `api/routes/review.py` -- Review Gate Operations

**Prefix**: `/api/review`

#### Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| `GET` | `/` | List pending review gates | Query: `?project_key=...` | `list[ReviewGateResponse]` |
| `GET` | `/{issue_id}` | Get review gate details with artifact | -- | `ReviewDetailResponse` |
| `POST` | `/{issue_id}/approve` | Approve a review gate | `ReviewDecision` | `ReviewResultResponse` |
| `POST` | `/{issue_id}/reject` | Reject a review gate (request changes) | `ReviewDecision` | `ReviewResultResponse` |

#### Data Models

```python
class ReviewGateResponse(BaseModel):
    """Summary of a pending review gate."""
    issue_id: str
    title: str
    project_key: str
    stage_name: str
    artifact_path: str | None
    created_at: str
    status: str

class ReviewDetailResponse(BaseModel):
    """Full review gate detail with artifact content."""
    issue_id: str
    title: str
    project_key: str
    stage_name: str
    artifact_path: str | None
    artifact_content: str | None  # Markdown content of the artifact
    status: str
    notes: str | None

class ReviewDecision(BaseModel):
    """Human review decision body."""
    feedback: str = ""          # Optional feedback text
    edited_content: str | None = None  # If the human edited the artifact inline

class ReviewResultResponse(BaseModel):
    """Result of a review decision."""
    issue_id: str
    decision: str               # "approved" or "rejected"
    next_action: str            # "dispatched_next_stage" or "dispatched_rework"
    message: str
```

#### Behavior

- `GET /` queries Beads: `bd list --label "type:review-gate" --status open --json` filtered by project.
- `GET /{issue_id}` loads the artifact content from the file referenced in the issue notes (`artifact: <path>`).
- `POST /{issue_id}/approve`:
  1. Updates Beads issue to `done`.
  2. If `edited_content` is provided, writes it back to the artifact file.
  3. Notifies Project Minder via Agent Mail.
  4. Broadcasts `review_approved` WebSocket event.
- `POST /{issue_id}/reject`:
  1. Adds feedback as a comment to the Beads issue.
  2. Dispatches Gibbon (rework agent) with the feedback.
  3. Broadcasts `review_rejected` WebSocket event.

---

### 5. `api/routes/notifications.py` -- Notification Management

**Prefix**: `/api/notifications`

#### Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| `GET` | `/` | Get notifications | Query: `?project_key=...&limit=20` | `list[NotificationResponse]` |
| `GET` | `/count` | Get unread count | Query: `?project_key=...` | `NotificationCountResponse` |
| `POST` | `/{notification_id}/read` | Mark notification as read | -- | 204 No Content |
| `POST` | `/read-all` | Mark all as read | Query: `?project_key=...` | `{"marked": N}` |

#### Data Models

```python
class NotificationResponse(BaseModel):
    """A notification for the UI."""
    id: str
    type: str                   # "review_gate", "escalation", "status_update", "info", "qa"
    title: str
    body: str
    project_key: str
    priority: int
    created_at: str
    read: bool
    source_issue: str | None

class NotificationCountResponse(BaseModel):
    """Unread notification count."""
    count: int
    by_type: dict[str, int]     # e.g., {"review_gate": 2, "escalation": 1}
```

#### Behavior

- Delegates directly to `NotificationManager`.
- `GET /count` includes a breakdown by notification type for badge display.
- Marking a notification as read broadcasts a `notification_read` WebSocket event for real-time UI sync.

---

### 6. `api/routes/questions.py` -- Q&A Answer Handler

**Prefix**: `/api/questions`

#### Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| `GET` | `/` | List pending questions | Query: `?project_key=...` | `list[QuestionResponse]` |
| `GET` | `/{issue_id}` | Get question details | -- | `QuestionDetailResponse` |
| `POST` | `/{issue_id}/answer` | Answer a question | `AnswerRequest` | `AnswerResultResponse` |

#### Data Models

```python
class QuestionResponse(BaseModel):
    """Summary of a pending Q&A question."""
    issue_id: str
    title: str
    project_key: str
    description: str            # Full question with options
    stage_name: str | None
    created_at: str
    status: str

class QuestionDetailResponse(BaseModel):
    """Full question detail with context."""
    issue_id: str
    title: str
    project_key: str
    description: str
    options: list[str]          # Parsed options (A, B, C, X)
    stage_name: str | None
    blocking_issue: str | None  # Which stage this question blocks
    created_at: str

class AnswerRequest(BaseModel):
    """Answer to a Q&A question."""
    answer: str                 # The selected option or free-text answer

class AnswerResultResponse(BaseModel):
    """Result of answering a question."""
    issue_id: str
    answer: str
    unblocked_stages: list[str] # Stages that are now unblocked
    message: str
```

#### Behavior

- `GET /` queries Beads: `bd list --label "type:qa" --status open --json` filtered by project.
- `GET /{issue_id}` parses the description to extract options (lines matching `^[A-Z]\)` pattern).
- `POST /{issue_id}/answer`:
  1. Adds the answer as a comment on the Beads issue.
  2. Closes the Q&A issue in Beads.
  3. Checks if any blocked stages are now unblocked (`bd ready --json`).
  4. Broadcasts `question_answered` WebSocket event.

---

### 7. `api/websocket.py` -- WebSocket Event Stream

**Purpose**: Real-time event push to connected dashboard clients.

#### Connection

```
ws://localhost:8000/ws?project_key=all
ws://localhost:8000/ws?project_key=my-project
```

Clients connect with an optional `project_key` filter. `all` (or omitted) receives events from all projects.

#### Event Protocol

All messages are JSON:

```json
{
    "event": "stage_completed",
    "project_key": "gorilla-troop",
    "data": { ... },
    "timestamp": "2026-02-15T12:00:00Z"
}
```

#### Event Types

| Event | Emitted When | Data Payload |
|-------|-------------|-------------|
| `project_created` | New project registered | `{project_key, name}` |
| `project_deleted` | Project removed | `{project_key}` |
| `project_paused` | Project paused | `{project_key}` |
| `project_resumed` | Project resumed | `{project_key}` |
| `stage_started` | Agent begins a stage | `{project_key, stage_name, agent_type, issue_id}` |
| `stage_completed` | Agent finishes a stage | `{project_key, stage_name, status, summary}` |
| `review_ready` | Review gate requires attention | `{project_key, issue_id, title, artifact_path}` |
| `review_approved` | Human approved a review | `{project_key, issue_id}` |
| `review_rejected` | Human rejected a review | `{project_key, issue_id, feedback}` |
| `question_asked` | Agent asked a question | `{project_key, issue_id, title}` |
| `question_answered` | Human answered a question | `{project_key, issue_id, answer}` |
| `notification_new` | New notification created | `{id, type, title, priority}` |
| `notification_read` | Notification marked read | `{id}` |
| `agent_spawned` | New agent instance started | `{project_key, agent_id, agent_type}` |
| `agent_stopped` | Agent instance completed/stopped | `{project_key, agent_id, status}` |
| `error_escalation` | Error escalated to human | `{project_key, agent_type, error, issue_id}` |

#### WebSocket Manager Class

```python
class ConnectionManager:
    """Manages WebSocket connections and event broadcasting."""

    async def connect(self, websocket: WebSocket, project_key: str = "all") -> None:
        """Accept a new WebSocket connection and register it."""

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""

    async def broadcast(
        self, event: str, project_key: str, data: dict
    ) -> None:
        """Send an event to all connected clients that match the project filter."""

    async def send_personal(
        self, websocket: WebSocket, event: str, data: dict
    ) -> None:
        """Send an event to a specific client."""
```

**Behavior**:
- Connections are tracked in a dict mapping `WebSocket -> project_key`.
- `broadcast()` sends to clients subscribed to the event's project or to `"all"`.
- Dead connections are cleaned up automatically on send failure.
- The `ConnectionManager` is stored in `app.state.ws_manager` and injected into route handlers that need to emit events.

---

### 8. `api/routes/health.py` -- Health and Info

**Prefix**: `/api`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/health` | Liveness check | `{"status": "ok"}` |
| `GET` | `/info` | System info | `SystemInfoResponse` |

```python
class SystemInfoResponse(BaseModel):
    """System information response."""
    version: str                # "0.1.0"
    active_projects: int
    active_agents: int
    pending_notifications: int
    engine_status: str          # "running", "shutting_down"
```

---

## Error Handling Strategy

All route handlers follow a consistent error response pattern:

| HTTP Status | Usage |
|-------------|-------|
| 200 | Successful GET/POST |
| 201 | Successful resource creation |
| 204 | Successful delete or side-effect-only action |
| 400 | Invalid request body or query parameters |
| 404 | Resource not found (project, issue, notification) |
| 409 | Conflict (duplicate project key) |
| 500 | Unexpected server error |

Error response body:
```json
{
    "detail": "Human-readable error message"
}
```

All exceptions from engine components (`KeyError`, `ValueError`, `RuntimeError`) are caught in route handlers and translated to appropriate HTTP responses.

---

## Dependency Summary

| Component | Source | Used By |
|-----------|--------|---------|
| `ProjectRegistry` | `orchestrator.engine` | projects, chat, review |
| `AgentEngine` | `orchestrator.engine` | projects, chat |
| `NotificationManager` | `orchestrator.engine` | notifications, websocket |
| `ConnectionManager` | `api/websocket.py` | all routes (event broadcasting) |
| Beads CLI | `orchestrator.lib.beads` | projects (status), review, questions |
| Agent Mail | `orchestrator.lib.agent_mail` | chat (Harmbe delegation) |
| Scribe | `orchestrator.lib.scribe` | review (artifact loading) |

---

## File Manifest

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `api/__init__.py` | Package init, exports `create_app` | ~10 |
| `api/app.py` | Application factory, middleware, lifespan | ~80 |
| `api/deps.py` | FastAPI dependency injection functions | ~30 |
| `api/websocket.py` | ConnectionManager + WebSocket endpoint | ~80 |
| `api/routes/__init__.py` | Package init | ~5 |
| `api/routes/projects.py` | Project CRUD + status routes | ~130 |
| `api/routes/chat.py` | Chat message handler | ~80 |
| `api/routes/review.py` | Review gate operations | ~120 |
| `api/routes/notifications.py` | Notification management | ~70 |
| `api/routes/questions.py` | Q&A answer handler | ~100 |
| `api/routes/health.py` | Health check + system info | ~30 |
| **Total** | | **~735** |
