# Workspace Detection (Beads-Adapted)

**Purpose**: Determine workspace state, initialize Beads, and create the AIDLC issue graph.

**Reference**: See `aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/inception/workspace-detection.md` for the original stage definition.

---

## Step 1: Initialize Beads (if not already initialized)

```bash
# Check if Beads is already initialized
bd list --json

# If not initialized:
bd init --prefix ab
```

## Step 2: Check for Existing AIDLC Beads Project

```bash
bd list --labels "phase:inception" --json
```

- **If issues exist with `phase:inception`**: This is a resume. Follow `session-continuity-beads.md`.
- **If no AIDLC issues exist**: This is a new project. Continue with Step 3.

## Step 3: Scan Workspace (Same as Original AIDLC)

Follow the original workspace detection steps:

1. Scan workspace for source code files.
2. Check for build files (pom.xml, package.json, build.gradle, etc.).
3. Look for project structure indicators.
4. Identify workspace root directory.

Record the findings:

| Finding | Value |
|---|---|
| Existing Code | Yes/No |
| Programming Languages | [list] |
| Build System | [name] |
| Project Structure | Monolith/Microservices/Library/Empty |
| Workspace Root | [absolute path] |

## Step 4: Create Phase Epics

```bash
# Create the three phase epics
bd create "INCEPTION PHASE" -t epic -p 1 \
  --description "Planning and architecture. Determines WHAT to build and WHY." \
  --labels "phase:inception,project:[greenfield|brownfield]" \
  --notes "workspace-root: [absolute path]" \
  --acceptance "All inception stages completed or intentionally skipped. Human approval at each gate."

bd create "CONSTRUCTION PHASE" -t epic -p 1 \
  --description "Design, implementation, build and test. Determines HOW to build it." \
  --labels "phase:construction" \
  --acceptance "All units designed, implemented, built, and tested. Human approval at each gate."

bd create "OPERATIONS PHASE" -t epic -p 3 \
  --description "Deployment and monitoring. Placeholder for future workflows." \
  --labels "phase:operations" \
  --acceptance "Deployment and monitoring configured."
```

Record the epic IDs from the output (e.g., `ab-a1b2`, `ab-c3d4`, `ab-e5f6`).

## Step 5: Create Inception Stage Issues and Review Gates

Create all inception stages as children of the Inception epic. Use the hierarchical ID format.

### Always-Execute Stages

```bash
# Workspace Detection (this stage - mark as in_progress)
bd create "Workspace Detection" -t task -p 1 \
  --description "Analyze workspace state, detect project type." \
  --labels "phase:inception,stage:workspace-detection,always" \
  --acceptance "Workspace state recorded. Project type determined."
bd update <workspace-detection-id> --claim
# Parent it to Inception epic
bd dep add <workspace-detection-id> <inception-epic-id> --type parent

# Requirements Analysis
bd create "Requirements Analysis" -t task -p 1 \
  --description "Gather and validate requirements. Generate clarifying questions. Produce requirements document." \
  --labels "phase:inception,stage:requirements-analysis,always" \
  --acceptance "Requirements document generated. All questions answered. Human review approved."
bd dep add <requirements-id> <inception-epic-id> --type parent
bd dep add <requirements-id> <workspace-detection-id> --type blocks

# Requirements Review Gate
bd create "REVIEW: Requirements Analysis - Awaiting Approval" -t task -p 0 \
  --description "Human reviews requirements document and approves." \
  --labels "phase:inception,type:review-gate" \
  --assignee human \
  --acceptance "Human approved requirements."
bd dep add <req-review-id> <inception-epic-id> --type parent
bd dep add <req-review-id> <requirements-id> --type blocks

# Workflow Planning
bd create "Workflow Planning" -t task -p 1 \
  --description "Determine which stages to execute. Create execution plan." \
  --labels "phase:inception,stage:workflow-planning,always" \
  --acceptance "Execution plan generated. Stages marked execute/skip."
bd dep add <workflow-planning-id> <inception-epic-id> --type parent
bd dep add <workflow-planning-id> <req-review-id> --type blocks

# Workflow Planning Review Gate
bd create "REVIEW: Workflow Planning - Awaiting Approval" -t task -p 0 \
  --description "Human reviews execution plan and approves stage selections." \
  --labels "phase:inception,type:review-gate" \
  --assignee human \
  --acceptance "Human approved execution plan."
bd dep add <wp-review-id> <inception-epic-id> --type parent
bd dep add <wp-review-id> <workflow-planning-id> --type blocks
```

### Conditional Stages

Create these but DO NOT set dependencies to downstream stages yet. Dependencies for conditional stages are wired during Workflow Planning when the AI determines which stages to execute or skip.

```bash
# Reverse Engineering (brownfield only)
bd create "Reverse Engineering" -t task -p 2 \
  --description "Analyze existing codebase. Document architecture, components, tech stack." \
  --labels "phase:inception,stage:reverse-engineering,conditional"
bd dep add <re-id> <inception-epic-id> --type parent

bd create "REVIEW: Reverse Engineering - Awaiting Approval" -t task -p 0 \
  --description "Human reviews codebase analysis." \
  --labels "phase:inception,type:review-gate" \
  --assignee human
bd dep add <re-review-id> <inception-epic-id> --type parent
bd dep add <re-review-id> <re-id> --type blocks

# User Stories
bd create "User Stories" -t task -p 2 \
  --description "Create user personas and stories with acceptance criteria." \
  --labels "phase:inception,stage:user-stories,conditional"
bd dep add <us-id> <inception-epic-id> --type parent

bd create "REVIEW: User Stories - Awaiting Approval" -t task -p 0 \
  --description "Human reviews user stories and personas." \
  --labels "phase:inception,type:review-gate" \
  --assignee human
bd dep add <us-review-id> <inception-epic-id> --type parent
bd dep add <us-review-id> <us-id> --type blocks

# Application Design
bd create "Application Design" -t task -p 2 \
  --description "High-level component identification, methods, business rules, service design." \
  --labels "phase:inception,stage:application-design,conditional"
bd dep add <ad-id> <inception-epic-id> --type parent

bd create "REVIEW: Application Design - Awaiting Approval" -t task -p 0 \
  --description "Human reviews application design artifacts." \
  --labels "phase:inception,type:review-gate" \
  --assignee human
bd dep add <ad-review-id> <inception-epic-id> --type parent
bd dep add <ad-review-id> <ad-id> --type blocks

# Units Generation
bd create "Units Generation" -t task -p 2 \
  --description "Decompose system into units of work with boundaries and dependencies." \
  --labels "phase:inception,stage:units-generation,conditional"
bd dep add <ug-id> <inception-epic-id> --type parent

bd create "REVIEW: Units Generation - Awaiting Approval" -t task -p 0 \
  --description "Human reviews unit decomposition." \
  --labels "phase:inception,type:review-gate" \
  --assignee human
bd dep add <ug-review-id> <inception-epic-id> --type parent
bd dep add <ug-review-id> <ug-id> --type blocks
```

## Step 6: Wire Brownfield Dependencies (if applicable)

If the project is brownfield:

```bash
# Reverse Engineering goes between Workspace Detection and Requirements
bd dep add <re-id> <workspace-detection-id> --type blocks
bd dep add <requirements-id> <re-review-id> --type blocks
# Remove the direct Workspace Detection → Requirements block
# (Requirements is now blocked by RE Review instead)
```

If greenfield, skip this step. Requirements is already blocked by Workspace Detection.

## Step 7: Complete Workspace Detection

```bash
bd update <workspace-detection-id> --status done \
  --notes "Project type: [greenfield|brownfield]. Languages: [list]. Build system: [name]. Workspace root: [path]."
```

## Step 8: Present Completion Message

**For Greenfield:**
```markdown
# Workspace Detection Complete

Workspace analysis findings:
- **Project Type**: Greenfield project
- **Beads initialized**: Issue prefix `ab-`
- **Inception stages created**: [count] stages with review gates
- **Next Step**: Proceeding to **Requirements Analysis**...
```

**For Brownfield:**
```markdown
# Workspace Detection Complete

Workspace analysis findings:
- **Project Type**: Brownfield project
- **Languages**: [list]
- **Build System**: [name]
- **Beads initialized**: Issue prefix `ab-`
- **Inception stages created**: [count] stages with review gates
- **Next Step**: Proceeding to **Reverse Engineering**...
```

## Step 9: Automatically Proceed

No user approval required for Workspace Detection. Automatically proceed to the next stage (Requirements Analysis for greenfield, Reverse Engineering for brownfield).
