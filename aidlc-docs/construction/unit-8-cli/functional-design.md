<!-- beads-issue: gt-77 -->
<!-- beads-review: gt-78 -->
# Unit 8: GT CLI -- Functional Design

## Overview

The `gt` CLI is a thin command-line wrapper that sends HTTP requests to the Orchestrator API (Unit 6) and prints formatted output. It provides quick access to common operations without opening the dashboard.

**Technology**: Python, Click library.

**Installation**: `pip install -e .` from the `cli/` directory, or run directly: `python cli/gt.py`.

---

## Command Surface

```
gt [--api-url URL] COMMAND [OPTIONS]
```

**Global option**: `--api-url` (default: `http://localhost:8000`) -- Orchestrator API base URL.

---

### `gt status`

Show the status of the active project or a specific project.

```
gt status [PROJECT_KEY]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `PROJECT_KEY` | No | Project to query. If omitted, shows summary of all projects. |

**Without project key** -- Lists all projects with status:
```
Projects:
  ● gorilla-troop    Active     3 agents   1 pending review
  ○ my-app           Paused     0 agents   0 pending reviews
```

**With project key** -- Shows detailed status:
```
Project: gorilla-troop (Gorilla Troop)
Status: active
Phase: construction
Active Agents: 3
Pending Reviews: 1
Open Questions: 0
```

**API calls**: `GET /api/projects/` or `GET /api/projects/{key}/status`

---

### `gt projects`

Manage projects.

```
gt projects list [--status STATUS]
gt projects create KEY NAME WORKSPACE_PATH
gt projects pause KEY
gt projects resume KEY
gt projects delete KEY [--confirm]
```

| Subcommand | Description | API Call |
|------------|-------------|----------|
| `list` | List all projects | `GET /api/projects/?status=...` |
| `create` | Create a new project | `POST /api/projects/` |
| `pause` | Pause a project | `POST /api/projects/{key}/pause` |
| `resume` | Resume a project | `POST /api/projects/{key}/resume` |
| `delete` | Delete (requires `--confirm`) | `DELETE /api/projects/{key}` |

**Output** for `list`:
```
KEY              NAME              STATUS    CREATED
gorilla-troop    Gorilla Troop     active    2026-02-15
my-app           My App            paused    2026-02-14
```

---

### `gt approve`

Approve a review gate.

```
gt approve ISSUE_ID [--feedback TEXT]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_ID` | Yes | Beads issue ID (e.g., `gt-12`) |
| `--feedback` | No | Optional feedback text |

**API call**: `POST /api/review/{issue_id}/approve`

**Output**:
```
✓ Review gt-12 approved. Next stage dispatched.
```

---

### `gt reject`

Reject a review gate (request changes).

```
gt reject ISSUE_ID --feedback TEXT
```

| Argument | Required | Description |
|----------|----------|-------------|
| `ISSUE_ID` | Yes | Beads issue ID |
| `--feedback` | Yes | Feedback text (required) |

**API call**: `POST /api/review/{issue_id}/reject`

**Output**:
```
✕ Review gt-12 rejected. Rework dispatched.
  Feedback: "Section 3 needs more detail on error handling"
```

---

### `gt reviews`

List pending review gates.

```
gt reviews [--project PROJECT_KEY]
```

**API call**: `GET /api/review/?project_key=...`

**Output**:
```
Pending Reviews:
  gt-12  Requirements Analysis         gorilla-troop
  gt-14  Application Design            gorilla-troop
```

---

### `gt questions`

List and answer pending questions.

```
gt questions [--project PROJECT_KEY]
gt questions answer ISSUE_ID ANSWER_TEXT
```

| Subcommand | Description | API Call |
|------------|-------------|----------|
| (default) | List pending questions | `GET /api/questions/` |
| `answer` | Answer a question | `POST /api/questions/{id}/answer` |

**Output** for list:
```
Pending Questions:
  gt-25  Authentication Method    gorilla-troop
  gt-31  Database Strategy        my-app
```

---

### `gt notifications`

View and manage notifications.

```
gt notifications [--project PROJECT_KEY] [--limit N]
gt notifications read ID
gt notifications read-all [--project PROJECT_KEY]
```

| Subcommand | Description | API Call |
|------------|-------------|----------|
| (default) | List unread notifications | `GET /api/notifications/` |
| `read` | Mark one as read | `POST /api/notifications/{id}/read` |
| `read-all` | Mark all as read | `POST /api/notifications/read-all` |

---

### `gt chat`

Send a one-shot message to Harmbe.

```
gt chat "message text" [--project PROJECT_KEY]
```

**API call**: `POST /api/chat/`

**Output**:
```
Harmbe: Acknowledged: "message text". Harmbe agent integration is pending.
```

---

### `gt info`

Show system information.

```
gt info
```

**API call**: `GET /api/info`

**Output**:
```
Gorilla Troop v0.1.0
Active Projects: 2
Active Agents: 3
Pending Notifications: 5
Engine: running
```

---

## Error Handling

- If the API is unreachable, print: `Error: Cannot connect to Orchestrator API at {url}` and exit with code 1.
- HTTP errors are printed as: `Error: {detail}` with the appropriate exit code.
- All output goes to stdout; errors go to stderr.

---

## File Manifest

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `cli/__init__.py` | Package init | ~1 |
| `cli/gt.py` | Click CLI with all commands | ~300 |
| **Total** | | **~301** |
