<!-- beads-issue: gt-8 -->
<!-- beads-review: gt-13 -->
# Service Architecture -- Gorilla Troop

## Service Definitions

### 1. orchestrator (Python, Strands Agents)

**Purpose**: Hosts the entire agent fleet in a single Python process.

**Interface**:
- Internal REST API (FastAPI) at port 8000, consumed by dashboard
- WebSocket endpoint at `ws://orchestrator:8000/ws` for real-time dashboard updates
- No direct human access -- dashboard is the frontend

**Key Endpoints**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/projects` | GET | List all projects with status |
| `/api/projects` | POST | Create a new project |
| `/api/projects/{id}/status` | GET | Get detailed project status |
| `/api/projects/{id}/pause` | POST | Pause a project |
| `/api/projects/{id}/resume` | POST | Resume a project |
| `/api/chat` | POST | Send a message to Harmbe |
| `/api/review/{gate_id}/approve` | POST | Approve a review gate |
| `/api/review/{gate_id}/reject` | POST | Reject a review gate with feedback |
| `/api/questions/{id}/answer` | POST | Answer a Q&A question |
| `/api/notifications` | GET | Get pending notifications |
| `/ws` | WebSocket | Real-time event stream (stage changes, notifications, chat responses) |

**Internal Architecture**:

```
orchestrator process
├── FastAPI app (REST + WebSocket server)
├── AgentEngine (manages agent lifecycle)
│   ├── Harmbe (always running, event loop)
│   │   ├── message_router() -- routes human input to correct handler
│   │   ├── project_registry -- persistent project list
│   │   └── notification_manager -- queues and prioritizes notifications
│   ├── Groomer (background coroutine)
│   │   ├── inbox_monitor() -- watches Agent Mail inbox
│   │   └── stale_detector() -- periodic checks for stuck work
│   └── [On demand, spawned as Strands agent instances]
│       ├── ProjectMinder(project_id) -- one per active project
│       ├── CuriousGeorge() -- on error
│       ├── Gibbon() -- on rework
│       ├── Snake() -- at checkpoints
│       └── Troop() -- ad-hoc tasks
├── Library modules (no LLM overhead)
│   ├── scribe -- artifact CRUD
│   ├── bonobo -- write guards
│   ├── context -- dispatch protocol
│   ├── beads -- Beads CLI wrapper
│   └── agent_mail -- Agent Mail HTTP client
└── Config
    ├── agent_prompts/ -- system prompts as .md files
    └── settings.py -- Bedrock config, paths, defaults
```

**Dependencies**: Strands Agents SDK, boto3 (Bedrock), FastAPI, uvicorn, websockets, httpx (Agent Mail client), Beads CLI (bd)

### 2. dashboard (FastAPI + React)

**Purpose**: Harmbe Dashboard web application for human interaction.

**Interface**: HTTP at port 3001 (host-exposed)

**Backend** (FastAPI):
- Proxy to orchestrator REST API
- Serve React frontend static files
- WebSocket relay from orchestrator to browser

**Frontend** (React):
- **Chat Panel**: WebSocket-based real-time chat with Harmbe
- **Document Review Panel**: Markdown renderer with approve/reject controls
- **Project Status Panel**: AIDLC dependency graph visualization (Mermaid or D3)
- **Notification Center**: Badge-counted notification list
- **Multi-Project Sidebar**: Project list with color-coded status

**Dependencies**: FastAPI, React, react-markdown, WebSocket client, CSS framework (Tailwind or similar)

### 3. agent-mail (MCP Agent Mail)

**Purpose**: Asynchronous messaging between agents and humans.

**Interface**: HTTP API at port 8765

**Data**: SQLite database + Git-backed archive in `agent-mail-data` Docker volume

**Agent Identities**: Harmbe, ProjectMinder, Scout, Sage, Bard, Planner, Architect, Steward, Forge, Crucible, Bonobo, Groomer, Snake, CuriousGeorge, Gibbon (Troop workers register ephemerally)

**Thread Convention**: Thread IDs map to Beads issue IDs (e.g., `gt-0042.3`)

### 4. outline (Existing)

**Purpose**: WYSIWYG document review for non-technical users.

**Interface**: HTTP at port 3000 (host-exposed)

**Enhancements**:
- Review status metadata pushed via enhanced `sync-outline.py`
- Action buttons (Approve, Request Changes, Done Editing, Ask Harmbe) implemented as document content or via Outline plugin/API

### 5. outline-postgres (Existing)

**Purpose**: Outline database backend. PostgreSQL 16.

### 6. outline-redis (Existing)

**Purpose**: Outline session/cache store. Redis 7.

---

## Service Communication Map

```mermaid
sequenceDiagram
    participant Browser
    participant Dashboard
    participant Orchestrator
    participant AgentMail as Agent Mail
    participant Bedrock
    participant Outline
    participant Workspace

    Note over Browser,Workspace: Human Chat Flow
    Browser->>Dashboard: WebSocket message
    Dashboard->>Orchestrator: WebSocket relay
    Orchestrator->>Bedrock: LLM call (Harmbe)
    Bedrock-->>Orchestrator: Response
    Orchestrator-->>Dashboard: WebSocket event
    Dashboard-->>Browser: Render response

    Note over Browser,Workspace: Review Gate Flow
    Orchestrator->>AgentMail: "Review gate ready" message
    Orchestrator->>Dashboard: WebSocket notification
    Dashboard-->>Browser: Notification badge
    Browser->>Dashboard: POST /review/{id}/approve
    Dashboard->>Orchestrator: Forward approval
    Orchestrator->>AgentMail: "Gate approved" message
    Orchestrator->>Workspace: bd update --status done

    Note over Orchestrator,Workspace: Stage Execution
    Orchestrator->>AgentMail: DISPATCH message to Chimp
    Orchestrator->>Bedrock: LLM call (Chimp agent)
    Bedrock-->>Orchestrator: Generated content
    Orchestrator->>Workspace: Write artifact (via Bonobo)
    Orchestrator->>Workspace: bd update --status done
    Orchestrator->>Outline: sync-outline.py push
