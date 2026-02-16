<!-- beads-issue: gt-5 -->
<!-- beads-review: gt-16 -->
# Requirements Document -- Gorilla Troop Multi-Agent System

## Intent Analysis

- **User Request**: Build a multi-agent AI system ("Gorilla Troop") that orchestrates the AIDLC workflow using Strands Agents on Amazon Bedrock. The system should support multiple concurrent projects, provide a rich human interface (dashboard + CLI + async messaging), and run locally via Docker Compose with a migration path to AWS.
- **Request Type**: New Feature (new system layered onto existing AIDLC-Beads framework)
- **Scope Estimate**: System-wide (new orchestrator, dashboard, agent fleet, communication layer, enhanced Outline integration)
- **Complexity Estimate**: Complex (16 agents, 4 communication channels, 6 Docker services, multi-project support)
- **Requirements Depth**: Comprehensive

## Source Documents

Requirements in this document are derived from:

1. `docs/design/gorilla-troop-architecture.md` -- Primary source. Detailed agent roster, communication infrastructure, deployment architecture, filesystem model, and implementation phases.
2. `aidlc-docs/inception/reverse-engineering/` -- 8 artifacts documenting the existing AIDLC-Beads codebase that Gorilla Troop builds upon.
3. Conversation history -- Iterative design decisions made during the architecture discussion.

---

## Functional Requirements

### FR-01: Agent Orchestration Engine

**FR-01.1**: The system SHALL implement a Python-based orchestrator process that hosts all Strands agents within a single process.

**FR-01.2**: The orchestrator SHALL use Amazon Bedrock as the LLM provider, with Claude Opus 4.6 (Global Endpoints) as the default model for all agents.

**FR-01.3**: The orchestrator SHALL support running multiple Project Minder instances concurrently, one per active project.

**FR-01.4**: Agents SHALL be implemented using the Strands Agents SDK, following these patterns:
- Harmbe: Agents as Tools (top-level orchestrator)
- Project Minder: Graph (AIDLC dependency graph with conditional edges)
- Chimps (Scout, Sage, Bard, Planner, Architect, Steward, Forge, Crucible): Agents as Tools (invoked by Project Minder)
- Bonobo: Tool execution wrapper
- Groomer: Event-driven agent
- Snake: Validation agent
- Curious George: Agents as Tools (invoked on error by any agent)
- Gibbon: Agents as Tools (invoked for rework by Project Minder)
- Troop: Short-lived task workers (spawned and terminated per task)

**FR-01.5**: The orchestrator SHALL implement the Context Dispatch Protocol, where Project Minder sends structured dispatch messages to Chimps containing: stage name, Beads issue references, artifact paths to load, human feedback, and stage-specific instructions.

### FR-02: Agent Fleet -- Tier 1: Orchestration

**FR-02.1 (Harmbe)**: Harmbe SHALL be the sole human-facing agent, receiving all human input through Chat UI, CLI, and Agent Mail, and routing decisions to downstream agents.

**FR-02.2 (Harmbe)**: Harmbe SHALL maintain a persistent project registry mapping project names to workspace paths, Project Minder instances, Beads prefixes, and status.

**FR-02.3 (Harmbe)**: Harmbe SHALL persist state across sessions, reconstructing context from Beads state and Agent Mail threads on reconnect.

**FR-02.4 (Harmbe)**: Harmbe SHALL manage background notifications with prioritization: review gates > escalations > status updates > informational.

**FR-02.5 (Project Minder)**: Project Minder SHALL own the AIDLC dependency graph for a single project, querying Beads (`bd ready`, `bd blocked`) to determine stage execution order.

**FR-02.6 (Project Minder)**: Project Minder SHALL enforce review gate protocol: create review gate issues, notify Harmbe, and wait for approval before dispatching the next stage.

**FR-02.7 (Project Minder)**: Project Minder SHALL handle conditional stage skip recommendations, forwarding to Harmbe for user approval before marking any stage as skipped.

### FR-03: Agent Fleet -- Tier 2: Stage Specialists (Chimps)

**FR-03.1**: Each Chimp SHALL follow a standard contract: receive dispatch via Agent Mail, execute stage per AIDLC rules, create artifacts using the Scribe tool library, and send completion message via Agent Mail.

**FR-03.2 (Scout)**: Scout SHALL handle Workspace Detection (Stage 1) and Reverse Engineering (Stage 2), producing codebase analysis artifacts.

**FR-03.3 (Sage)**: Sage SHALL handle Requirements Analysis (Stage 3), generating clarifying questions and requirements documents.

**FR-03.4 (Bard)**: Bard SHALL handle User Stories (Stage 4), creating personas and user stories with INVEST criteria.

**FR-03.5 (Planner)**: Planner SHALL handle Workflow Planning (Stage 5) and Units Generation (Stage 7), producing execution plans and unit decomposition.

**FR-03.6 (Architect)**: Architect SHALL handle Application Design (Stage 6), producing component and service designs with Mermaid diagrams.

**FR-03.7 (Steward)**: Steward SHALL handle NFR Requirements (Stage 9), NFR Design (Stage 10), and Infrastructure Design (Stage 11).

**FR-03.8 (Forge)**: Forge SHALL handle Functional Design (Stage 8) and Code Generation (Stage 12), producing domain models, business rules, application code, and unit tests.

**FR-03.9 (Crucible)**: Crucible SHALL handle Build and Test (Stage 13), executing builds, running tests, and producing test summary artifacts.

### FR-04: Agent Fleet -- Tier 3: Cross-Cutting Roles

**FR-04.1 (Bonobo)**: Bonobo SHALL guard and execute all write operations: filesystem writes, git commits, Beads state mutations, and Outline sync pushes. All write operations from any agent MUST go through Bonobo.

**FR-04.2 (Bonobo -- Git)**: Git Bonobo SHALL enforce the branch model: agents never commit to `main`; Inception work goes to `aidlc/inception`; Construction work goes to `aidlc/construction/<unit-name>`; rework goes to `aidlc/rework/<name>`.

**FR-04.3 (Bonobo -- Git)**: Git Bonobo SHALL perform automatic clean merges for rework branches, attempt LLM-based conflict resolution for conflicting merges, and escalate unresolvable conflicts to Harmbe.

**FR-04.4 (Bonobo -- Git)**: Every agent commit SHALL include the Beads issue ID, agent name, and stage name in the format `[<issue-id>] <message>`.

**FR-04.5 (Groomer)**: Groomer SHALL monitor its Agent Mail inbox for state-change notifications (review gate closures, Q&A answers, Outline edits) and forward them to Project Minder or Harmbe.

**FR-04.6 (Groomer)**: On session startup, Groomer SHALL compile a status report from its accumulated Agent Mail inbox.

**FR-04.7 (Groomer)**: Groomer SHALL detect stale state: issues stuck in_progress, unanswered Q&As past threshold, overdue review gates.

**FR-04.8 (Snake)**: Snake SHALL perform security reviews at defined checkpoints: after NFR stages, after Code Generation, and during Build and Test.

**FR-04.9 (Snake)**: Snake SHALL perform static analysis, dependency vulnerability scanning, secrets detection, and OWASP compliance checks on generated code.

### FR-05: Agent Fleet -- Tier 4: Error Recovery and Rework

**FR-05.1 (Curious George)**: Curious George SHALL receive error reports from any agent via Agent Mail, investigate the root cause, attempt autonomous correction for within-scope fixes, and escalate to Harmbe for human help when the fix is beyond scope.

**FR-05.2 (Gibbon)**: Gibbon SHALL receive rework requests from Project Minder (triggered by rejected review gates, requirements changes, or security issues), re-invoke the appropriate Chimp with the original artifact plus feedback, and manage cascade rework chains.

### FR-06: Agent Fleet -- Tier 5: Ad-Hoc Workers

**FR-06.1 (Troop)**: Troop workers SHALL be short-lived agents spawned by Project Minder or Chimps for specific tasks (research, library comparison, template generation), returning structured results and terminating.

### FR-07: Scribe Tool Library

**FR-07.1**: Scribe SHALL be implemented as a Python module (not an agent) providing deterministic artifact management functions.

**FR-07.2**: Scribe SHALL provide these functions:
- `create_artifact(stage, name, content, beads_issue_id, review_gate_id)` -- create markdown file with correct headers and directory placement
- `validate_artifact(path)` -- check headers, directory, cross-references
- `register_artifact(beads_issue_id, artifact_path)` -- update Beads issue notes
- `sync_to_outline()` / `pull_from_outline()` -- run sync-outline.py
- `apply_template(template_name, variables)` -- fill artifact templates
- `list_stage_artifacts(stage_name)` -- list artifacts for a stage

### FR-08: Harmbe Dashboard (Primary Human Interface)

**FR-08.1**: The dashboard SHALL be a web application with a FastAPI backend and React frontend, accessible at `http://localhost:3001`.

**FR-08.2**: The dashboard SHALL provide these panels:
- **Chat Panel**: Real-time conversational interface with Harmbe (WebSocket)
- **Document Review Panel**: Inline markdown viewer/editor with approve/reject/request-changes controls
- **Project Status Panel**: Visual AIDLC dependency graph showing current stage, completed stages, blocked stages, and pending review gates
- **Notification Center**: Prioritized list of items needing human attention (review gates, Q&A, escalations)
- **Multi-Project Sidebar**: List of all active projects with status indicators (green/yellow/red)

**FR-08.3**: The dashboard review workflow SHALL allow humans to: receive review gate notifications, view artifacts inline, edit them optionally, and approve/reject with feedback -- all without leaving the dashboard.

**FR-08.4**: The dashboard SHALL communicate with the orchestrator via WebSocket (real-time) and REST API (queries).

### FR-09: CLI Interface

**FR-09.1**: The system SHALL provide a CLI (`gorilla` or `gt`) that sends structured messages to Harmbe and prints responses.

**FR-09.2**: The CLI SHALL support commands: `gt status`, `gt projects`, `gt approve <issue-id>`, `gt pause <project>`, `gt resume <project>`.

### FR-10: Outline Wiki Integration (Enhanced)

**FR-10.1**: Outline documents SHALL display review status flags: "Draft", "Awaiting Review", "In Review", "Approved", "Changes Requested", "Rework In Progress", synced from Beads issue state.

**FR-10.2**: Outline SHALL provide action buttons: "Done Editing", "Approve", "Request Changes", "Ask Harmbe", which send instructions to Harmbe via Agent Mail.

**FR-10.3**: The existing `sync-outline.py` SHALL be enhanced to push review status metadata alongside document content and relay Outline action events to Harmbe.

### FR-11: Communication Infrastructure

**FR-11.1**: The system SHALL use MCP Agent Mail for asynchronous inter-agent messaging, with thread IDs mapped to Beads issue IDs.

**FR-11.2**: Agent Mail file reservations SHALL be used to prevent artifact conflicts when multiple agents could write to the same file.

**FR-11.3**: Agent Mail's Human Overseer feature SHALL be available for humans to send direct messages to agents.

**FR-11.4**: Beads SHALL remain the source of truth for workflow state (issue status, dependencies, priorities). Agent Mail is for messaging, not state.

### FR-12: Multi-Project Support

**FR-12.1**: The system SHALL support managing multiple projects simultaneously, each with its own Project Minder instance, Beads database, and workspace directory.

**FR-12.2**: The project registry SHALL persist project configurations including name, host path, container path, Beads prefix, Project Minder ID, and status.

**FR-12.3**: Users SHALL be able to create new projects, pause/resume projects, and switch project context through Harmbe.

### FR-13: Filesystem Model

**FR-13.1**: The developer SHALL own the Git repositories on their host machine. Gorilla Troop SHALL mount the developer's existing directories via Docker bind mounts, not clone or own the repos.

**FR-13.2**: All projects SHALL live under a configurable projects root directory, mounted into the orchestrator (read-write) and dashboard (read-only) containers.

**FR-13.3**: File changes by agents SHALL appear immediately on the host (Docker bind mount), and file changes by the developer SHALL appear immediately to agents.

---

## Non-Functional Requirements

### NFR-01: Performance

**NFR-01.1**: Stage execution latency is dominated by LLM round-trips (Bedrock). The system SHALL NOT add significant overhead beyond LLM call time. Accuracy is prioritized over speed.

**NFR-01.2**: The dashboard SHALL respond to user interactions within 2 seconds for status queries and navigation.

**NFR-01.3**: Agent Mail message delivery SHALL complete within 1 second for local deployment.

### NFR-02: Reliability

**NFR-02.1**: The system SHALL be resilient to orchestrator container restarts. On restart, the orchestrator SHALL reconstruct state from Beads (`bd ready`, `bd list --status in_progress`) and Agent Mail inbox.

**NFR-02.2**: All workflow state SHALL be durable via Beads JSONL export (Git-tracked) and Agent Mail persistence (SQLite + Git archive).

**NFR-02.3**: No agent action SHALL produce irreversible damage: agents never commit to `main`, all writes go through Bonobo, and file reservations prevent concurrent writes.

### NFR-03: Security

**NFR-03.1**: AWS credentials for Bedrock SHALL be provided via mounted `~/.aws` directory (preferred) or environment variables -- never hardcoded.

**NFR-03.2**: Agent Mail SHALL require a bearer token for API authentication.

**NFR-03.3**: For local development, the dashboard SHALL be accessible on localhost only. Authentication is deferred to AWS migration phase.

**NFR-03.4**: Snake SHALL enforce security scanning on all generated code before it reaches review gates.

### NFR-04: Maintainability

**NFR-04.1**: Each agent SHALL be defined as a separate Python module with its own system prompt, tool list, and invocation contract.

**NFR-04.2**: Agent system prompts SHALL be stored as separate files (not inline strings) to enable iterative tuning without code changes.

**NFR-04.3**: The orchestrator codebase SHALL follow standard Python packaging conventions with `pyproject.toml` or `setup.py`.

### NFR-05: Observability

**NFR-05.1**: The orchestrator SHALL log all agent invocations, tool calls, and state transitions to structured logs (JSON format).

**NFR-05.2**: Agent Mail messages SHALL serve as an audit trail for all inter-agent communication and human decisions.

**NFR-05.3**: Beads event log SHALL record all workflow state changes with timestamps.

### NFR-06: Portability

**NFR-06.1**: The local Docker Compose deployment SHALL map cleanly to AWS services (ECS Fargate, RDS, ElastiCache, EFS) without agent logic changes.

**NFR-06.2**: Agent code (Strands agents), Agent Mail API calls, Beads CLI usage, Scribe tool library, Context Dispatch Protocol, and Dashboard UI code SHALL remain unchanged during AWS migration.

**NFR-06.3**: The migration boundary SHALL be purely infrastructure: swap Docker Compose for Terraform/CDK, point service URLs to AWS endpoints, add IAM roles.

### NFR-07: Scalability (Future)

**NFR-07.1**: The agent architecture SHALL support adding new Chimp agents for additional AIDLC stages without modifying the orchestrator core.

**NFR-07.2**: The multi-project support SHALL be designed to handle 5+ concurrent projects (limited by Bedrock API throughput, not system architecture).

### NFR-08: Developer Experience

**NFR-08.1**: The developer SHALL be able to use their existing IDE (Cursor, VS Code) alongside the Gorilla Troop dashboard, viewing the same files.

**NFR-08.2**: Agent file reservations SHALL be visible in the dashboard so developers know which files are currently being modified by agents.

**NFR-08.3**: The `gt` CLI SHALL provide quick access to common operations without opening the dashboard.

---

## Technical Constraints

### TC-01: Technology Stack
- **Runtime**: Python 3.11+
- **Agent Framework**: Strands Agents SDK
- **LLM Provider**: Amazon Bedrock (Claude Opus 4.6 default, Global Endpoints)
- **Dashboard Backend**: FastAPI
- **Dashboard Frontend**: React
- **Communication**: MCP Agent Mail (FastMCP HTTP Server)
- **Workflow State**: Beads CLI (`bd`)
- **Document Review**: Outline Wiki (existing Docker setup)
- **Containerization**: Docker Compose (local), ECS Fargate (future)

### TC-02: Existing System Integration
- The system MUST preserve compatibility with the existing AIDLC-Beads framework: rules, templates, Beads database schema, Outline sync, and cross-reference conventions.
- The existing `sync-outline.py` script MUST be enhanced, not replaced.
- The existing `AGENTS.md` rule system MUST be usable by the new agent fleet.

### TC-03: Git Model
- Agents MUST NOT commit to `main`.
- All agent work MUST go to `aidlc/*` branches.
- The developer controls merges to `main`.

---

## Assumptions

1. **Single machine (V1)**: The system runs on a single developer's laptop. Multi-user access is out of scope for V1.
2. **Bedrock availability**: Amazon Bedrock with Claude Opus 4.6 is available and the developer has appropriate IAM credentials.
3. **Docker available**: Docker Desktop (or equivalent) is installed and running on the developer's machine.
4. **Beads CLI installed**: The `bd` CLI is already installed and functional (confirmed by existing project).
5. **Local-first**: No internet dependency beyond Bedrock API calls. All other services run locally.
6. **No authentication (V1)**: Dashboard and Agent Mail are localhost-only. Authentication is deferred to AWS migration.

---

## Out of Scope (V1)

1. AWS deployment (Phase 2 -- documented in architecture but not implemented in V1)
2. Multi-user authentication and authorization
3. IDE extension for file reservation awareness
4. Performance optimization / model selection per agent
5. Automated CI/CD pipeline for the Gorilla Troop system itself
6. Production monitoring and alerting (beyond structured logging)
