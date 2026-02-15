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

### 7. Conditional Stage Skipping

When a conditional stage should be skipped:

```bash
bd update <stage-id> --status done --notes "SKIPPED: [rationale]"
bd update <review-gate-id> --status done --notes "SKIPPED: Stage was skipped"
```

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
