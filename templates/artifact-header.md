# Artifact Header Template

Every AIDLC markdown artifact MUST include this header at the top of the file.

## Template

```markdown
<!-- beads-issue: ab-XXXX.N -->
<!-- beads-review: ab-XXXX.M -->
# [Document Title]

...content...
```

## Field Descriptions

- `beads-issue`: The Beads issue ID of the stage task that produced this artifact.
- `beads-review`: The Beads issue ID of the review gate that must approve this artifact.

## Examples

### Requirements Document

```markdown
<!-- beads-issue: ab-a1b2.4 -->
<!-- beads-review: ab-a1b2.5 -->
# Requirements Document

## Intent Analysis
- **User Request**: Build a REST API for user management
...
```

### User Stories

```markdown
<!-- beads-issue: ab-a1b2.6 -->
<!-- beads-review: ab-a1b2.7 -->
# User Stories

## Personas
...

## Stories
...
```

### Execution Plan

```markdown
<!-- beads-issue: ab-a1b2.8 -->
<!-- beads-review: ab-a1b2.9 -->
# Execution Plan

## Analysis Summary
...
```

### Question File

```markdown
<!-- beads-issue: ab-a1b2.4 -->
<!-- beads-review: ab-a1b2.5 -->
# Requirements Clarification Questions

Please answer the following questions...

## Question 1
...
```

## Rules

1. The HTML comments MUST be the first lines of the file (before the title).
2. `beads-issue` is MANDATORY for all AIDLC artifacts.
3. `beads-review` is MANDATORY for all artifacts that have a review gate.
4. Use the actual Beads issue IDs assigned during project initialization.
5. These headers should NOT be removed or changed after creation.
