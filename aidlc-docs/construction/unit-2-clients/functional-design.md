<!-- beads-issue: gt-23 -->
<!-- beads-review: gt-24 -->
# Functional Design -- Unit 2: Beads + Agent Mail Clients

## Overview

Unit 2 provides two Python client libraries that wrap external systems:

1. **Beads Client** (`orchestrator/lib/beads/client.py`): Wraps the `bd` CLI, turning shell commands into typed Python calls with structured return values.
2. **Agent Mail Client** (`orchestrator/lib/agent_mail/client.py`): HTTP client for the MCP Agent Mail server, providing messaging, file reservations, and agent directory operations.

Both clients have **zero LLM dependency** and use only Python stdlib + `httpx` (for Agent Mail HTTP calls).

---

## Module: `beads/client.py` -- Beads CLI Wrapper

### Data Models

```python
@dataclass
class BeadsIssue:
    id: str
    title: str
    status: str             # "open", "in_progress", "done", "closed"
    priority: int           # 0-4
    issue_type: str         # "task", "epic", "bug", "feature", "chore", "decision", "message"
    assignee: str | None
    labels: list[str]
    notes: str | None
    description: str | None
    created_at: str
    updated_at: str | None

@dataclass
class BeadsDependency:
    from_id: str
    to_id: str
    dep_type: str           # "blocks", "parent", "tracks", "related", etc.
```

### Functions

#### `create_issue(title, issue_type, priority, **kwargs) -> BeadsIssue`

Create a Beads issue. Maps to `bd create`.

**Parameters**:
- `title`: Issue title (required)
- `issue_type`: "task", "epic", "bug", "feature", "chore", "decision", "message"
- `priority`: 0-4
- `description`: Optional description text
- `labels`: Optional comma-separated labels string
- `assignee`: Optional assignee name
- `notes`: Optional notes
- `acceptance`: Optional acceptance criteria
- `thread`: Optional parent issue ID for threading

**Returns**: `BeadsIssue` parsed from `--json` output.

#### `show_issue(issue_id) -> BeadsIssue`

Get full details of a single issue. Maps to `bd show <id> --json`.

#### `update_issue(issue_id, **kwargs) -> None`

Update issue fields. Maps to `bd update`.

**Supported kwargs**: `status`, `notes`, `append_notes`, `assignee`, `priority`, `add_label`, `remove_label`, `claim` (bool).

#### `close_issue(issue_id, reason=None) -> None`

Close an issue. Maps to `bd close <id>`.

#### `reopen_issue(issue_id, reason=None) -> None`

Reopen a closed issue. Maps to `bd reopen <id>`.

#### `list_issues(**filters) -> list[BeadsIssue]`

List issues with filters. Maps to `bd list --json`.

**Supported filters**: `status`, `label`, `label_any`, `assignee`, `issue_type`, `parent`, `priority`, `title`, `notes_contains`, `sort`, `reverse`, `limit`.

#### `ready(**filters) -> list[BeadsIssue]`

Get ready (unblocked) work. Maps to `bd ready --json`.

**Supported filters**: `assignee`, `unassigned` (bool).

#### `blocked() -> list[BeadsIssue]`

Get blocked issues. Maps to `bd blocked --json`.

#### `add_dependency(blocked_id, blocker_id, dep_type="blocks") -> None`

Add a dependency. Maps to `bd dep add`.

#### `remove_dependency(issue_id, depends_on_id) -> None`

Remove a dependency. Maps to `bd dep remove`.

#### `sync(force=False, full=False, import_mode=False) -> None`

Sync database. Maps to `bd sync`.

#### `search(query) -> list[BeadsIssue]`

Search issues by text. Maps to `bd search`.

### Internal Helper

```python
def _run_bd(*args, json_output=False) -> str | dict | list:
    """Run a bd CLI command and return output.
    
    If json_output=True, appends --json and parses the result.
    Raises subprocess.CalledProcessError on non-zero exit.
    """
```

---

## Module: `agent_mail/client.py` -- Agent Mail HTTP Client

### Configuration

```python
@dataclass
class AgentMailConfig:
    base_url: str = "http://localhost:8765"
    bearer_token: str | None = None
    timeout: float = 30.0
```

Loaded from environment variables:
- `AGENT_MAIL_URL` (default: `http://localhost:8765`)
- `AGENT_MAIL_TOKEN` (bearer token)

### Data Models

```python
@dataclass
class MailMessage:
    id: str
    subject: str
    body: str
    from_agent: str
    to_agents: list[str]
    cc_agents: list[str]
    thread_id: str | None
    importance: str          # "normal", "high", "low"
    created_at: str
    acknowledged: bool

@dataclass
class FileReservation:
    id: str
    agent_name: str
    paths: list[str]
    exclusive: bool
    reason: str | None
    ttl_seconds: int
    created_at: str
    expires_at: str

@dataclass
class AgentInfo:
    name: str
    project_key: str
    model: str | None
    program: str | None
    registered_at: str
```

### Functions

All functions call the Agent Mail MCP HTTP API. The client uses `httpx` for HTTP calls.

#### `ensure_project(project_key, human_name=None) -> dict`

Ensure a project exists. Maps to MCP tool `ensure_project`.

#### `register_agent(project_key, agent_name, model=None, program=None) -> AgentInfo`

Register an agent identity. Maps to MCP tool `register_agent`.

#### `send_message(project_key, from_agent, to_agents, subject, body, thread_id=None, cc_agents=None, importance="normal", ack_required=False) -> MailMessage`

Send a message. Maps to MCP tool `send_message`.

#### `fetch_inbox(project_key, agent_name, limit=20, unread_only=False) -> list[MailMessage]`

Fetch inbox messages. Maps to MCP tool `fetch_inbox`.

#### `acknowledge_message(project_key, agent_name, message_id) -> None`

Acknowledge a message. Maps to MCP tool `acknowledge_message`.

#### `search_messages(project_key, query, scope="both", limit=20) -> list[MailMessage]`

Search messages. Maps to MCP tool `search_messages`.

#### `reserve_files(project_key, agent_name, paths, ttl_seconds=3600, exclusive=True, reason=None) -> FileReservation`

Create file reservations. Maps to MCP tool `file_reservation_paths`.

#### `release_files(project_key, agent_name, paths=None) -> None`

Release file reservations. Maps to MCP tool `release_file_reservations`.
If `paths` is None, releases all reservations for the agent.

#### `list_agents(project_key) -> list[AgentInfo]`

List registered agents. Maps to MCP tool or resource `resource://agents/{project}`.

### Internal Helper

```python
class AgentMailClient:
    """HTTP client for Agent Mail MCP server.
    
    Wraps httpx to call the MCP Streamable HTTP endpoint.
    All MCP tools are invoked via POST to the /mcp endpoint
    with JSON-RPC format.
    """
    
    def __init__(self, config: AgentMailConfig | None = None):
        ...
    
    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool via the HTTP API."""
        ...
```

---

## Error Handling

| Client | Error | Behavior |
|--------|-------|----------|
| Beads | bd not on PATH | Raise `RuntimeError` |
| Beads | bd command fails | Raise `subprocess.CalledProcessError` |
| Beads | JSON parse fails | Raise `ValueError` |
| Agent Mail | Server unreachable | Raise `ConnectionError` |
| Agent Mail | Auth failure (401/403) | Raise `PermissionError` |
| Agent Mail | Tool error response | Raise `RuntimeError` with error detail |
| Agent Mail | Timeout | Raise `TimeoutError` |

---

## Dependencies

- **Python stdlib**: `subprocess`, `json`, `dataclasses`, `os`
- **External**: `httpx` (Agent Mail HTTP calls only)
- **System**: `bd` CLI on PATH (Beads client), Agent Mail server running (Agent Mail client)
