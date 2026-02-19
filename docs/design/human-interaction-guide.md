# Human Interaction Guide for AIDLC-Beads

## Overview

In the AIDLC-Beads workflow, humans interact with three systems:

1. **Outline Wiki** (web browser) for reviewing and editing document artifacts in a familiar WYSIWYG interface.
2. **Beads (`bd` CLI)** for approving stages, answering questions, and checking project status.
3. **Markdown files** in `aidlc-docs/` as the canonical source of truth (managed by agents; humans use Outline instead of editing these directly).

This guide covers all human interaction patterns, with a focus on the Outline-based review workflow for non-technical users.

---

## 1. Reviewing Documents in Outline (Recommended for Non-Technical Users)

### What is Outline?

Outline is a web-based wiki with a WYSIWYG editor -- it renders markdown as formatted text that looks like a word processor. You can read, comment on, and edit documents without ever seeing raw markdown or using the command line.

### Accessing Outline

Open your web browser and navigate to:

```
http://localhost:3000
```

(Or the URL your team has configured for Outline.)

### Reviewing a Document

1. Log in to Outline.
2. Navigate to the **AIDLC Documents** collection.
3. Find the document the agent has asked you to review (check your notification or the review gate message for the document name).
4. Read through the document -- it will be formatted with headings, lists, tables, and other rich content.
5. If you have feedback:
   - **Use Outline's comment feature** to leave inline comments on specific sections.
   - **Edit the document directly** using the WYSIWYG editor if you want to make changes yourself.

### After Reviewing

Once you have reviewed the document, approve or request changes using Beads (see Section 2 below).

---

## 2. Approving and Managing Workflow (via Beads CLI)

### Checking What Needs Your Attention

```bash
bd ready --json
```

Returns all unblocked tasks. Look for items with `assignee: human` -- those are waiting for you.

### Seeing Overall Progress

```bash
bd list --json
```

Shows all issues with their statuses. Issues marked `done` are completed stages.

### Seeing Details of a Specific Stage

```bash
bd show ab-XXXX.4 --json
```

Shows the issue details, including artifact paths in the notes field.

---

## 3. The Review Workflow

### How It Works

1. **Agent completes a stage** and creates a review gate issue assigned to `human`.
2. **Agent pushes artifacts to Outline** so they appear in the web UI.
3. **Agent notifies you** with the review gate ID and the document name.
4. **You review** the document in Outline (see Section 1 above).
5. **You approve or request changes** via Beads (see below).

### Approving a Stage

```bash
bd update ab-XXXX.5 --status done --notes "Approved. Requirements look good."
```

### Requesting Changes

```bash
bd update ab-XXXX.5 --notes "Changes needed: 1) Add rate limiting requirements. 2) Clarify authentication flow for API keys."
```

Do NOT close the issue when requesting changes. The agent will see the notes, make changes, push updated documents to Outline, and notify you again.

### Approving After Changes

```bash
bd update ab-XXXX.5 --status done --notes "Changes addressed. Approved."
```

### Editing Documents Yourself

If you prefer to make edits rather than describing changes:

1. Edit the document directly in Outline's WYSIWYG editor.
2. The agent will pull your edits before continuing: `python scripts/sync-outline.py pull`
3. Approve the review gate so the agent can proceed.

---

## 4. Answering Questions

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

## 5. Overriding Stage Decisions

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

## 6. Adding Work Items

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

## 7. Quick Reference

| Action | Method |
|---|---|
| Read a document | Open Outline in browser > AIDLC Documents collection |
| Comment on a document | Use Outline's inline comment feature |
| Edit a document | Use Outline's WYSIWYG editor |
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

## 8. Tips

- **Review documents in Outline** instead of opening raw markdown files -- it is much easier to read.
- **Use Outline comments** for specific feedback on sections -- the agent or a technical team member will address them.
- **Run `bd sync` after making changes** to push your updates to git so agents can see them.
- **Use `bd ready --json` frequently** to see what is waiting for you.
- **You can batch approvals** -- approve multiple review gates at once if you have reviewed all the artifacts.
- **Review gates block progress** -- agents cannot proceed past a review gate until you approve it.
- **Questions block the parent stage** -- answer promptly to keep agents productive.

---

## 9. Outline Setup (One-Time)

If Outline is not yet running for your project, a technical team member needs to set it up:

1. Navigate to the `outline/` directory in the project.
2. Copy `outline/.env.example` to `outline/.env` and configure it.
3. Run `docker compose up -d` to start Outline.
4. Create an API key in Outline settings and add it to the `.env` file.
5. Run `python scripts/sync-outline.py init` to push existing documents.

See `docs/design/outline-integration.md` for detailed setup instructions.
