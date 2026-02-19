# Session Continuity with Beads

## Purpose

Replaces the `aidlc-state.md`-based session continuity from the original AIDLC workflow. Beads provides persistent state across agent sessions without needing to parse markdown state files.

---

## Session Resume Protocol

### Step 1: Query Beads for Current State

```bash
# What is ready for work?
bd ready --json

# What is currently in progress?
bd list --status in_progress --json

# Full project state
bd list --json

# Pull any edits humans made in Outline since last session
python scripts/sync-outline.py pull
```

**Note:** The Outline pull may fail if Outline is not configured. This is non-fatal -- skip and continue.

### Step 2: Determine Project Context

From the Beads issue list, derive:

| Context Item | How to Derive |
|---|---|
| Project Type | Look for `project:greenfield` or `project:brownfield` label on the Inception epic |
| Current Phase | The phase epic with `in_progress` or `open` children |
| Current Stage | Issues with `status: in_progress` |
| Completed Stages | Issues with `status: done` (and NOT `SKIPPED` in notes) |
| Skipped Stages | Issues with `status: done` AND `SKIPPED` in notes |
| Pending Stages | Issues with `status: open` |
| Blocked Stages | Issues blocked by open review gates or Q&A |
| Human Actions Needed | Issues with `assignee: human` and `status: open` |

### Step 3: Load Previous Artifacts

For each completed stage, read the artifact paths from the issue `notes` field:

```bash
bd show <completed-stage-id> --json
# Extract "artifact:" lines from notes
# Read each referenced markdown file
```

**Smart Context Loading by Stage** (same as original AIDLC):

- **Early Stages** (Workspace Detection, Reverse Engineering): Load workspace analysis only.
- **Requirements/Stories**: Load reverse engineering + requirements artifacts.
- **Design Stages**: Load requirements + stories + architecture + design artifacts.
- **Code Stages**: Load ALL artifacts + existing code files.

### Step 4: Present Welcome Back Message

```markdown
**Welcome back! Resuming AIDLC project via Beads.**

**Project State** (from `bd list`):
- **Phase**: [INCEPTION/CONSTRUCTION/OPERATIONS]
- **Completed**: [List of done stages]
- **In Progress**: [List of in_progress stages, if any]
- **Next Up**: [List of ready stages from bd ready]
- **Waiting on Human**: [List of review gates/questions assigned to human]

**Loaded Artifacts**:
- [List of artifacts loaded from completed stages]

**What would you like to work on?**

A) Continue with [next ready stage from bd ready]
B) Review a completed stage
C) Check pending human actions
```

---

## Comparison with Original Session Continuity

| Original (aidlc-state.md) | Beads-Based |
|---|---|
| Parse markdown state file | `bd ready --json` and `bd list --json` |
| Checkbox-based progress | Issue status (done/open/in_progress) |
| Manual state updates | Automatic via `bd update` |
| Single file, single writer | Distributed, multi-agent safe |
| No dependency tracking | Full dependency graph |
| No blocking mechanism | Review gates and Q&A block progress |
| Artifact paths hardcoded in state | Artifact paths in issue notes (cross-reference) |

---

## Session End Protocol

Before ending a session:

1. Ensure current work is saved (artifacts written, code committed).
2. Update Beads issues to reflect current state:
   - Mark completed stages as `done`.
   - Leave in-progress work as `in_progress` with a note about where you stopped.
3. Push any new or updated artifacts to Outline for human review.
4. Run `bd sync` to push all Beads changes to git.
5. File any discovered work as new Beads issues.

```bash
# Update current work status
bd update <current-stage> --notes "Session ended. Completed: [summary]. Remaining: [what's left]."

# Push artifacts to Outline
python scripts/sync-outline.py push

# Sync to git
bd sync
```
