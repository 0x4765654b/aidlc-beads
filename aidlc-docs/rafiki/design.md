<!-- beads-issue: gt-106 -->
<!-- beads-review: gt-107 -->
# Rafiki: Human Simulation Agent — Design Document

## 1. Purpose

Rafiki is an **external acceptance-test agent** that plays the human role in the Gorilla Troop AIDLC pipeline. It creates a project, monitors every stage, approves review gates, answers Q&A questions, chats with Harmbe, and verifies the finished output — all through the same user-facing interfaces a real human would use.

The test project is the **Scientific Calculator API** (`rafiki-project/`), chosen because it is small enough to complete in a single run yet rich enough to exercise every AIDLC stage: requirements, design, code generation, build & test, and operations.

### Goals

1. **Golden-path validation** — prove the end-to-end pipeline works without human intervention.
2. **Regression guard** — run Rafiki after any system change to catch breakages.
3. **Interface coverage** — exercise the REST API, WebSocket events, and notification flow that real users depend on.
4. **Decision audit** — produce a structured run report showing every decision Rafiki made and why.

---

## 2. Architecture

### 2.1 Location

Rafiki lives as a **standalone top-level package** at `rafiki/` in the repository root — not under `orchestrator/agents/`. Rationale:

- Rafiki is an *external client* of Gorilla Troop, not an internal agent. It should not import orchestrator internals or depend on the agent base classes.
- It communicates exclusively via the public HTTP API (`http://localhost:9741`), exactly as a human using the Dashboard or CLI would.
- This separation also lets Rafiki run from a different host or container in the future.

```
rafiki/
├── __init__.py
├── __main__.py              # CLI entry point (python -m rafiki)
├── config.py                # RafikiConfig dataclass (env + YAML)
├── client/
│   ├── __init__.py
│   ├── base.py              # BaseClient (httpx session, retry, auth)
│   ├── projects.py          # ProjectClient
│   ├── reviews.py           # ReviewClient
│   ├── questions.py         # QuestionClient
│   ├── chat.py              # ChatClient
│   ├── notifications.py     # NotificationClient
│   └── health.py            # HealthClient
├── handlers/
│   ├── __init__.py
│   ├── review_handler.py    # Artifact evaluation + approve/reject
│   ├── question_handler.py  # Q&A answer selection
│   └── chat_handler.py      # Harmbe conversation driver
├── issues.py                # Beads issue filing (bd CLI wrapper)
├── cleanup.py               # Post-run cleanup (project, files, issues)
├── monitor.py               # Progress tracking + stall detection
├── lifecycle.py             # Main orchestration loop
├── verifier.py              # Post-completion verification suite
├── report.py                # Structured run report generator
└── models.py                # Pydantic models for Rafiki state
```

### 2.2 Interaction Mode

**Primary: REST API via httpx** — All interactions use the public API at `/api/projects/`, `/api/review/`, `/api/questions/`, `/api/chat/`, `/api/notifications/`. This gives Rafiki the exact same view a human gets through the Dashboard.

**Secondary: WebSocket for real-time events** — Rafiki connects to `ws://localhost:9741/ws` and listens for `review_approved`, `question_answered`, `chat_message`, and `project_created` events. This allows Rafiki to react to events immediately instead of relying solely on polling.

**Fallback: Polling** — If the WebSocket connection drops, Rafiki falls back to polling the REST endpoints at a configurable interval (default: 5 seconds). The monitor automatically switches between WebSocket push and poll-based modes.

### 2.3 Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                        Rafiki                            │
│                                                          │
│  ┌──────────────┐   ┌───────────────────────────┐        │
│  │   Lifecycle   │──▶│   Monitor (poll / WS)     │        │
│  │  Controller   │   └───────────┬───────────────┘        │
│  └──────┬───────┘               │                        │
│         │              ┌────────┴────────┐               │
│         │              ▼                 ▼               │
│  ┌──────┴──────┐  ┌──────────┐   ┌───────────┐          │
│  │   Verifier  │  │  Review  │   │  Question  │          │
│  │             │  │  Handler │   │  Handler   │          │
│  └──────┬──────┘  └────┬─────┘   └─────┬─────┘          │
│         │              │               │                 │
│         │         ┌────┴─────┐         │                 │
│         │         │   Chat   │         │                 │
│         │         │  Handler │         │                 │
│         │         └────┬─────┘         │                 │
│         │              │               │                 │
│         ▼              ▼               ▼                 │
│  ┌─────────────────────────────────────────────────┐     │
│  │            Issue Filer (bd CLI)                  │     │
│  │  Files Beads bugs/tasks for discovered problems │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────┴──────────────────────────┐     │
│  │              Report Generator                   │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────┴──────────────────────────┐     │
│  │         API Client Library (httpx + WS)         │     │
│  └──────────────────────┬──────────────────────────┘     │
└─────────────────────────┼────────────────────────────────┘
                          │ HTTP / WS / bd CLI
                          ▼
          ┌──────────────────────────────┐
          │   Gorilla Troop API + Beads  │
          │   localhost:9741  / bd CLI   │
          └──────────────────────────────┘
```

---

## 3. Decision Engine

Rafiki needs to make two kinds of decisions: **review approvals** and **question answers**. The design uses a layered strategy with an LLM-powered primary and deterministic fallbacks.

### 3.1 Review Handler Strategy: Hybrid (Rule + LLM)

**Layer 1 — Structural checks (rule-based, always run):**
- Artifact content is non-empty
- Artifact is at least 200 characters (not a stub)
- Contains expected markdown headings for the stage type (e.g., "## Requirements" for requirements docs, "## API" for functional design)
- No obvious placeholder text (`TODO`, `TBD`, `FIXME` in headings)

If structural checks fail → **reject** with specific feedback listing the failures.

**Layer 2 — Semantic quality (LLM-based, run if Layer 1 passes):**
- Send the artifact content + the project's `vision.md` and `tech-env.md` to Bedrock via the Rafiki chat endpoint or a direct Bedrock invocation.
- Prompt asks the LLM to evaluate: completeness, consistency with the vision, technical accuracy, and whether the artifact is ready for the next stage.
- LLM returns a structured verdict: `APPROVE`, `REJECT`, or `NEEDS_DISCUSSION` with a rationale.

If LLM says REJECT → **reject** with LLM's feedback.
If LLM says APPROVE → **approve** with LLM's summary as feedback.
If LLM says NEEDS_DISCUSSION or is unavailable → **approve** (to avoid blocking the pipeline) and log a warning.

**Layer 3 — Auto-approve mode (configurable):**
- When `--auto-approve` is set, skip both layers and approve immediately with "Auto-approved by Rafiki" feedback.
- Useful for throughput testing and CI/CD.

### 3.2 Question Handler Strategy: Context-Aware Selection

**Step 1 — Parse options** from the question description (A, B, C, ... X=Other format).

**Step 2 — Context matching:**
- Load `vision.md` and `tech-env.md` from the project workspace.
- For each option, score relevance against the project context:
  - Direct keyword matches (e.g., "FastAPI" in tech-env.md → prefer option mentioning FastAPI)
  - Technology alignment (Python 3.13, uv, pytest, ruff preferences)
  - Scope alignment (stateless API, no CAS, no UI preferences from vision.md)

**Step 3 — LLM tiebreaker (if scores are close or no clear winner):**
- Send the question, options, and project context to Bedrock.
- LLM selects the best option with rationale.

**Step 4 — Fallback:** If no LLM available, select the first non-"Other" option.

**Never select "Other"** unless all other options are clearly wrong — Rafiki should avoid generating free-text answers that could derail the pipeline.

### 3.3 Chat Handler Strategy

Rafiki uses chat interactions strategically, not continuously:

1. **After project creation** — "What is the current status of the sci-calc project?"
2. **After each phase completes** — "What phase are we in now? What's next?"
3. **When stall detected** — "I haven't seen progress in N minutes. What's happening with [stage]?"
4. **On completion** — "Is the sci-calc project fully complete? What's the final status?"

Each chat response is logged in the run report for later analysis of Harmbe's contextual awareness.

---

## 4. Lifecycle Model

Rafiki uses an **async event loop with a state machine** that drives the project through its full lifecycle.

### 4.1 States

```
INITIALIZING → CREATING_PROJECT → MONITORING → COMPLETED → VERIFYING → REPORTING → CLEANING_UP → DONE
                                      │                                                │
                                      ├──▶ HANDLING_REVIEW (re-enters MONITORING)       │
                                      ├──▶ HANDLING_QUESTION (re-enters MONITORING)     │
                                      ├──▶ CHATTING (re-enters MONITORING)              │
                                      └──▶ STALLED (re-enters MONITORING or → FAILED)   │
                                                                              │          │
                                                                              └──▶ CLEANING_UP → DONE
```

**CLEANING_UP** runs on every exit path -- both after successful completion and after critical failures. It is the *only* path to DONE.

### 4.2 Main Loop

```python
async def run(self):
    try:
        self.state = "INITIALIZING"
        await self.check_api_health()

        self.state = "CREATING_PROJECT"
        await self.create_project()

        self.state = "MONITORING"
        while not self.is_complete():
            events = await self.poll_or_receive()

            for event in events:
                if event.type == "review_gate":
                    self.state = "HANDLING_REVIEW"
                    await self.handle_review(event)
                    self.state = "MONITORING"

                elif event.type == "question":
                    self.state = "HANDLING_QUESTION"
                    await self.handle_question(event)
                    self.state = "MONITORING"

                elif event.type == "chat_trigger":
                    self.state = "CHATTING"
                    await self.handle_chat(event)
                    self.state = "MONITORING"

            if self.is_stalled():
                self.state = "STALLED"
                await self.handle_stall()
                if self.stall_count > MAX_STALLS:
                    self.state = "FAILED"
                    break
                self.state = "MONITORING"

            await asyncio.sleep(self.poll_interval)

        self.state = "COMPLETED" if not self.failed else "FAILED"

        self.state = "VERIFYING"
        results = await self.verify()

        self.state = "REPORTING"
        await self.generate_report(results)

    except Exception as e:
        self.state = "FAILED"
        self.issue_filer.file_bug(
            f"Rafiki: Unhandled exception: {type(e).__name__}",
            str(e), priority=0, source="lifecycle",
        )

    finally:
        # Cleanup ALWAYS runs -- success, failure, timeout, or crash
        self.state = "CLEANING_UP"
        await self.cleanup()
        self.state = "DONE"
```

### 4.3 Completion Detection

Rafiki considers the project **complete** when:
- The API reports the project status as complete, OR
- All review gates and Q&A questions from the project have been handled AND no new events have appeared for `completion_timeout` seconds (default: 120s), OR
- Rafiki has exceeded `max_runtime` (default: 2 hours).

### 4.4 State Persistence

Rafiki persists its state to a JSON file (`rafiki-state.json`) in the workspace:
- Current lifecycle state
- All decisions made (reviews, questions, chats)
- Timestamps for each state transition
- Stall count and recovery actions

On `--resume`, Rafiki reloads this state and continues from where it left off.

### 4.5 Cleanup

Cleanup runs in `finally` on **every exit path** — successful completion, critical failure, timeout, or unhandled exception. The simulated project must not be left behind polluting the system.

**Cleanup steps (in order):**

1. **Close WebSocket** — Disconnect the real-time event listener gracefully.

2. **Delete the simulated project** — Call `DELETE /api/projects/{project_key}` to remove the project from the ProjectRegistry. This removes the entry from `.gorilla-troop/projects.json`.

3. **Remove generated files** — Delete the project workspace directory that was created during the run (e.g., the generated `sci-calc/` source tree). Uses `shutil.rmtree` with error handling. Only deletes if the directory is inside the expected workspace root (safety guard against deleting unrelated files).

4. **Remove generated AIDLC artifacts** — Delete the `aidlc-docs/` artifacts that were produced for the simulated project during the run. Rafiki tracks which artifact paths it saw during review handling and removes them.

5. **Close Beads simulation issues** — Close any Beads issues that were created *by the AIDLC pipeline* for the simulated project (stage issues, review gates, Q&A questions) with a note: "Closed by Rafiki cleanup — simulation complete." Issues filed *by Rafiki itself* (bugs, tasks in `discovered-by:rafiki`) are **not closed** — those are real findings that need follow-up.

6. **Persist final state** — Write the final `rafiki-state.json` and `rafiki-report.json` before exiting.

7. **Close httpx client** — Release the connection pool.

**What cleanup preserves (not deleted):**
- Beads issues filed by Rafiki (`discovered-by:rafiki` label) — these are real bugs/tasks to fix.
- The run report (`rafiki-report.json`) — the record of what happened.
- The state file (`rafiki-state.json`) — for debugging and auditing.
- Log output.

**Cleanup safety guards:**
- If the API is unreachable during cleanup (e.g., the stack crashed), Rafiki logs the failure but does not error out — cleanup is best-effort.
- File deletion is guarded by path prefix checks: only deletes under the configured workspace root.
- If `--skip-cleanup` is passed (useful for debugging), cleanup is skipped entirely and a warning is logged.

**Cleanup configuration:**

```python
@dataclass
class RafikiConfig:
    ...
    # Cleanup
    skip_cleanup: bool = False           # Skip cleanup (for debugging)
    cleanup_timeout: float = 60.0        # Max seconds for cleanup phase
    preserve_artifacts: bool = False     # Keep AIDLC artifacts (for inspection)
```

---

## 5. Configuration

Rafiki uses a layered configuration: CLI flags > environment variables > config file > defaults.

### 5.1 Configuration Dataclass

```python
@dataclass
class RafikiConfig:
    # Connection
    api_url: str = "http://localhost:9741"
    ws_url: str = "ws://localhost:9741/ws"

    # Project
    project_key: str = "sci-calc"
    project_name: str = "Scientific Calculator API"
    project_workspace: str = ""  # resolved from rafiki-project/ at runtime

    # Decision engine
    auto_approve: bool = False
    llm_enabled: bool = True
    bedrock_model_id: str = "us.anthropic.claude-opus-4-6-v1"
    aws_profile: str = "ai3_d"

    # Timing
    poll_interval: float = 5.0        # seconds between polls
    stall_threshold: float = 300.0    # seconds before declaring a stall
    max_stalls: int = 5               # max stalls before failing
    max_runtime: float = 7200.0       # max total runtime (2 hours)
    completion_timeout: float = 120.0 # seconds of quiet before declaring done

    # Cleanup
    skip_cleanup: bool = False           # Skip cleanup (for debugging)
    cleanup_timeout: float = 60.0        # Max seconds for cleanup phase
    preserve_artifacts: bool = False     # Keep AIDLC artifacts (for inspection)

    # Paths
    state_file: str = "rafiki-state.json"
    report_file: str = "rafiki-report.json"
    log_file: str | None = None       # None = stdout only

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"          # "json" or "text"
```

### 5.2 CLI Interface

```bash
# Basic run
python -m rafiki

# With options
python -m rafiki \
    --api-url http://localhost:9741 \
    --project-key sci-calc \
    --poll-interval 3 \
    --auto-approve \
    --verbose

# Resume from saved state
python -m rafiki --resume

# Skip cleanup (for debugging -- leaves project and artifacts in place)
python -m rafiki --skip-cleanup

# Keep artifacts but delete the project (for post-mortem inspection)
python -m rafiki --preserve-artifacts

# Config file
python -m rafiki --config rafiki.yaml
```

### 5.3 Environment Variables

All config fields map to `RAFIKI_` prefixed env vars:
- `RAFIKI_API_URL`, `RAFIKI_PROJECT_KEY`, `RAFIKI_AUTO_APPROVE=true`, etc.

---

## 6. Operator Experience

When you run Rafiki, the console output is designed to give a clear, real-time picture of what is happening at every stage. In `text` log format (the default), the output uses a human-friendly rolling log. In `json` log format, the same events emit one structured JSON object per line for CI/CD piping.

### 6.1 Startup Banner

On launch, Rafiki prints a banner with connection status and run configuration:

```
═══════════════════════════════════════════════════════════════
  Rafiki — Human Simulation Agent  v0.1.0
  Run ID:    rafiki-2026-02-17T09-15-00
  API:       http://localhost:9741 ✓ healthy
  WebSocket: ws://localhost:9741/ws ✓ connected
  Project:   sci-calc (Scientific Calculator API)
  Mode:      hybrid (rules + LLM)
═══════════════════════════════════════════════════════════════
```

If the API or WebSocket health check fails, the banner shows the failure and Rafiki exits immediately.

### 6.2 Rolling Log Format

Every event follows the format `[timestamp] STATE description` with indented detail lines using tree-drawing characters (`├─`, `└─`):

```
[09:15:02] CREATING_PROJECT  Created project sci-calc at /workspace/sci-calc
[09:15:05] MONITORING        Waiting for first stage...
[09:15:18] MONITORING        Stage started: Workspace Detection (Scout)
[09:15:34] MONITORING        Stage completed: Workspace Detection
```

The `STATE` field matches the lifecycle state machine (Section 4.1) so the operator always knows where Rafiki is in its lifecycle.

### 6.3 Review Handling

When Rafiki handles a review gate, it shows the evaluation pipeline — structural checks, LLM evaluation, and final decision:

```
[09:15:35] HANDLING_REVIEW   Review gate: REVIEW: Workspace Detection
                             ├─ Artifact: aidlc-docs/inception/reverse-engineering/architecture.md
                             ├─ Structural checks: ✓ passed (3/3)
                             ├─ LLM evaluation: APPROVE — "Complete workspace analysis with..."
                             └─ Decision: APPROVED
```

On rejection, the output shows which checks failed and the filed Beads issue:

```
[09:22:10] HANDLING_REVIEW   Review gate: REVIEW: Functional Design
                             ├─ Artifact: aidlc-docs/construction/unit-1/functional-design.md
                             ├─ Structural checks: ✗ FAILED (1/3)
                             │  └─ Missing required heading: ## API Specification
                             ├─ Decision: REJECTED
                             └─ Filed: gt-122 (P1 bug) "Rafiki: Artifact missing ## API Specification"
```

### 6.4 Question Handling

Questions show the parsed options, the matching strategy, and the selected answer:

```
[09:16:01] HANDLING_QUESTION Q: "QUESTION: Requirements - Authentication Method"
                             ├─ Options: A) OAuth/SSO  B) None  C) API Keys  X) Other
                             ├─ Context match: vision.md says "no authentication"
                             └─ Answer: B) None
```

### 6.5 Chat Interactions

Chat exchanges show Rafiki's prompt and Harmbe's response (truncated to one line):

```
[09:28:30] CHATTING          Chat: "What phase are we in now?"
                             └─ Harmbe: "The sci-calc project is in Construction, completing Build..."
```

### 6.6 Stall Alerts

Stalls are highly visible with the filed issue and recovery action:

```
[09:35:00] STALLED           No progress for 300s at stage: Code Generation
                             ├─ Filed: gt-125 (P0 bug) "Rafiki: Pipeline stalled at Code Generation"
                             ├─ Chat: "No progress in 5 minutes. What's happening?"
                             └─ Harmbe: "Forge agent encountered a dependency resolution error..."
[09:35:15] MONITORING        Resuming monitoring (stall 1/5)...
```

### 6.7 Verification Checklist

Verification prints a numbered checklist with pass/fail marks. Failed checks show the filed Beads issue:

```
[09:40:01] VERIFYING         [1/8] AIDLC artifacts exist          ✓ 12/12 found
[09:40:01] VERIFYING         [2/8] No open Beads issues           ✓ 0 open
[09:40:02] VERIFYING         [3/8] Source code structure           ✓ src/sci_calc/, tests/, pyproject.toml
[09:40:05] VERIFYING         [4/8] Build succeeds (uv sync)       ✓ 0.8s
[09:40:09] VERIFYING         [5/8] Tests pass (uv run pytest)     ✗ 44 passed, 3 FAILED (3.2s)
                             ├─ FAILED: test_arithmetic.py::test_divide_by_zero
                             ├─ FAILED: test_arithmetic.py::test_modulo_negative
                             ├─ FAILED: test_conversions.py::test_stones_to_kg
                             └─ Filed: gt-126 (P0 bug) "Rafiki: pytest failed — 3 tests in 2 files"
[09:40:10] VERIFYING         [6/8] Linting (uv run ruff check)    ✗ 12 violations
                             └─ Filed: gt-127 (P2 task) "Rafiki: ruff found 12 lint violations"
[09:40:13] VERIFYING         [7/8] API starts (/health)           ✓ 200 OK
[09:40:14] VERIFYING         [8/8] Endpoint spot-checks           ✓ 3/3 correct
                             └─ add(2,3)=5 ✓  sqrt(16)=4.0 ✓  sin(0)=0.0 ✓
```

### 6.8 Cleanup Progress

Cleanup shows each step with a completion mark:

```
[09:40:20] CLEANING_UP       Deleting project sci-calc from registry...    ✓
                             Removing generated source: /workspace/sci-calc  ✓
                             Removing AIDLC artifacts: aidlc-docs/sci-calc/  ✓
                             Closing 23 pipeline Beads issues...             ✓
                             Preserving 2 Rafiki-filed issues (gt-126, gt-127)
```

### 6.9 Final Summary Banner

The run ends with a summary banner. The operator can see at a glance whether the run passed, what was filed, and where to look next:

```
═══════════════════════════════════════════════════════════════
  Rafiki Run Complete
───────────────────────────────────────────────────────────────
  Outcome:      PASS (with 2 issues filed)
  Duration:     25m 18s
  Stages:       14 completed, 0 failed
  Reviews:      11 approved, 0 rejected
  Questions:    4 answered
  Chats:        3 interactions
  Stalls:       0
  Issues filed: 2 (gt-126 P0 bug, gt-127 P2 task)
  Verification: 6/8 passed, 2 failed
───────────────────────────────────────────────────────────────
  Report: rafiki-report.json
  Beads issues to fix:
    gt-126  P0 bug   Rafiki: pytest failed — 3 tests in 2 files
    gt-127  P2 task  Rafiki: ruff found 12 lint violations
═══════════════════════════════════════════════════════════════
```

On a fully clean run with no issues, the summary is simpler:

```
═══════════════════════════════════════════════════════════════
  Rafiki Run Complete
───────────────────────────────────────────────────────────────
  Outcome:      PASS
  Duration:     22m 05s
  Stages:       14 completed, 0 failed
  Reviews:      11 approved, 0 rejected
  Questions:    4 answered
  Chats:        3 interactions
  Stalls:       0
  Issues filed: 0
  Verification: 8/8 passed
───────────────────────────────────────────────────────────────
  Report: rafiki-report.json
═══════════════════════════════════════════════════════════════
```

### 6.10 JSON Log Format

When `--log-format json` is set (or `RAFIKI_LOG_FORMAT=json`), every event emits a single JSON line instead of the formatted text above. Each line contains:

```json
{"ts":"2026-02-17T09:15:35Z","state":"HANDLING_REVIEW","event":"review_decision","issue_id":"gt-42","decision":"approved","strategy":"llm","detail":"Complete workspace analysis..."}
```

This format is designed for piping into log aggregators, CI/CD systems, or post-processing scripts. The `event` field is a machine-readable enum (`stage_started`, `stage_completed`, `review_decision`, `question_answered`, `chat_interaction`, `stall_detected`, `verification_check`, `cleanup_step`, `issue_filed`, `run_complete`).

---

## 7. API Client Library

The client library is a thin, typed wrapper around httpx. Each sub-client handles one API domain.

### 7.1 BaseClient

```python
class BaseClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    async def _get(self, path: str, **params) -> dict:
        resp = await self.client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict | None = None) -> dict:
        resp = await self.client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()
```

### 7.2 Sub-Clients

| Client | Endpoint Base | Key Methods |
|---|---|---|
| `HealthClient` | `/api/health` | `check()` |
| `ProjectClient` | `/api/projects/` | `create()`, `list()`, `get()`, `status()`, `pause()`, `resume()` |
| `ReviewClient` | `/api/review/` | `list()`, `get_detail()`, `approve()`, `reject()` |
| `QuestionClient` | `/api/questions/` | `list()`, `get_detail()`, `answer()` |
| `ChatClient` | `/api/chat/` | `send()`, `history()` |
| `NotificationClient` | `/api/notifications/` | `list()`, `count()`, `mark_read()`, `mark_all_read()` |

All methods return typed Pydantic models that mirror the API response schemas.

### 7.3 WebSocket Client

```python
class WebSocketListener:
    async def connect(self, ws_url: str):
        self.ws = await websockets.connect(ws_url)
        asyncio.create_task(self._listen())

    async def _listen(self):
        async for message in self.ws:
            event = json.loads(message)
            await self.event_queue.put(event)
```

The WebSocketListener feeds events into an `asyncio.Queue` consumed by the Lifecycle Controller.

---

## 8. Verification Suite

After the pipeline completes, the Verifier runs a sequence of checks:

| # | Check | How |
|---|---|---|
| 1 | AIDLC artifacts exist | Glob `aidlc-docs/` for expected stage files (requirements.md, functional-design.md, etc.) |
| 2 | No open Beads issues | Call `bd list --status open --json` via subprocess or API and confirm count is 0 for the project |
| 3 | Source code structure | Verify `src/sci_calc/`, `tests/`, `pyproject.toml` exist in the generated project |
| 4 | Build succeeds | Run `uv sync` in the generated project directory |
| 5 | Tests pass | Run `uv run pytest` and parse exit code |
| 6 | Linting passes | Run `uv run ruff check .` and parse exit code |
| 7 | API starts | Start `uv run uvicorn sci_calc.app:app --port 8765` and hit `/health` |
| 8 | Endpoint spot-checks | `POST /api/v1/arithmetic/add {"a": 2, "b": 3}` → result=5, etc. |

Each check produces a `VerificationResult(name, passed, detail, duration_ms)`.

When a verification check **fails**, the Verifier calls the Issue Filer (see Section 8) to create a Beads issue so the failure is tracked and can be fixed in a follow-up step.

---

## 9. Beads Issue Filing

Rafiki does not just log problems — it **files Beads issues** so every discovered problem is tracked, prioritized, and actionable in follow-up steps. The Issue Filer is a cross-cutting component used by the Review Handler, Question Handler, Monitor, Verifier, and Lifecycle Controller.

### 9.1 Issue Filer (`issues.py`)

The Issue Filer wraps the `bd` CLI to create issues in the project's Beads database. It runs `bd create` via subprocess (not the orchestrator API) because Beads is a host-side tool and Rafiki operates as an external client.

```python
class IssueFiler:
    """Files Beads issues for problems Rafiki discovers."""

    def __init__(self, workspace_root: Path, run_id: str):
        self.workspace_root = workspace_root
        self.run_id = run_id
        self.filed: list[FiledIssue] = []

    async def file_bug(
        self, title: str, description: str, priority: int = 1,
        labels: list[str] | None = None, source: str = "",
    ) -> str:
        """File a bug issue via bd create. Returns the issue ID."""
        all_labels = ["discovered-by:rafiki", f"rafiki-run:{self.run_id}"]
        if source:
            all_labels.append(f"discovered-from:{source}")
        if labels:
            all_labels.extend(labels)

        result = await run_bd([
            "create", title, "-t", "bug", "-p", str(priority),
            "--description", description,
            "--labels", ",".join(all_labels),
        ])
        issue_id = parse_issue_id(result)
        self.filed.append(FiledIssue(id=issue_id, title=title, ...))
        return issue_id

    async def file_task(
        self, title: str, description: str, priority: int = 2,
        labels: list[str] | None = None, source: str = "",
    ) -> str:
        """File a follow-up task via bd create. Returns the issue ID."""
        ...  # same pattern as file_bug with -t task
```

### 9.2 When Issues Are Filed

Rafiki files Beads issues at every point where it discovers a problem:

| Trigger | Issue Type | Priority | Source Label | Example |
|---|---|---|---|---|
| **Review rejection** | `bug` | P1 | `discovered-from:review-{stage}` | "Artifact missing required section: ## API Specification" |
| **Structural check failure** | `bug` | P1 | `discovered-from:review-{stage}` | "Artifact contains TODO placeholders in headings" |
| **Question answer ambiguity** | `task` | P2 | `discovered-from:qa` | "Question had no clear match for project context; defaulted to option A" |
| **Stall detected** | `bug` | P0 | `discovered-from:monitoring` | "Pipeline stalled for 5+ minutes at stage: Code Generation" |
| **API error (persistent)** | `bug` | P0 | `discovered-from:api-health` | "Orchestrator API returning 500 on /api/review/ after 3 retries" |
| **Verification: artifacts missing** | `bug` | P1 | `discovered-from:verification` | "Expected artifact not found: aidlc-docs/construction/unit-1/functional-design.md" |
| **Verification: build fails** | `bug` | P0 | `discovered-from:verification` | "uv sync failed: missing dependency 'httpx' in pyproject.toml" |
| **Verification: tests fail** | `bug` | P0 | `discovered-from:verification` | "pytest exited with code 1: 3 tests failed in test_arithmetic.py" |
| **Verification: lint fails** | `task` | P2 | `discovered-from:verification` | "ruff check found 12 violations in src/sci_calc/routes/" |
| **Verification: API won't start** | `bug` | P0 | `discovered-from:verification` | "uvicorn failed to start: ImportError in sci_calc.app" |
| **Verification: endpoint wrong result** | `bug` | P1 | `discovered-from:verification` | "POST /api/v1/arithmetic/add {a:2,b:3} returned 4, expected 5" |
| **Unexpected agent error** | `bug` | P1 | `discovered-from:notification` | "CuriousGeorge reported error in Forge agent during code generation" |
| **Global timeout** | `bug` | P0 | `discovered-from:timeout` | "Pipeline exceeded 2-hour max runtime; last active stage: Build and Test" |

### 9.3 Issue Content Format

Every filed issue follows a consistent structure:

```
Title: "Rafiki: {concise problem description}"

Description:
  ## Context
  - Run ID: {run_id}
  - Stage: {current stage or "verification"}
  - Timestamp: {ISO 8601}

  ## Problem
  {Detailed description of what went wrong}

  ## Evidence
  {Relevant output, error messages, or artifact snippets}

  ## Expected Behavior
  {What Rafiki expected to see}

  ## Suggested Fix
  {If determinable from context}
```

### 9.4 Issue Labeling Convention

All Rafiki-filed issues carry these labels:
- `discovered-by:rafiki` — identifies the source as Rafiki (vs. human or another agent)
- `rafiki-run:{run_id}` — links all issues from a single run for batch analysis
- `discovered-from:{source}` — where in Rafiki's lifecycle the issue was found

### 9.5 Issue Filing in the Run Report

The run report includes a `issues_filed` section listing every Beads issue Rafiki created:

```json
"issues_filed": [
  {
    "issue_id": "gt-120",
    "title": "Rafiki: pytest failed - 3 tests in test_arithmetic.py",
    "type": "bug",
    "priority": 0,
    "source": "verification",
    "filed_at": "2026-02-17T10:20:33Z"
  },
  ...
],
"issues_filed_count": 3
```

---

## 10. Run Report

Rafiki generates a structured JSON report at the end of each run:

```json
{
  "run_id": "rafiki-2026-02-17T09-15-00",
  "started_at": "2026-02-17T09:15:00Z",
  "completed_at": "2026-02-17T10:23:45Z",
  "duration_seconds": 4125,
  "project_key": "sci-calc",
  "outcome": "PASS",
  "lifecycle_states": [
    {"state": "INITIALIZING", "entered_at": "...", "duration_ms": 150},
    {"state": "CREATING_PROJECT", "entered_at": "...", "duration_ms": 2300},
    ...
  ],
  "reviews_handled": [
    {"issue_id": "...", "decision": "approved", "feedback": "...", "strategy": "llm", "at": "..."}
  ],
  "questions_answered": [
    {"issue_id": "...", "answer": "B", "rationale": "...", "strategy": "context_match", "at": "..."}
  ],
  "chat_interactions": [
    {"prompt": "...", "response": "...", "at": "..."}
  ],
  "stalls_detected": 0,
  "issues_filed": [
    {"issue_id": "gt-120", "title": "Rafiki: ...", "type": "bug", "priority": 0, "source": "verification", "filed_at": "..."}
  ],
  "issues_filed_count": 0,
  "verification": {
    "overall": "PASS",
    "checks": [
      {"name": "artifacts_exist", "passed": true, "detail": "...", "duration_ms": 50},
      ...
    ]
  }
}
```

---

## 11. Failure Handling

Every failure that Rafiki detects results in a **Beads issue** being filed (see Section 9) so the problem is tracked and can be fixed in follow-up steps. The issue is filed first, then Rafiki decides whether to retry, recover, or abort.

### 11.1 Stall Detection

The monitor tracks the timestamp of the last meaningful event (new review gate, new question, stage completion, notification). If no event occurs within `stall_threshold` (default 5 minutes):

1. Increment stall counter.
2. **File a Beads bug** (P0): "Rafiki: Pipeline stalled for N minutes at stage: {stage}".
3. Chat with Harmbe: "No progress detected in 5 minutes. What's happening?"
4. Check notifications for error reports.
5. If stall_count > `max_stalls`, fail the run with a detailed stall report.

### 11.2 API Errors

- **Connection refused** → Retry with exponential backoff (1s, 2s, 4s, 8s, max 30s). After 10 retries, **file a Beads bug** (P0) and fail.
- **5xx errors** → Retry up to 3 times with 2s delay. If persistent, **file a Beads bug** (P0).
- **4xx errors** → Do not retry. Log the error and decide based on context (e.g., 404 on review gate means it was already handled).
- **WebSocket disconnect** → Automatic reconnection with backoff. Fall back to polling.

### 11.3 Decision Errors

- **LLM timeout/error** → Fall back to rule-based decision. **File a Beads task** (P2) noting the LLM failure.
- **Unexpected artifact format** → Auto-approve with warning. **File a Beads task** (P2) noting the format issue for later investigation.
- **Unknown question format** → Select first option with warning. **File a Beads task** (P2).

### 11.4 Global Timeout

`max_runtime` (default 2 hours) is a hard limit. If exceeded, Rafiki:
1. **Files a Beads bug** (P0): "Rafiki: Pipeline exceeded max runtime of N hours".
2. Logs all current state.
3. Generates a partial run report.
4. Exits with non-zero exit code.

---

## 12. Docker Support

Rafiki runs as an optional service in the Docker Compose stack:

```yaml
# infra/docker-compose.yml (addition)
rafiki:
  profiles: ["rafiki"]
  build:
    context: ..
    dockerfile: infra/Dockerfile.rafiki
  environment:
    - RAFIKI_API_URL=http://orchestrator:8000
    - RAFIKI_WS_URL=ws://orchestrator:8000/ws
    - RAFIKI_PROJECT_KEY=sci-calc
    - RAFIKI_AUTO_APPROVE=${RAFIKI_AUTO_APPROVE:-false}
  depends_on:
    orchestrator:
      condition: service_healthy
  networks:
    - gorilla-net
```

Start with: `docker compose --profile rafiki up`

---

## 13. Design Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Location | Standalone `rafiki/` package | External client, not an internal agent. No orchestrator imports. |
| Primary interaction | REST API via httpx | Same interface humans use. Tests the real user path. |
| Real-time events | WebSocket with polling fallback | Low-latency event handling, resilient to disconnects. |
| Review strategy | Hybrid: rules + LLM + auto-approve | Structural validation catches obvious issues; LLM catches semantic problems; auto-approve for speed. |
| Question strategy | Context-matching + LLM tiebreaker | Project docs drive answers; LLM handles ambiguity. |
| Lifecycle model | Async state machine | Clean state transitions, observable, resumable. |
| State persistence | JSON file | Simple, human-readable, no extra dependencies. |
| Configuration | CLI > env > YAML > defaults | Standard layered config for flexibility across local dev and Docker. |
| Verification | Build + test + lint + API spot-checks | Proves the generated code actually works, not just that files exist. |
| Issue filing | Beads issues via `bd` CLI | Every discovered problem becomes a tracked, prioritized, actionable issue — not just a log line. |
| Cleanup | Always runs via `finally` | Simulated project, generated files, and pipeline issues are removed. Rafiki-filed bugs are preserved. |
| Report format | Structured JSON | Machine-parseable for CI/CD integration. |
