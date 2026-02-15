# Cross-Reference Contract

## Purpose

The cross-reference contract ensures traceability between Beads issues (workflow tracking) and markdown artifacts (rich documents). It allows agents to find artifacts from issues and issues from artifacts, maintaining the link between "what is being tracked" and "what was produced."

---

## Direction 1: Beads Issue → Markdown Artifact

### Location

The `notes` field of any Beads issue that produces an artifact.

### Format

```
artifact: <relative-path-from-project-root>
```

Multiple artifacts use one line per artifact:

```
artifact: aidlc-docs/inception/requirements/requirements.md
artifact: aidlc-docs/inception/requirements/requirement-verification-questions.md
```

### Rules

1. The path MUST be relative to the project root.
2. The path MUST use forward slashes (even on Windows).
3. Every stage task that produces a markdown artifact MUST include an `artifact:` line in its notes.
4. Review gate issues SHOULD include an `artifact:` line referencing the document to be reviewed.
5. If a stage produces no artifacts (e.g., Workspace Detection), no `artifact:` line is needed.

### Example

```bash
bd update ab-a1b2.4 --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nartifact: aidlc-docs/inception/requirements/requirement-verification-questions.md\nRequirements generated at standard depth. 12 functional and 5 non-functional requirements identified."
```

---

## Direction 2: Markdown Artifact → Beads Issue

### Location

An HTML comment block at the very top of the markdown file, before the document title.

### Format

```markdown
<!-- beads-issue: ab-XXXX.N -->
<!-- beads-review: ab-XXXX.M -->
# Document Title

...content...
```

### Fields

| Field | Required | Description |
|---|---|---|
| `beads-issue` | YES | The Beads issue ID of the stage task that produced this artifact |
| `beads-review` | YES (if applicable) | The Beads issue ID of the review gate that must approve this artifact |

### Rules

1. The HTML comments MUST be the first lines of the file.
2. `beads-issue` is mandatory for all AIDLC artifacts.
3. `beads-review` is mandatory for all artifacts that go through a review gate.
4. If a document is updated, the beads-issue ID stays the same (it references the producing stage, not a specific version).
5. Agents MUST add these headers when creating new artifacts.
6. Agents MUST NOT remove or change these headers when editing existing artifacts (unless the issue is being re-mapped).

### Example

```markdown
<!-- beads-issue: ab-a1b2.4 -->
<!-- beads-review: ab-a1b2.5 -->
# Requirements Document

## Intent Analysis
- **User Request**: Build a REST API for user management
- **Request Type**: New Feature
...
```

---

## Validation

### Agent-Side Validation

Before completing a stage, the agent SHOULD verify:

1. All markdown artifacts created during the stage have valid `beads-issue` headers.
2. The `notes` field of the Beads issue contains matching `artifact:` paths.
3. All referenced file paths actually exist.

### Future: bd doctor Extension

A custom `bd doctor` check can validate:

1. All issues with `artifact:` lines in notes → referenced files exist on disk.
2. All markdown files with `beads-issue:` headers → referenced Beads issues exist.
3. All review gates with `artifact:` lines → referenced files have matching `beads-review:` headers.

---

## Lifecycle

### When an Artifact is Created

1. Agent creates the markdown file with `beads-issue` and `beads-review` headers.
2. Agent updates the Beads issue notes with `artifact:` path.
3. Agent creates or updates the review gate issue notes with `artifact:` path.

### When an Artifact is Updated

1. Agent edits the markdown file (headers remain unchanged).
2. Agent updates the Beads issue with a note about what changed.
3. If the review gate was already closed, no change needed (the update is tracked by Beads event log).

### When a Stage is Skipped

1. No markdown artifact is created.
2. The Beads issue is closed with `SKIPPED: [rationale]` in notes.
3. No `artifact:` line is added.
4. No cross-reference validation is needed.
