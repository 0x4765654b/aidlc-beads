# Architecture C: Hybrid with Clean Contract - Detailed Design

## Overview

Architecture C splits responsibility between two systems:

- **Beads** owns workflow state, task dependency graph, approval gates, Q&A, audit trail, and agent coordination.
- **Markdown** owns rich document artifacts (requirements, designs, stories, test plans).

A **cross-reference contract** links the two: every Beads issue that produces an artifact stores the file path, and every markdown artifact header includes its Beads issue ID.

---

## 1. Beads Issue Schema

### 1.1 Issue Prefix

All AIDLC-Beads issues use the prefix `ab-` (short for aidlc-beads).

### 1.2 Issue Types

Beads supports these issue types, mapped to AIDLC concepts:

| Beads Type | AIDLC Concept | Description |
|---|---|---|
| `epic` | Phase | Top-level container (Inception, Construction, Operations) |
| `task` | Stage | Individual workflow stage within a phase |
| `task` (sub-task) | Sub-step | Fine-grained step within a stage (e.g., "Generate requirements doc") |
| `task` | Review Gate | Blocking issue requiring human approval before next stage |
| `message` | Q&A | Question from AI to human, blocking until answered |

### 1.3 Priority Mapping

| Beads Priority | AIDLC Usage |
|---|---|
| P0 | Review gates and blocking Q&A (must resolve to proceed) |
| P1 | Always-execute stages (Workspace Detection, Requirements, Workflow Planning, Code Gen, Build & Test) |
| P2 | Conditional stages (User Stories, App Design, Units, NFR, Infra Design) |
| P3 | Housekeeping (audit sync, cleanup) |

### 1.4 Issue Fields Usage

| Beads Field | AIDLC Usage |
|---|---|
| `title` | Stage name or review gate description |
| `description` | Stage purpose, prerequisites, and execution summary |
| `design` | Stage-specific design notes (for construction stages) |
| `notes` | **Cross-reference to artifact file path** and free-form notes |
| `acceptance` | Completion criteria for the stage |
| `status` | `open`, `in_progress`, `done`, `blocked` |
| `assignee` | Agent ID or `human` for review gates |
| `labels` | `phase:inception`, `phase:construction`, `type:review-gate`, `type:qa`, `always`, `conditional` |

### 1.5 Dependency Links

| Link Type | AIDLC Usage |
|---|---|
| `parent` / `child` | Phase-to-stage hierarchy (epic contains tasks) |
| `blocks` | Stage ordering (Requirements blocks Workflow Planning) |
| `blocks` | Review gates block next stage |
| `relates_to` | Cross-unit references (e.g., NFR Design relates to Functional Design) |
| `discovered-from` | Work items discovered during execution |

---

## 2. AIDLC Phase-to-Epic Mapping

### 2.1 Phase Epics

```
ab-XXXX  INCEPTION PHASE (epic, P1)
ab-XXXX  CONSTRUCTION PHASE (epic, P1)
ab-XXXX  OPERATIONS PHASE (epic, P3)
```

### 2.2 Inception Stage Tasks (Children of Inception Epic)

```
ab-XXXX.1  Workspace Detection          (task, P1, always, no review gate)
ab-XXXX.2  Reverse Engineering          (task, P2, conditional)
ab-XXXX.3  REVIEW: Reverse Engineering  (task, P0, review-gate, assignee=human)
ab-XXXX.4  Requirements Analysis        (task, P1, always)
ab-XXXX.5  REVIEW: Requirements         (task, P0, review-gate, assignee=human)
ab-XXXX.6  User Stories                 (task, P2, conditional)
ab-XXXX.7  REVIEW: User Stories         (task, P0, review-gate, assignee=human)
ab-XXXX.8  Workflow Planning            (task, P1, always)
ab-XXXX.9  REVIEW: Workflow Planning    (task, P0, review-gate, assignee=human)
ab-XXXX.10 Application Design           (task, P2, conditional)
ab-XXXX.11 REVIEW: Application Design   (task, P0, review-gate, assignee=human)
ab-XXXX.12 Units Generation             (task, P2, conditional)
ab-XXXX.13 REVIEW: Units Generation     (task, P0, review-gate, assignee=human)
```

### 2.3 Construction Stage Tasks (Children of Construction Epic)

These are created per-unit during Units Generation. For each unit:

```
ab-YYYY.1  [Unit Name]: Functional Design       (task, P2, conditional)
ab-YYYY.2  REVIEW: [Unit] Functional Design      (task, P0, review-gate)
ab-YYYY.3  [Unit Name]: NFR Requirements         (task, P2, conditional)
ab-YYYY.4  REVIEW: [Unit] NFR Requirements       (task, P0, review-gate)
ab-YYYY.5  [Unit Name]: NFR Design               (task, P2, conditional)
ab-YYYY.6  REVIEW: [Unit] NFR Design             (task, P0, review-gate)
ab-YYYY.7  [Unit Name]: Infrastructure Design    (task, P2, conditional)
ab-YYYY.8  REVIEW: [Unit] Infra Design           (task, P0, review-gate)
ab-YYYY.9  [Unit Name]: Code Generation          (task, P1, always)
ab-YYYY.10 REVIEW: [Unit] Code                   (task, P0, review-gate)
```

After all units:

```
ab-YYYY.N  Build and Test                        (task, P1, always)
ab-YYYY.N+1 REVIEW: Build and Test               (task, P0, review-gate)
```

### 2.4 Dependency Chain (Inception Example)

```
Workspace Detection
  └── blocks → Requirements Analysis
                  └── blocks → REVIEW: Requirements (assignee=human)
                                  └── blocks → User Stories (conditional)
                                                  └── blocks → REVIEW: User Stories
                                                                  └── blocks → Workflow Planning
                                                                                  └── blocks → REVIEW: Workflow Planning
                                                                                                  └── blocks → [next stage]
```

When a conditional stage is skipped, the agent closes it as `done` with a note "Skipped - [rationale]" and the review gate is also closed, unblocking the next stage.

---

## 3. Cross-Reference Contract

### 3.1 Beads → Markdown (Issue Notes Field)

Every Beads issue that produces a markdown artifact includes this in its `notes` field:

```
artifact: aidlc-docs/inception/requirements/requirements.md
```

Multiple artifacts:
```
artifact: aidlc-docs/inception/requirements/requirements.md
artifact: aidlc-docs/inception/requirements/requirement-verification-questions.md
```

### 3.2 Markdown → Beads (Document Header)

Every AIDLC markdown artifact includes a metadata comment at the top:

```markdown
<!-- beads-issue: ab-a1b2.4 -->
<!-- beads-review: ab-a1b2.5 -->
# Requirements Document

...content...
```

- `beads-issue` references the stage task that produced this artifact.
- `beads-review` references the review gate issue that must be resolved before proceeding.

### 3.3 Contract Enforcement

The cross-reference convention is enforced by:

1. **Agent rules**: The AIDLC-Beads rule files instruct the agent to always add cross-references when creating artifacts or Beads issues.
2. **bd doctor extension** (future): A custom `bd doctor` check that validates all artifact paths exist and all markdown headers reference valid Beads issues.

---

## 4. Human Interaction Patterns

### 4.1 Review Gates

**Agent creates a review gate:**
```bash
bd create "REVIEW: Requirements Analysis - Awaiting Approval" \
  -t task -p 0 \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md" \
  --labels "type:review-gate,phase:inception" \
  --assignee human
```

**Agent blocks the next stage on the review gate:**
```bash
bd dep add ab-XXXX.5 ab-XXXX.6   # Review blocks User Stories
```

**Human approves:**
```bash
bd update ab-XXXX.5 --status done --notes "Approved. No changes needed."
```

Or with changes requested:
```bash
bd update ab-XXXX.5 --notes "Changes requested: Add security requirements section."
```

### 4.2 Questions (Q&A)

**Agent files a question:**
```bash
bd create "QUESTION: Requirements - Authentication Method" \
  -t message -p 0 --thread ab-XXXX.4 \
  --description "What authentication method should be used?\nA) Username/password\nB) OAuth/SSO\nC) Multi-factor\nD) Other" \
  --labels "type:qa,phase:inception" \
  --assignee human
```

**Human answers:**
```bash
bd update ab-QXXX --notes "Answer: B - OAuth/SSO with Google and GitHub providers"
bd update ab-QXXX --status done
```

### 4.3 Session Continuity

When an agent starts a new session, instead of reading `aidlc-state.md`, it runs:

```bash
bd ready --json
```

This returns all unblocked tasks, immediately telling the agent what to work on next. The agent can also query the full project state:

```bash
bd list --json                    # All issues
bd show ab-XXXX --json            # Inception epic details
bd list --status in_progress --json  # What's currently being worked on
```

---

## 5. State Tracking Migration

### 5.1 What aidlc-state.md Tracked

| State Field | Beads Equivalent |
|---|---|
| Project Type (Greenfield/Brownfield) | Label on Inception epic: `project:greenfield` or `project:brownfield` |
| Current Phase | Derived from which epic has `in_progress` children |
| Current Stage | The issue(s) with `status: in_progress` |
| Stage Progress (checkboxes) | Issue statuses: `done` = checked, `open` = unchecked |
| Workspace Root | Stored in Inception epic `notes` field |
| Execution Plan Summary | Derived from issue graph (which stages are `open` vs closed as "skipped") |

### 5.2 What audit.md Tracked

| Audit Field | Beads Equivalent |
|---|---|
| User inputs | Review gate and Q&A issue updates (timestamped in Beads event log) |
| AI responses | Issue creation and update events |
| Timestamps | Beads event timestamps (automatic) |
| Stage context | Issue labels and parent epic |
| Approval prompts | Review gate issues |
| Approval responses | Review gate status changes with notes |

---

## 6. Conditional Stage Handling

When the AI determines a conditional stage should be skipped:

1. Update the stage issue: `bd update ab-XXXX.6 --status done --notes "SKIPPED: [rationale]"`
2. Close the associated review gate: `bd update ab-XXXX.7 --status done --notes "SKIPPED: Stage was skipped"`
3. The next stage in the dependency chain is automatically unblocked.

When a skipped stage is later re-enabled by the human:

1. Reopen the stage issue: `bd update ab-XXXX.6 --status open`
2. Reopen the review gate: `bd update ab-XXXX.7 --status open`
3. The dependency chain re-blocks downstream stages.

---

## 7. Multi-Agent Coordination

### 7.1 Single Agent (Default)

Agent runs `bd ready --json` and picks the highest-priority unblocked task. Completes it, creates artifacts, files review gate, syncs with `bd sync`.

### 7.2 Multiple Agents (Parallel Units)

During Construction, multiple units can be worked on in parallel:

1. Each agent runs `bd ready --json` to find available work.
2. Agent claims a unit: `bd update ab-YYYY.1 --claim` (sets assignee + in_progress atomically).
3. Agent works on the unit, creates artifacts, files review gates.
4. Agent syncs: `bd sync`.
5. Hash-based IDs prevent collisions even on different branches.

### 7.3 Swarm Mode

For large projects with many units:

1. A coordinator agent creates all unit epics and stage issues.
2. Worker agents each run `bd ready --json --assignee unassigned` to find unclaimed work.
3. Workers claim and complete tasks independently.
4. All workers sync via `bd sync` which handles git-level merging.
5. Human reviews can be batched (review multiple units at once).

---

## 8. File Structure

```
project-root/
├── .beads/                          # Beads database (auto-created by bd init)
│   └── issues.jsonl                 # Issue store
├── aidlc-docs/                      # Markdown artifacts (human-readable)
│   ├── inception/
│   │   ├── requirements/
│   │   │   ├── requirements.md
│   │   │   └── requirement-verification-questions.md
│   │   ├── user-stories/
│   │   │   ├── stories.md
│   │   │   └── personas.md
│   │   ├── application-design/
│   │   │   ├── components.md
│   │   │   └── unit-of-work.md
│   │   └── plans/
│   │       └── execution-plan.md
│   ├── construction/
│   │   ├── {unit-name}/
│   │   │   ├── functional-design.md
│   │   │   ├── nfr-requirements.md
│   │   │   ├── nfr-design.md
│   │   │   └── infrastructure-design.md
│   │   └── build-and-test/
│   │       └── build-instructions.md
│   └── operations/
├── aidlc-beads-rules/               # Agent rules (loaded into agent context)
│   ├── common/
│   │   ├── beads-integration.md
│   │   └── session-continuity-beads.md
│   └── inception/
│       ├── workspace-detection-beads.md
│       ├── requirements-analysis-beads.md
│       └── workflow-planning-beads.md
├── templates/
│   └── artifact-header.md
├── AGENTS.md                        # Top-level agent instructions
└── README.md
```
