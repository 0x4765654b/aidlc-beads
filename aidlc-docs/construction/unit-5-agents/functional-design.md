<!-- beads-issue: gt-47 -->
<!-- beads-review: gt-48 -->
# Functional Design -- Unit 5: Agent Definitions (16 Roles)

## Architecture

All agents share a common base class `BaseAgent` that provides:
- Strands SDK integration (model configuration, tool binding)
- Agent Mail identity registration
- Dispatch message handling (receive, deserialize, execute, respond)
- Error reporting (to Curious George)
- Audit logging (via Bonobo)

Each agent has:
- `agent.py` -- agent class with Strands configuration
- `prompt.md` -- system prompt template
- `tools.py` -- Strands tool definitions bound to this agent

**Module path**: `orchestrator/agents/`

---

## Base Class: `BaseAgent`

```python
class BaseAgent:
    """Base class for all Gorilla Troop agents."""
    
    agent_type: str                  # e.g., "Scout"
    agent_mail_identity: str         # e.g., "Scout"
    model_id: str = "anthropic.claude-opus-4-6"
    
    def __init__(self, engine: AgentEngine, mail: AgentMailClient, beads_guard: BeadsGuard, ...):
        ...
    
    async def handle_dispatch(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Main entry point: receive a stage dispatch, execute, return completion."""
    
    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Subclass override: perform the actual stage work."""
    
    async def _load_context(self, dispatch: DispatchMessage) -> str:
        """Load input artifacts and reference docs into context string."""
    
    async def _report_error(self, error: Exception, dispatch: DispatchMessage) -> None:
        """Send error to Curious George for investigation."""
    
    def _get_tools(self) -> list:
        """Return Strands tool definitions for this agent."""
```

---

## 1. Harmbe -- Silverback (Supervisor)

**Pattern**: Agents as Tools (top-level orchestrator)
**Mail Identity**: `Harmbe`

**Responsibilities**:
- Sole human interface across Chat UI, CLI, and Agent Mail
- Project registry management (create, pause, resume, list)
- Route human decisions: approvals, Q&A answers, skip permissions
- Escalation handler for unrecoverable agent errors
- Notification management for humans

**Tools**:
- `project_create(name, workspace_path)` -- register new project
- `project_list()` -- list all projects with status
- `project_status(key)` -- detailed project status
- `project_pause(key)` / `project_resume(key)`
- `approve_review(issue_id, feedback?)` -- approve a review gate
- `reject_review(issue_id, feedback)` -- reject with feedback
- `answer_qa(issue_id, answer)` -- answer a Q&A question
- `approve_skip(issue_id)` / `deny_skip(issue_id)`
- `get_notifications(project_key?)` -- unread notifications
- `search_history(query)` -- search Agent Mail and Beads

**Does NOT**: Execute AIDLC stages, create artifacts, invoke OS tools

---

## 2. Project Minder -- Beta Ape

**Pattern**: Graph (AIDLC dependency graph)
**Mail Identity**: `ProjectMinder`

**Responsibilities**:
- Owns the AIDLC workflow graph for a single project
- Determines execution order via `bd ready`
- Dispatches stages to Chimps via Context Dispatch Protocol
- Manages review gate lifecycle
- Handles conditional stage skip recommendations

**Tools**:
- `dispatch_stage(stage_name, chimp_type)` -- send dispatch to a Chimp
- `check_ready()` -- query `bd ready` for next work
- `check_blocked()` -- query blocked issues
- `create_review_gate(stage_id, artifact_path)` -- create review gate issue
- `recommend_skip(stage_id, rationale)` -- recommend stage skip to Harmbe
- `update_stage_status(issue_id, status, notes)` -- update Beads
- `file_reservation(paths, reason)` -- reserve artifacts via Agent Mail

**Does NOT**: Create artifacts, interact with humans directly

---

## 3-10. Chimps (8 Specialist Workers)

All Chimps extend `BaseChimp(BaseAgent)` which adds:
- Scribe tool integration for artifact creation
- Standard dispatch/completion flow
- Input artifact loading

### 3. Scout -- Workspace Detection & Reverse Engineering

**Stages**: workspace-detection, reverse-engineering
**Tools**: `read_file`, `list_directory`, `search_code`, `scribe_create_artifact`, `scribe_validate`

### 4. Sage -- Requirements & Functional Design

**Stages**: requirements-analysis, functional-design
**Tools**: `read_artifact`, `scribe_create_artifact`, `scribe_update_artifact`, `search_beads_history`

### 5. Bard -- User Stories

**Stages**: user-stories
**Tools**: `read_artifact`, `scribe_create_artifact`, `search_prior_artifacts`

### 6. Planner -- Workflow Planning & Units Generation

**Stages**: workflow-planning, units-generation
**Tools**: `read_artifact`, `scribe_create_artifact`, `beads_list_issues`, `beads_create_issue`, `beads_add_dependency`

### 7. Architect -- Application Design & Infrastructure Design

**Stages**: application-design, infrastructure-design
**Tools**: `read_artifact`, `scribe_create_artifact`, `read_file`, `list_directory`

### 8. Steward -- NFR Requirements & NFR Design

**Stages**: nfr-requirements, nfr-design
**Tools**: `read_artifact`, `scribe_create_artifact`, `search_prior_artifacts`

### 9. Forge -- Code Generation

**Stages**: code-generation
**Tools**: `read_artifact`, `read_file`, `write_code_file` (via FileGuard), `git_commit` (via GitGuard), `run_linter`

### 10. Crucible -- Build and Test

**Stages**: build-and-test
**Tools**: `read_artifact`, `read_file`, `write_test_file`, `run_tests`, `run_linter`, `git_commit`

---

## 11. Bonobo -- Write Guard Agent

**Pattern**: Tool executor (validates then executes)
**Mail Identity**: `Bonobo`

Bonobo is unique: it wraps the guard libraries (Unit 3) as an agent that other agents invoke as a tool. When Forge needs to write a file, it calls the Bonobo tool, which validates via FileGuard and executes.

**Tools exposed to other agents**:
- `write_file(path, content)` -- via FileGuard
- `delete_file(path)` -- via FileGuard
- `git_commit(message, files, issue_id)` -- via GitGuard
- `git_create_branch(name)` -- via GitGuard
- `beads_create(title, type, priority, ...)` -- via BeadsGuard
- `beads_update(issue_id, ...)` -- via BeadsGuard
- `outline_push()` -- via Scribe outline_sync

---

## 12. Groomer -- Event Monitor

**Pattern**: Event-driven (triggered by Agent Mail messages)
**Mail Identity**: `Groomer`

**Responsibilities**:
- Monitor Agent Mail inbox for state-change notifications
- Session resume: compile status report from accumulated inbox
- Route notifications to Project Minder or Harmbe
- Detect stale state (stuck issues, overdue reviews)

**Tools**:
- `check_inbox()` -- fetch and process new messages
- `compile_status_report(project_key)` -- build session resume report
- `detect_stale(threshold_hours)` -- find stuck issues
- `notify_harmbe(title, body, priority)` -- send notification

---

## 13. Snake -- Security Validator

**Pattern**: Validation agent (invoked at checkpoints)
**Mail Identity**: `Snake`

**Checkpoints**: After NFR Design, after Code Generation, during Build & Test

**Tools**:
- `scan_artifact(path)` -- review document for security gaps
- `scan_code(path)` -- static analysis, dependency scan, secrets detection
- `scan_dependencies()` -- check for known vulnerabilities
- `generate_security_report(findings)` -- create formatted report

**Output**: Security report with severity levels (critical, high, medium, low, info)

---

## 14. Curious George -- Error Investigator

**Pattern**: Agents as Tools (invoked by any agent on error)
**Mail Identity**: `CuriousGeorge`

**Responsibilities**:
- Receive error reports from any agent
- Investigate: read logs, check Beads state, examine files
- Attempt correction if within scope
- Escalate to Harmbe if unresolvable

**Tools**:
- `read_file`, `read_beads_issue`, `read_agent_mail_thread`
- `attempt_fix(fix_description, files)` -- try a correction via Bonobo
- `escalate(diagnostic_report)` -- send to Harmbe

---

## 15. Gibbon -- Rework Specialist

**Pattern**: Agents as Tools (invoked when review is rejected)
**Mail Identity**: `Gibbon`

**Responsibilities**:
- Receive rework requests (rejected review gates with feedback)
- Load the original artifact and rejection feedback
- Apply corrections using the same tools as the original Chimp
- Resubmit for review

**Tools**: Same as the relevant Chimp for the stage being reworked, plus `read_review_feedback(issue_id)`

---

## 16. Troop -- General Purpose Worker

**Pattern**: Short-lived worker (spawned for ad-hoc tasks)
**Mail Identity**: `Troop-{uuid}`

**Use cases**: Discovered work, one-off research tasks, parallel subtasks

**Tools**: Full tool set (read, write via Bonobo, Scribe, Beads)

---

## Agent Communication Flow

```
Human -> Harmbe -> ProjectMinder -> Chimp (dispatch)
                                 <- Chimp (completion)
                   ProjectMinder -> Harmbe (review gate notification)
Human -> Harmbe -> ProjectMinder (approval)
                   ProjectMinder -> next Chimp (dispatch)

On error:
Chimp -> CuriousGeorge (error report)
CuriousGeorge -> Bonobo (attempt fix)
CuriousGeorge -> Harmbe (escalation if unfixable)

On rejection:
Harmbe -> ProjectMinder (rejection + feedback)
ProjectMinder -> Gibbon (rework request)
Gibbon -> ProjectMinder (completion)
```
