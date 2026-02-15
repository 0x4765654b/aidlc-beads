# Human Interaction Guide for AIDLC-Beads

## Overview

In the AIDLC-Beads workflow, humans interact with two systems:

1. **Markdown files** for reviewing rich document artifacts (requirements, designs, stories).
2. **Beads (`bd` CLI)** for approving stages, answering questions, and checking project status.

This guide covers all human interaction patterns.

---

## 1. Checking Project Status

### See what needs your attention
```bash
bd ready --json
```
Returns all unblocked tasks. Look for items with `assignee: human` -- those are waiting for you.

### See overall progress
```bash
bd list --json
```
Shows all issues with their statuses. Issues marked `done` are completed stages.

### See details of a specific stage
```bash
bd show ab-XXXX.4 --json
```
Shows the issue details, including artifact paths in the notes field.

---

## 2. Reviewing and Approving Stages

### The Review Workflow

1. **Agent completes a stage** and creates a review gate issue assigned to `human`.
2. **Agent notifies you** with the review gate ID and the artifact path.
3. **You review** the markdown artifact at the specified path.
4. **You approve or request changes** via Beads.

### Approving a Stage
```bash
bd update ab-XXXX.5 --status done --notes "Approved. Requirements look good."
```

### Requesting Changes
```bash
bd update ab-XXXX.5 --notes "Changes needed: 1) Add rate limiting requirements. 2) Clarify authentication flow for API keys."
```
Do NOT close the issue when requesting changes. The agent will see the notes, make changes, and notify you again.

### Approving After Changes
```bash
bd update ab-XXXX.5 --status done --notes "Changes addressed. Approved."
```

---

## 3. Answering Questions

### The Q&A Workflow

1. **Agent files a question** as a Beads message issue with multiple-choice options.
2. **You view the question**: `bd show ab-QXXX --json`
3. **You answer** by updating the issue.
4. The agent picks up your answer in its next session.

### Answering a Question
```bash
bd show ab-QXXX --json
# Read the question in the description field

bd update ab-QXXX --status done --notes "Answer: B - OAuth/SSO with Google and GitHub"
```

### If None of the Options Fit
```bash
bd update ab-QXXX --status done --notes "Answer: Other - We need certificate-based mTLS authentication for service-to-service calls"
```

---

## 4. Overriding Stage Decisions

### Re-enabling a Skipped Stage

If the agent skipped a conditional stage and you want it executed:

```bash
# Reopen the stage
bd update ab-XXXX.6 --status open --notes "Re-enabled by human. User stories needed for stakeholder alignment."

# Reopen the review gate
bd update ab-XXXX.7 --status open
```

### Skipping a Stage the Agent Planned to Execute

```bash
bd update ab-XXXX.6 --status done --notes "SKIPPED: Human override. Not needed for this project."
bd update ab-XXXX.7 --status done --notes "SKIPPED: Stage skipped by human."
```

---

## 5. Adding Work Items

You can file Beads issues directly:

```bash
# File a bug you noticed
bd create "Fix: Login page CSS broken on mobile" -t task -p 1 \
  --labels "phase:construction,discovered-by:human"

# File a feature request
bd create "Add: Export requirements to PDF" -t task -p 3 \
  --labels "enhancement"
```

---

## 6. Quick Reference

| Action | Command |
|---|---|
| What needs my attention? | `bd ready --json` |
| See all issues | `bd list --json` |
| View an issue | `bd show <id> --json` |
| Approve a review | `bd update <id> --status done --notes "Approved."` |
| Request changes | `bd update <id> --notes "Changes: ..."` |
| Answer a question | `bd update <id> --status done --notes "Answer: B"` |
| Re-enable skipped stage | `bd update <id> --status open` |
| File a new issue | `bd create "Title" -t task -p <priority>` |
| Sync database | `bd sync` |

---

## 7. Tips

- **Run `bd sync` after making changes** to push your updates to git so agents can see them.
- **Use `bd ready --json` frequently** to see what's waiting for you.
- **You can batch approvals** -- approve multiple review gates at once if you've reviewed all the artifacts.
- **Review gates block progress** -- agents cannot proceed past a review gate until you approve it.
- **Questions block the parent stage** -- answer promptly to keep agents productive.
