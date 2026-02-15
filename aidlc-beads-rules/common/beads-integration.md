# Beads Integration Rules

## Purpose

These rules govern how AI agents integrate Beads (`bd` CLI) with the AIDLC workflow. All agents MUST follow these rules at all times.

---

## Session Start Protocol

Every agent session MUST begin with:

```bash
# 1. Check for existing Beads database
bd ready --json

# 2. If bd ready fails (no database), initialize:
bd init --prefix ab

# 3. Check for in-progress work from a previous session
bd list --status in_progress --json
```

If there are `in_progress` issues, the agent SHOULD resume that work before starting new tasks.

If there are `ready` issues (unblocked, open), the agent SHOULD pick the highest-priority one.

---

## Stage Execution Protocol

### Before Starting a Stage

```bash
# 1. Claim the stage issue
bd update <stage-id> --claim

# 2. Load the stage rule file from aidlc-beads-rules/
# 3. Load any predecessor artifacts referenced in predecessor issue notes
```

### During a Stage

1. Follow the stage-specific rule file instructions.
2. Create markdown artifacts in the correct `aidlc-docs/` subdirectory.
3. Add cross-reference headers to every markdown artifact created.
4. If questions arise for the human, file Q&A issues immediately.
5. If additional work is discovered, file Beads issues immediately.

### After Completing a Stage

```bash
# 1. Update the stage issue with artifact references
bd update <stage-id> --status done --notes "artifact: aidlc-docs/path/to/artifact.md\nCompleted: [brief summary]"

# 2. If the stage has a review gate, ensure it exists and is properly configured
bd show <review-gate-id> --json
# Verify: assignee=human, status=open, notes contain artifact path

# 3. Sync the database
bd sync

# 4. Present the AIDLC completion message to the user (see stage rule file)
# 5. STOP and wait for human approval on the review gate
```

---

## Review Gate Protocol

### Creating a Review Gate

Review gates are created during project initialization (see workspace-detection-beads.md). Agents should NOT create new review gates unless a stage is being dynamically added.

### Handling Review Gate Responses

After a human updates a review gate:

1. Check the notes for feedback: `bd show <review-gate-id> --json`
2. If status is `done` → proceed to next stage.
3. If notes contain change requests but status is NOT `done` → address the changes, update the artifact, and notify the human again.

---

## Q&A Protocol

### Filing a Question

```bash
bd create "QUESTION: [Stage Name] - [Brief Topic]" -t message -p 0 \
  --thread <parent-stage-issue-id> \
  --description "[Question text]\n\nA) [Option 1]\nB) [Option 2]\nC) [Option 3]\nX) Other (please describe)" \
  --labels "type:qa,phase:[current-phase]" \
  --assignee human
```

### Rules for Questions

1. ALWAYS include multiple-choice options (minimum 2 meaningful + Other).
2. ALWAYS include "Other" as the last option.
3. ALWAYS assign to `human`.
4. ALWAYS link to the parent stage via `--thread`.
5. NEVER ask questions in chat -- always use Beads issues.
6. After filing the question, STOP the current stage and wait for the answer.

### Processing Answers

```bash
bd show <question-id> --json
# Read the answer from the notes field
# If answer is "Other", read the human's description
# Continue the stage with the answer incorporated
```

---

## Cross-Reference Protocol

### When Creating a Markdown Artifact

1. Add the HTML comment header:
```markdown
<!-- beads-issue: <stage-issue-id> -->
<!-- beads-review: <review-gate-id> -->
# Document Title
```

2. Update the Beads issue notes:
```bash
bd update <stage-id> --notes "artifact: <relative-path>"
```

3. Update the review gate notes:
```bash
bd update <review-gate-id> --notes "artifact: <relative-path>"
```

### Validation

Before marking a stage as done, verify:
- Every artifact has a `beads-issue` header.
- Every artifact with a review gate has a `beads-review` header.
- The Beads issue notes contain matching `artifact:` lines.

---

## Conditional Stage Handling

### Skipping a Stage

When analysis determines a conditional stage is not needed:

```bash
bd update <stage-id> --status done --notes "SKIPPED: [detailed rationale]"
bd update <review-gate-id> --status done --notes "SKIPPED: Stage was skipped - [rationale]"
```

### Re-enabling a Skipped Stage

If a human reopens a stage (status changed back to `open`):

1. The agent should detect this via `bd ready --json`.
2. Execute the stage normally following its rule file.
3. Create artifacts and review gates as if the stage was never skipped.

---

## Error Handling

### Beads Command Failures

If a `bd` command fails:
1. Retry once after 2 seconds.
2. If still failing, run `bd doctor --fix`.
3. If still failing, file a discovered work issue and proceed with the next available task.

### Missing Artifacts

If a predecessor's artifact file is missing:
1. Check the Beads issue for the artifact path.
2. If the path is wrong, check `aidlc-docs/` for the actual file.
3. If the file truly does not exist, file a blocking issue and notify the human.

### Merge Conflicts

If `bd sync` encounters conflicts:
1. For JSONL conflicts: `git checkout --theirs .beads/issues.jsonl` then `bd import`.
2. For markdown conflicts: resolve by keeping both changes and reconciling content.
3. Run `bd doctor --fix` after resolution.
