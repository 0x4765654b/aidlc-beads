# Workflow Planning (Beads-Adapted)

**Purpose**: Determine which stages to execute and create the execution plan.

**Reference**: See `aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/inception/workflow-planning.md` for the original stage definition.

**Always Execute**: This stage always runs after requirements are approved.

---

## Prerequisites

Check with Beads:

```bash
bd show <requirements-review-gate-id> --json
# Verify status: done (human approved requirements)

# If user stories were executed:
bd show <user-stories-review-gate-id> --json
# Verify status: done
```

## Step 1: Claim the Stage

```bash
bd update <workflow-planning-id> --claim
```

## Step 2: Load All Prior Context

Load artifacts from all completed predecessor stages:

```bash
# Load requirements
bd show <requirements-analysis-id> --json
# Read artifact files from notes

# Load reverse engineering (if brownfield)
bd show <reverse-engineering-id> --json
# Read artifact files from notes

# Load user stories (if executed)
bd show <user-stories-id> --json
# Read artifact files from notes
```

## Step 3: Detailed Scope and Impact Analysis

Follow the original AIDLC workflow planning analysis:

1. **Transformation Scope Detection** (brownfield only)
2. **Change Impact Assessment**
3. **Component Relationship Mapping** (brownfield only)
4. **Risk Assessment**

## Step 4: Phase Determination

For each conditional stage, determine EXECUTE or SKIP:

| Stage | Decision Criteria |
|---|---|
| User Stories | Already executed? Multiple personas? UX impact? |
| Application Design | New components needed? Service layer design? |
| Units Generation | Multiple packages? Complex decomposition? |
| Functional Design (per-unit) | Complex business logic? |
| NFR Requirements (per-unit) | Performance/security/scalability concerns? |
| NFR Design (per-unit) | NFR patterns needed? |
| Infrastructure Design (per-unit) | Cloud infrastructure mapping? |

## Step 5: Wire Conditional Stage Dependencies in Beads

This is the critical Beads-specific step. Based on the phase determination, wire the dependency chain.

### For Stages Marked EXECUTE

Wire them into the dependency chain:

```bash
# Example: User Stories is EXECUTE
# User Stories is blocked by Requirements Review
bd dep add <user-stories-id> <requirements-review-gate-id> --type blocks

# User Stories Review blocks Workflow Planning
# (Workflow Planning was previously blocked by Requirements Review - update the chain)
bd dep add <workflow-planning-id> <user-stories-review-gate-id> --type blocks
```

### For Stages Marked SKIP

Close them immediately with rationale:

```bash
# Example: User Stories is SKIP
bd update <user-stories-id> --status done \
  --notes "SKIPPED: Internal refactoring project with no user-facing changes. No personas or acceptance criteria needed."
bd update <user-stories-review-gate-id> --status done \
  --notes "SKIPPED: User Stories stage was skipped."
```

### Wire Construction Stage Dependencies

For stages that WILL execute in Construction:

```bash
# Example: Functional Design executes, then Code Generation
# These get wired when units are created, but set up the skeleton:
bd dep add <first-construction-stage> <workflow-planning-review-gate-id> --type blocks
```

## Step 6: Generate Execution Plan Document

Create `aidlc-docs/inception/plans/execution-plan.md`:

```markdown
<!-- beads-issue: <workflow-planning-id> -->
<!-- beads-review: <workflow-planning-review-gate-id> -->
# Execution Plan

## Analysis Summary

### Change Impact Assessment
- **User-facing changes**: [Yes/No - Description]
- **Structural changes**: [Yes/No - Description]
- **Data model changes**: [Yes/No - Description]
- **API changes**: [Yes/No - Description]
- **NFR impact**: [Yes/No - Description]

### Risk Assessment
- **Risk Level**: [Low/Medium/High/Critical]
- **Rollback Complexity**: [Easy/Moderate/Difficult]

## Stages to Execute

### INCEPTION PHASE
- [x] Workspace Detection (COMPLETED)
- [x] Reverse Engineering ([COMPLETED/SKIPPED])
- [x] Requirements Analysis (COMPLETED)
- [x] User Stories ([COMPLETED/SKIPPED - rationale])
- [x] Workflow Planning (IN PROGRESS)
- [ ] Application Design - [EXECUTE/SKIP: rationale]
- [ ] Units Generation - [EXECUTE/SKIP: rationale]

### CONSTRUCTION PHASE
- [ ] Functional Design - [EXECUTE/SKIP: rationale]
- [ ] NFR Requirements - [EXECUTE/SKIP: rationale]
- [ ] NFR Design - [EXECUTE/SKIP: rationale]
- [ ] Infrastructure Design - [EXECUTE/SKIP: rationale]
- [ ] Code Generation - EXECUTE (ALWAYS)
- [ ] Build and Test - EXECUTE (ALWAYS)

### OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Beads Dependency Chain

The following dependency chain is active in Beads:
[List the actual issue IDs and their blocking relationships]

## Estimated Timeline
- **Total Stages**: [count]
- **Estimated Duration**: [estimate]
```

## Step 7: Update Beads Issue

```bash
bd update <workflow-planning-id> --status done \
  --notes "artifact: aidlc-docs/inception/plans/execution-plan.md\nStages to execute: [list]. Stages skipped: [list]. Risk level: [level]."

bd update <workflow-planning-review-gate-id> \
  --notes "artifact: aidlc-docs/inception/plans/execution-plan.md\nPlease review the execution plan and stage selections."
```

## Step 8: Sync and Present Completion

```bash
bd sync
```

Present the completion message:

```markdown
# Workflow Planning Complete

Execution plan created based on requirements analysis:

**Stages to Execute:**
- [Stage name] - Rationale: [why]
- ...

**Stages to Skip:**
- [Stage name] - Rationale: [why]
- ...

**Risk Level**: [level]
**Estimated Timeline**: [estimate]

> **REVIEW REQUIRED:**
> Please examine the execution plan at: `aidlc-docs/inception/plans/execution-plan.md`

> **WHAT'S NEXT?**
>
> **You may:**
>
> **Request Changes** - Ask for modifications to the execution plan
> **Add Skipped Stages** - Re-enable stages currently marked as SKIP
> **Approve & Continue** - Approve plan and proceed to **[Next Stage]**
>
> To approve: `bd update <workflow-planning-review-gate-id> --status done --notes "Approved."`
```

## Step 9: Wait for Human Approval

**STOP** here. Do not proceed until the review gate is closed.

When the review gate is closed:
- If notes contain changes → update execution plan, re-wire dependencies, re-present.
- If human wants to re-enable skipped stages → reopen those stages and their review gates, re-wire dependencies.
- If approved → proceed to the next stage (determined by `bd ready --json`).
