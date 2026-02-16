<!-- beads-issue: gt-37 -->
<!-- beads-review: gt-38 -->
# Functional Design -- Unit 4: Context Dispatch + Agent Engine

## Overview

Unit 4 is the **heart of the orchestrator**. It provides:
1. **Context Dispatch Protocol** -- standardized message format for agent-to-agent stage delegation
2. **Agent Engine** -- lifecycle management for agent instances (create, start, stop, spawn)
3. **Project Registry** -- multi-project state management
4. **Notification Manager** -- priority-ordered notification queue for humans

---

## Module: `context/dispatch.py` -- Context Dispatch Protocol

The CDP defines how Project Minder delegates stage work to Chimps and receives results.

### Data Models

```python
@dataclass
class DispatchMessage:
    """Message sent from Project Minder to a Chimp to execute a stage."""
    stage_name: str              # e.g., "requirements-analysis"
    stage_type: str              # e.g., "functional-design", "code-generation"
    beads_issue_id: str          # The Beads issue for this stage
    review_gate_id: str | None   # Review gate issue ID (if applicable)
    unit_name: str | None        # Construction unit (e.g., "unit-1-scribe")
    phase: str                   # "inception" or "construction"
    
    # Context artifacts to load
    input_artifacts: list[str]   # Paths to artifacts the Chimp should read
    reference_docs: list[str]    # Additional reference docs
    
    # Execution parameters
    project_key: str             # Agent Mail project key
    workspace_root: str          # Path to workspace root
    
    # Agent assignment
    assigned_agent: str          # Which Chimp type should handle this
    
    # Optional overrides
    instructions: str | None = None  # Additional instructions from Project Minder

@dataclass
class CompletionMessage:
    """Message sent from a Chimp back to Project Minder after completing a stage."""
    stage_name: str
    beads_issue_id: str
    status: str                  # "completed", "failed", "needs_rework"
    
    # Output
    output_artifacts: list[str]  # Paths to created/updated artifacts
    summary: str                 # Human-readable summary of what was done
    
    # Discovered work
    discovered_issues: list[dict]  # New issues to create [{title, type, priority, description}]
    
    # Error info (if status != "completed")
    error_detail: str | None = None
    rework_reason: str | None = None
```

### Functions

#### `build_dispatch(stage_name, beads_issue_id, ...) -> DispatchMessage`

Factory function that constructs a DispatchMessage with defaults filled in.

**Business Rules**:
1. Automatically determine `assigned_agent` from stage_name using the STAGE_AGENT_MAP
2. Load input_artifacts from the Beads issue notes field (artifact: ... lines)
3. Include the relevant AIDLC rule file as a reference doc

#### `serialize_dispatch(msg: DispatchMessage) -> str`

Serialize to JSON string for Agent Mail transmission.

#### `deserialize_dispatch(data: str) -> DispatchMessage`

Deserialize from JSON string.

#### `build_completion(stage_name, beads_issue_id, output_artifacts, summary, ...) -> CompletionMessage`

Factory function for building completion messages.

#### `serialize_completion(msg: CompletionMessage) -> str` / `deserialize_completion(data: str) -> CompletionMessage`

Serialization pair for completion messages.

### Stage-to-Agent Mapping

```python
STAGE_AGENT_MAP = {
    # Inception
    "workspace-detection": "Scout",
    "reverse-engineering": "Scout",
    "requirements-analysis": "Sage",
    "user-stories": "Bard",
    "workflow-planning": "Planner",
    "application-design": "Architect",
    "units-generation": "Planner",
    # Construction
    "functional-design": "Sage",
    "nfr-requirements": "Steward",
    "nfr-design": "Steward",
    "infrastructure-design": "Architect",
    "code-generation": "Forge",
    "build-and-test": "Crucible",
}
```

---

## Module: `engine/agent_engine.py` -- Agent Lifecycle Manager

### `AgentEngine`

```python
class AgentEngine:
    """Manages agent lifecycle: spawn, track, and stop agent instances."""
    
    def __init__(self, config: EngineConfig):
        self._agents: dict[str, AgentInstance] = {}
        self._config = config
    
    async def spawn_agent(self, agent_type: str, context: dict) -> AgentInstance:
        """Spawn a new agent instance for a task.
        
        Args:
            agent_type: The agent role (e.g., "Scout", "Forge")
            context: Configuration dict including dispatch message
        
        Returns:
            AgentInstance handle
        """
    
    async def stop_agent(self, agent_id: str, reason: str = "") -> None:
        """Gracefully stop an agent instance."""
    
    def get_agent(self, agent_id: str) -> AgentInstance | None:
        """Get an active agent by ID."""
    
    def list_active(self) -> list[AgentInstance]:
        """List all currently active agents."""
    
    async def shutdown(self) -> None:
        """Gracefully shut down all agents."""
```

### `AgentInstance`

```python
@dataclass
class AgentInstance:
    agent_id: str
    agent_type: str              # "Scout", "Forge", etc.
    status: str                  # "starting", "running", "stopping", "stopped", "error"
    created_at: datetime
    project_key: str
    current_task: str | None     # Beads issue ID being worked on
```

### `EngineConfig`

```python
@dataclass
class EngineConfig:
    max_concurrent_agents: int = 4
    agent_timeout_seconds: int = 3600    # 1 hour max per agent
    model_id: str = "anthropic.claude-opus-4-6"
    aws_region: str = "us-east-1"
```

---

## Module: `engine/project_registry.py` -- Multi-Project State

```python
@dataclass
class ProjectState:
    project_key: str
    name: str
    workspace_path: str
    status: str                  # "active", "paused", "completed"
    minder_agent_id: str | None  # The Project Minder agent for this project
    created_at: datetime
    paused_at: datetime | None = None

class ProjectRegistry:
    """Manages multiple AIDLC projects."""
    
    def create_project(self, key: str, name: str, workspace_path: str) -> ProjectState:
        """Register a new project."""
    
    def get_project(self, key: str) -> ProjectState | None:
        """Get project by key."""
    
    def list_projects(self, status: str | None = None) -> list[ProjectState]:
        """List all projects, optionally filtered by status."""
    
    def pause_project(self, key: str) -> None:
        """Pause a project (suspends its Project Minder)."""
    
    def resume_project(self, key: str) -> None:
        """Resume a paused project."""
    
    def update_project(self, key: str, **kwargs) -> None:
        """Update project fields."""
```

**Persistence**: Project state is persisted to `{workspace}/.gorilla-troop/projects.json`.

---

## Module: `engine/notification_manager.py` -- Notification Queue

```python
@dataclass
class Notification:
    id: str
    type: str                    # "review_gate", "escalation", "status_update", "info"
    title: str
    body: str
    project_key: str
    priority: int                # 0 (critical) - 4 (info)
    created_at: datetime
    read: bool = False
    source_issue: str | None = None  # Beads issue ID

class NotificationManager:
    """Priority-ordered notification queue for human users."""
    
    def add(self, notification: Notification) -> None:
        """Add a notification to the queue."""
    
    def get_unread(self, project_key: str | None = None, limit: int = 20) -> list[Notification]:
        """Get unread notifications, highest priority first."""
    
    def mark_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
    
    def clear_project(self, project_key: str) -> None:
        """Clear all notifications for a project."""
```

**Priority ordering**:
1. P0: Review gates awaiting approval
2. P1: Escalations from Curious George
3. P2: Stage completions
4. P3: Q&A questions needing answers
5. P4: Informational (session summaries, sync status)

---

## Dependencies

- **Internal**: `orchestrator.lib.beads`, `orchestrator.lib.agent_mail`, `orchestrator.lib.bonobo`
- **Python stdlib**: `asyncio`, `dataclasses`, `json`, `uuid`, `datetime`, `pathlib`
- **External**: None (Strands SDK will be added in Unit 5 when agents are actually defined)
