# AIDLC-Beads Agent Instructions

## Overview

This project uses **Beads** (`bd` CLI) as the workflow orchestrator for the AI-DLC (AI-Driven Development Life Cycle). Beads replaces `aidlc-state.md` and `audit.md` for state tracking, while markdown files remain the primary format for rich document artifacts.

## Quick Start

At the beginning of every session:

```bash
bd ready --json
```

This tells you exactly what to work on next. If no issues exist yet, run the initialization workflow (see below).

## Core Rules

### 0. NEVER Skip Workflow Steps Without Explicit User Permission

This is the **highest-priority rule** and overrides all other guidance.

- **DO NOT** skip, omit, or bypass any AIDLC workflow stage -- whether "always-execute" or "conditional" -- without the user's explicit, affirmative permission.
- **DO NOT** mark any stage as `SKIPPED` in Beads without the user first agreeing to skip it.
- **DO NOT** assume a stage is unnecessary based on your own analysis. Always present your recommendation to the user and wait for their decision.
- **DO** present a clear recommendation (with rationale) when you believe a conditional stage should be skipped, then **ask the user** before proceeding.
- **DO** use a Beads Q&A issue or direct chat to request skip permission when in doubt.
- If the user has not explicitly said "skip [stage]", "yes, skip it", or equivalent -- **execute the stage**.

**This applies to:**
- Inception conditional stages (Reverse Engineering, User Stories, Application Design, Units Generation)
- Construction conditional stages (Functional Design, NFR Requirements, NFR Design, Infrastructure Design)
- Any sub-steps within a stage that could be considered optional
- Any future stages added to the workflow

**Violation of this rule is a critical workflow error.**

### 1. Beads Is the Source of Truth for Workflow State

- **DO** use `bd ready --json` to determine what to work on.
- **DO** update Beads issue status as you progress through stages.
- **DO** run `bd sync` after completing work.
- **DO NOT** create or update `aidlc-state.md` -- Beads replaces it.
- **DO NOT** create or update `audit.md` -- Beads event log replaces it.

### 2. Markdown Is the Source of Truth for Artifacts

- **DO** create markdown artifacts in `aidlc-docs/` following the standard AIDLC directory structure.
- **DO** add `beads-issue` and `beads-review` HTML comment headers to every artifact.
- **DO** store artifact paths in the Beads issue `notes` field using `artifact: <path>` format.
- **DO NOT** store long-form content (requirements docs, design docs) inside Beads issue fields.

### 3. Cross-Reference Convention

When creating a markdown artifact:

```markdown
<!-- beads-issue: ab-XXXX.N -->
<!-- beads-review: ab-XXXX.M -->
# Document Title

...content...
```

When updating the Beads issue:

```bash
bd update <issue-id> --notes "artifact: aidlc-docs/path/to/artifact.md"
```

### 4. Review Gates

After completing a stage that requires human review:

1. Create or update the review gate issue (assigned to `human`).
2. Present the standard AIDLC completion message to the user.
3. **STOP** and wait for the human to close the review gate via `bd update <id> --status done`.
4. Do not proceed past a review gate until `bd ready --json` shows the next stage is unblocked.

### 5. Questions

When you need human input during a stage:

1. File a Beads message issue: `bd create "QUESTION: ..." -t message -p 0 --assignee human`
2. Include multiple-choice options in the description (A, B, C, ... with "Other" as last option).
3. The question blocks the current stage until the human answers.

### 6. Session Continuity

When resuming a session:

1. Run `bd ready --json` to find unblocked work.
2. Run `bd list --status in_progress --json` to see what was in progress.
3. Load the relevant markdown artifacts referenced in the issue `notes` fields.
4. Continue where the previous session left off.

### 7. Conditional Stage Skipping (Requires User Permission)

**No stage may be skipped without explicit user permission.** See Core Rule 0.

When the agent's analysis suggests a conditional stage is not needed:

1. **Present a recommendation** to the user explaining why the stage could be skipped, including the rationale.
2. **Ask the user** for explicit permission to skip. Use a Beads Q&A issue or direct chat.
3. **Wait for the user's response.** Do not proceed until the user confirms.
4. **Only after the user explicitly approves skipping**, mark the stage:

```bash
bd update <stage-id> --status done --notes "SKIPPED: [rationale] -- User approved skip."
bd update <review-gate-id> --status done --notes "SKIPPED: Stage was skipped -- User approved."
```

If the user does not approve the skip, **execute the stage normally.**

### 8. Discovered Work

When you discover additional work during any stage, file a Beads issue immediately:

```bash
bd create "Found: [description of discovered work]" -t task -p <priority> \
  --labels "discovered-from:<current-stage>"
```

## AIDLC Phase Rules

The original AIDLC phase rules are in `aidlc-workflows/aidlc-rules/`. The Beads-adapted rules are in `aidlc-beads-rules/`. When executing a stage:

1. Read the Beads-adapted rule file from `aidlc-beads-rules/` for that stage.
2. The adapted rules reference the original AIDLC rules for content guidance and add Beads-specific workflow instructions.
3. Follow the adapted rule -- it includes all Beads integration steps.

## Initialization

If this is a new project (no `.beads/` directory):

1. Run `bd init --prefix ab`
2. Run the initialization steps in `aidlc-beads-rules/inception/workspace-detection-beads.md`
3. This creates the phase epics and the Inception stage dependency chain.

## File Structure

```
aidlc-docs/           # Markdown artifacts (human-readable documents)
aidlc-beads-rules/    # Beads-adapted AIDLC rules (agent instructions)
aidlc-workflows/      # Original AIDLC rules (reference)
docs/design/          # Architecture and design documentation
templates/            # Artifact templates
scripts/              # Setup and utility scripts
.beads/               # Beads database (auto-managed)
```

---

## `bd` CLI Quick Reference

Use this section instead of running `bd <command> --help`. All common AIDLC-Beads operations are documented here.

**Global flags** available on every command: `--json` (JSON output), `--quiet` (errors only), `--verbose` (debug output).

---

### Setup & Initialization

```bash
# Initialize Beads in a new project
bd init --prefix ab

# Configure git role (suppresses warnings)
git config beads.role maintainer

# Health check and auto-fix
bd doctor
bd doctor --fix
bd doctor --fix --yes          # Skip confirmation prompts
bd doctor --deep               # Full graph integrity validation
```

---

### Session Start (What to Work On)

```bash
# Show ready work (open, no blockers) -- primary entry point
bd ready --json

# Show ready work filtered by assignee
bd ready --assignee <name> --json

# Show only unassigned ready work
bd ready --unassigned --json

# Show what is currently in progress
bd list --status in_progress --json

# Show blocked issues
bd blocked --json

# Full project overview
bd list --json
bd list --all --json           # Include closed issues
bd list --pretty               # Tree format with status symbols
```

---

### Creating Issues

```bash
# Create a task
bd create "Title" -t task -p <priority> \
  --description "Description text" \
  --labels "label1,label2" \
  --acceptance "Acceptance criteria"

# Create an epic
bd create "PHASE NAME" -t epic -p 1 \
  --description "Description" \
  --labels "phase:inception"

# Create a Q&A issue (question for human)
bd create "QUESTION: [Stage] - [Topic]" -t message -p 0 \
  --thread <parent-stage-id> \
  --description "Question text\n\nA) Option 1\nB) Option 2\nX) Other" \
  --labels "type:qa,phase:inception" \
  --assignee human

# Create a review gate
bd create "REVIEW: Stage Name - Awaiting Approval" -t task -p 0 \
  --description "Human reviews artifact." \
  --labels "phase:inception,type:review-gate" \
  --assignee human

# Create with notes and artifact reference
bd create "Title" -t task -p 1 \
  --notes "artifact: aidlc-docs/path/to/file.md"

# Create a discovered work issue
bd create "Found: [description]" -t task -p <priority> \
  --labels "discovered-from:<current-stage>"
```

**Issue types**: `task`, `epic`, `bug`, `feature`, `chore`, `decision`, `message`

**Priority levels**: `0` (critical/highest) through `4` (lowest). Default is `2`.

---

### Viewing Issues

```bash
# Show full issue details
bd show <issue-id> --json

# Show issue with children
bd show <issue-id> --children --json

# Show conversation thread (for message issues)
bd show <issue-id> --thread --json

# Show compact one-liner
bd show <issue-id> --short
```

---

### Updating Issues

```bash
# Claim an issue (sets assignee + status=in_progress atomically)
bd update <issue-id> --claim

# Update status
bd update <issue-id> --status open
bd update <issue-id> --status in_progress
bd update <issue-id> --status done

# Update notes (replaces all notes)
bd update <issue-id> --notes "artifact: path/to/file.md\nCompleted: summary"

# Append to existing notes (does not overwrite)
bd update <issue-id> --append-notes "Additional info here"

# Update multiple fields at once
bd update <issue-id> --status done \
  --notes "artifact: aidlc-docs/path.md\nCompleted: stage summary"

# Add or remove labels
bd update <issue-id> --add-label "new-label"
bd update <issue-id> --remove-label "old-label"

# Change assignee
bd update <issue-id> --assignee human
bd update <issue-id> --assignee ""           # Remove assignee

# Change priority
bd update <issue-id> --priority 1

# Mark a stage as skipped (ONLY after user approval -- see Core Rule 0)
bd update <stage-id> --status done --notes "SKIPPED: [rationale] -- User approved skip."
bd update <review-gate-id> --status done --notes "SKIPPED: Stage was skipped -- User approved."
```

---

### Closing & Reopening Issues

```bash
# Close an issue (sets status=closed, records closed_at)
bd close <issue-id>
bd close <issue-id> --reason "Completed successfully"

# Close and show what's unblocked next
bd close <issue-id> --suggest-next

# Reopen a closed issue (clears closed_at, emits Reopened event)
bd reopen <issue-id>
bd reopen <issue-id> --reason "Re-enabled by user request"
```

---

### Dependencies

```bash
# Add a blocking dependency: <blocker> blocks <blocked>
bd dep add <blocked-id> <blocker-id>
# Shorthand: <issue> --blocks <other>
bd dep <blocker-id> --blocks <blocked-id>

# Set parent-child relationship
bd dep add <child-id> <parent-id> --type parent

# Dependency types: blocks (default), tracks, related, parent-child,
#   discovered-from, until, caused-by, validates, relates-to, supersedes

# Remove a dependency
bd dep remove <issue-id> <depends-on-id>

# List dependencies of an issue
bd dep list <issue-id> --json

# Show dependency tree
bd dep tree <issue-id>

# Check for circular dependencies
bd dep cycles
```

---

### Listing & Filtering

```bash
# Filter by status
bd list --status open --json
bd list --status in_progress --json
bd list --status closed --json

# Filter by labels (AND -- must have ALL)
bd list --label "phase:inception" --json
bd list --label "phase:inception,stage:requirements-analysis" --json

# Filter by labels (OR -- must have AT LEAST ONE)
bd list --label-any "type:review-gate,type:qa" --json

# Filter by assignee
bd list --assignee human --json
bd list --no-assignee --json

# Filter by type
bd list --type epic --json
bd list --type message --json

# Filter by parent (show children of an epic)
bd list --parent <epic-id> --json

# Filter by priority
bd list --priority 0 --json              # Critical only

# Filter by title text
bd list --title "Requirements" --json

# Filter by notes content
bd list --notes-contains "artifact:" --json

# Combine filters
bd list --status open --label "phase:inception" --assignee human --json

# Sort and limit
bd list --sort priority --json
bd list --sort created --reverse --json
bd list --limit 0 --json                 # Unlimited results (default is 50)

# Tree view
bd list --pretty
bd list --tree                            # Alias for --pretty
```

---

### Comments

```bash
# List comments on an issue
bd comments <issue-id>
bd comments <issue-id> --json

# Add a comment
bd comments add <issue-id> "Comment text here"

# Add a comment from a file
bd comments add <issue-id> -f notes.txt
```

---

### Sync & Data

```bash
# Export database to JSONL (prep for git commit)
bd sync

# Import from JSONL (after git pull)
bd sync --import

# Show sync state (pending changes, last export, conflicts)
bd sync --status

# Force full export (skip incremental)
bd sync --force

# Full sync: pull -> merge -> export -> commit -> push
bd sync --full

# Resolve sync conflicts
bd sync --resolve               # Use configured strategy
bd sync --resolve --ours        # Keep local
bd sync --resolve --theirs      # Keep remote
```

---

### Troubleshooting

```bash
# Health check
bd doctor
bd doctor --fix                 # Auto-fix with confirmation
bd doctor --fix --yes           # Auto-fix without confirmation
bd doctor --dry-run             # Preview what --fix would do

# Rebuild database from JSONL
bd doctor --fix --source=jsonl

# Check for circular dependencies
bd dep cycles

# Validate data integrity
bd doctor --check=validate
bd doctor --check=validate --fix

# Database info
bd info

# Search issues by text
bd search "keyword"
```

---

### Common AIDLC Workflow Patterns

**Start of session:**
```bash
bd ready --json
bd list --status in_progress --json
```

**Claim and begin a stage:**
```bash
bd update <stage-id> --claim
```

**Complete a stage with artifact:**
```bash
bd update <stage-id> --status done \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nCompleted: Requirements analysis at standard depth."
bd update <review-gate-id> \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nPlease review the requirements document."
bd sync
```

**Ask the user a question:**
```bash
bd create "QUESTION: Requirements - Authentication Method" -t message -p 0 \
  --thread <stage-id> \
  --description "Which authentication approach?\n\nA) OAuth/SSO\nB) Username/Password\nC) API Keys\nX) Other" \
  --labels "type:qa,phase:inception" \
  --assignee human
```

**Check if questions are answered:**
```bash
bd list --label "type:qa" --status open --json
```

**File discovered work:**
```bash
bd create "Found: Need database migration for schema change" -t task -p 2 \
  --labels "discovered-from:requirements-analysis"
```

**Wire a dependency chain:**
```bash
# Stage depends on (is blocked by) a review gate
bd dep add <stage-id> <review-gate-id>
# Review gate depends on its stage
bd dep add <review-gate-id> <stage-id>
# Parent an issue under an epic
bd dep add <issue-id> <epic-id> --type parent
```

**End of session:**
```bash
bd update <current-stage> --append-notes "Session ended. Completed: [summary]. Remaining: [what's left]."
bd sync
```
