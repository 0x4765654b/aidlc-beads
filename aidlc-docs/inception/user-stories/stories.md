<!-- beads-issue: gt-6 -->
<!-- beads-review: gt-11 -->
# User Stories

## Epic: Project Lifecycle Management

### US-01: Create a New Project
**As** Alex (Developer), **I want** to tell Harmbe "Start a new project for X at this path" **so that** Gorilla Troop initializes the AIDLC workflow, creates the Beads database, and begins Inception without me manually running setup scripts.

**Acceptance Criteria**:
- [ ] Harmbe accepts project creation via Chat UI or CLI
- [ ] Harmbe prompts for: project name, workspace path, greenfield/brownfield
- [ ] Orchestrator initializes Beads with a unique prefix
- [ ] A Project Minder instance is spawned for the project
- [ ] Scout begins Workspace Detection automatically
- [ ] Project appears in the Multi-Project Sidebar

### US-02: Check Project Status
**As** Alex (Developer), **I want** to ask "Where are we on project X?" via chat or run `gt status` **so that** I get a human-friendly summary of current stage, blockers, pending reviews, and progress.

**Acceptance Criteria**:
- [ ] Harmbe queries Beads and Agent Mail for current state
- [ ] Response includes: current active stage, completed stages, pending review gates, blocked items, progress percentage
- [ ] Available via Chat UI, CLI (`gt status`), and Multi-Project Sidebar

### US-03: Pause and Resume a Project
**As** Jordan (Team Lead), **I want** to pause a project and resume it later **so that** I can manage resource priorities across multiple projects.

**Acceptance Criteria**:
- [ ] `gt pause project-x` or chat command suspends the Project Minder
- [ ] No new stages are dispatched while paused
- [ ] Beads state is preserved
- [ ] `gt resume project-x` re-activates the Project Minder
- [ ] Groomer compiles a status report on resume

### US-04: View All Projects
**As** Jordan (Team Lead), **I want** to see all active projects with their statuses in one view **so that** I can identify which projects need attention.

**Acceptance Criteria**:
- [ ] Multi-Project Sidebar shows all projects with color indicators (green/yellow/red)
- [ ] Green = progressing, Yellow = waiting for human, Red = error/escalation
- [ ] Clicking a project switches context to that project's status view

---

## Epic: Review and Approval Workflow

### US-05: Review an Artifact at a Review Gate
**As** Alex (Developer), **I want** to receive a notification when a review gate is ready, click it, read the artifact inline, and approve or reject **so that** I can review without leaving the dashboard.

**Acceptance Criteria**:
- [ ] Notification appears in Notification Center when a review gate is ready
- [ ] Clicking the notification opens the artifact in the Document Review Panel
- [ ] Artifact displays as rendered markdown with scrolling
- [ ] "Approve" and "Request Changes" buttons with feedback text area are visible
- [ ] Approval routes decision to Project Minder and unblocks next stage
- [ ] Rejection triggers rework via Gibbon

### US-06: Review an Artifact in Outline (Non-Technical)
**As** Morgan (Product Owner), **I want** to review an artifact in Outline Wiki with clear status badges and approve/reject buttons **so that** I don't need to learn developer tools.

**Acceptance Criteria**:
- [ ] Artifact in Outline shows review status: "Awaiting Review"
- [ ] "Approve" and "Request Changes" buttons are available
- [ ] Clicking "Approve" sends approval message to Harmbe via Agent Mail
- [ ] Morgan can edit the document before approving
- [ ] "Done Editing" button notifies Harmbe that edits are complete

### US-07: Request Changes with Feedback
**As** Alex (Developer), **I want** to reject an artifact with specific feedback text **so that** the AI agents know exactly what to fix during rework.

**Acceptance Criteria**:
- [ ] Feedback text area accepts freeform text
- [ ] Feedback is attached to the rework request sent to Gibbon
- [ ] Gibbon re-invokes the appropriate Chimp with the feedback in context
- [ ] Revised artifact appears at a new review gate

---

## Epic: Question Resolution

### US-08: Answer an AI Question
**As** Alex (Developer), **I want** to see AI-generated questions and answer them quickly **so that** the workflow isn't blocked waiting for my input.

**Acceptance Criteria**:
- [ ] Q&A questions appear in the Notification Center with high priority
- [ ] Questions display as multiple-choice with an "Other" option
- [ ] Answering routes the response to the blocked agent
- [ ] The blocked stage resumes automatically after the answer

### US-09: Ask Harmbe a Context Question
**As** Alex (Developer), **I want** to ask "What did we decide about authentication?" **so that** I can get context from past decisions without searching through documents.

**Acceptance Criteria**:
- [ ] Harmbe searches Agent Mail threads and Beads history
- [ ] Returns relevant context with references to decisions and artifacts
- [ ] Available via Chat UI and CLI

---

## Epic: Error Handling and Escalation

### US-10: Receive and Resolve an Escalation
**As** Alex (Developer), **I want** to be notified when Curious George cannot fix an error **so that** I can provide guidance and unblock the workflow.

**Acceptance Criteria**:
- [ ] Escalation notification appears with error description, investigation steps taken, and recommended actions
- [ ] Developer provides guidance via chat
- [ ] Harmbe routes guidance to the agent that escalated
- [ ] Workflow resumes after guidance is applied

### US-11: Skip a Conditional Stage
**As** Alex (Developer), **I want** the AI to recommend whether a conditional stage should be skipped, and for me to confirm **so that** unnecessary stages don't slow down the project.

**Acceptance Criteria**:
- [ ] Recommendation includes rationale for skipping
- [ ] Developer can approve skip or override ("No, execute it")
- [ ] Decision is recorded in Beads with the rationale

---

## Epic: CLI Operations

### US-12: Quick Approve via CLI
**As** Alex (Developer), **I want** to run `gt approve gt-0042.3` from the terminal **so that** I can approve a review gate without opening the dashboard.

**Acceptance Criteria**:
- [ ] CLI sends approval to Harmbe
- [ ] Harmbe routes to Project Minder
- [ ] Beads review gate is closed
- [ ] Next stage is dispatched

### US-13: Quick Status via CLI
**As** Alex (Developer), **I want** to run `gt status` for a one-line status summary **so that** I get a quick check without context switching.

**Acceptance Criteria**:
- [ ] Displays: project name, current stage, pending reviews count, errors count
- [ ] Exits immediately (no interactive mode)

---

## Epic: System Setup and Operations

### US-14: Start the System
**As** Alex (Developer), **I want** to run `docker compose up` and have the entire system ready **so that** setup is a single command.

**Acceptance Criteria**:
- [ ] All services start and become healthy
- [ ] Dashboard accessible at `http://localhost:3001`
- [ ] Outline accessible at `http://localhost:3000`
- [ ] Orchestrator connects to Bedrock successfully
- [ ] Agent Mail is initialized and reachable

### US-15: System Survives Restart
**As** Alex (Developer), **I want** the system to recover gracefully from a Docker restart **so that** I don't lose work or have to reconfigure.

**Acceptance Criteria**:
- [ ] All Beads state is preserved (JSONL export is git-tracked)
- [ ] Agent Mail messages are preserved (SQLite + volume)
- [ ] On restart, Groomer compiles inbox and reports what happened
- [ ] In-progress stages are detected and resumed
- [ ] No manual intervention needed

### US-16: Work Alongside IDE
**As** Alex (Developer), **I want** to open the same project in Cursor/VS Code while agents are working **so that** I can code alongside the AI.

**Acceptance Criteria**:
- [ ] File changes by agents appear immediately in the IDE (bind mount)
- [ ] File changes by the developer appear immediately to agents
- [ ] Dashboard shows which files have active agent reservations
- [ ] Git branches created by agents are visible in the IDE
