# Outline Integration Design

## Overview

This document describes how [Outline Wiki](https://www.getoutline.com/) integrates with the AIDLC-Beads workflow to provide non-technical users with a web-based WYSIWYG interface for reviewing, commenting on, and editing AIDLC artifacts.

**Architecture Summary:**

- **Git** remains the source of truth for all markdown artifacts in `aidlc-docs/`.
- **Outline** provides a web UI for human reviewers who cannot use CLI or raw markdown.
- **sync-outline.py** bridges the two systems, pushing local changes to Outline and pulling edits back.
- **Beads** continues to manage workflow state, review gates, and approval tracking.

---

## Architecture

```
┌──────────────────────┐     ┌───────────────────────┐
│    AI Agents          │     │   Non-Technical Users  │
│  (read/write files)  │     │   (web browser)        │
└──────────┬───────────┘     └───────────┬────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐     ┌───────────────────────┐
│  Git Repository       │     │  Outline Wiki          │
│  aidlc-docs/*.md     │◄───►│  WYSIWYG Editor       │
│  .beads/ (workflow)  │     │  Comments & Reviews    │
└──────────────────────┘     └───────────────────────┘
           ▲                             ▲
           └──────── sync-outline.py ────┘
```

### Data Flow

1. **Agent produces artifact** -- writes markdown to `aidlc-docs/`, updates Beads issue.
2. **Agent (or CI) pushes to Outline** -- `python scripts/sync-outline.py push`
3. **Human reviews in Outline** -- reads rendered document, adds comments, makes edits.
4. **Agent (or CI) pulls from Outline** -- `python scripts/sync-outline.py pull`
5. **Human approves in Beads** -- `bd update <review-gate-id> --status done`

### What Each System Owns

| Concern | System |
|---|---|
| Workflow state, dependencies, status | Beads |
| Rich document content | Git (markdown files) |
| Human-friendly document viewing/editing | Outline |
| Review approval/rejection | Beads (review gate issues) |
| Comments on document content | Outline |
| Cross-reference traceability | Beads notes + markdown headers |

---

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- An AIDLC-Beads project with `aidlc-docs/` directory

### Step 1: Configure Outline

```bash
# Navigate to the outline/ directory
cd outline/

# Create .env from template
cp .env.example .env

# Generate required secrets
# On Linux/macOS:
openssl rand -hex 32   # Copy output to SECRET_KEY
openssl rand -hex 32   # Copy output to UTILS_SECRET

# On Windows (PowerShell):
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
```

Edit `outline/.env` and configure:
1. `SECRET_KEY` and `UTILS_SECRET` (generated above)
2. At least one authentication provider (Google, Slack, Azure AD, or OIDC)
3. `URL` to match where Outline will be accessible

### Step 2: Start Outline

```bash
cd outline/
docker compose up -d
```

Wait for all services to be healthy:

```bash
docker compose ps
```

Outline will be available at `http://localhost:3000` (or your configured URL).

### Step 3: Create an API Key

1. Log in to Outline at `http://localhost:3000`
2. Go to **Settings** > **API**
3. Create a new API key
4. Add it to `outline/.env` as `OUTLINE_API_KEY`

### Step 4: Install Python Dependencies

```bash
pip install -r scripts/requirements.txt
```

### Step 5: Initialize the Sync

```bash
python scripts/sync-outline.py init
```

This creates an "AIDLC Documents" collection in Outline and pushes all existing artifacts from `aidlc-docs/`.

---

## Usage

### Pushing Local Changes to Outline

After an agent produces or updates artifacts:

```bash
python scripts/sync-outline.py push
```

### Pulling Edits from Outline to Git

After a human edits documents in Outline:

```bash
python scripts/sync-outline.py pull
```

### Full Bidirectional Sync

```bash
python scripts/sync-outline.py sync
```

### Checking Sync Status

```bash
python scripts/sync-outline.py status
```

---

## Integration with Beads Workflow

### Agent Workflow (Updated)

When an agent completes a stage:

1. Create the markdown artifact in `aidlc-docs/` (unchanged).
2. Update Beads issue with artifact path (unchanged).
3. **NEW**: Push the artifact to Outline: `python scripts/sync-outline.py push`
4. Update the review gate issue with a note pointing to the Outline URL.
5. STOP and wait for human approval.

### Human Workflow (Updated)

When a review gate is created:

1. Open Outline in your web browser.
2. Navigate to the "AIDLC Documents" collection.
3. Read the document in rendered form.
4. Use Outline's comment feature to leave feedback directly on the document.
5. Optionally edit the document using the WYSIWYG editor.
6. Approve or request changes via Beads: `bd update <review-gate-id> --status done`

### Pulling Human Edits

If the human edited the document in Outline:

1. The agent runs `python scripts/sync-outline.py pull` before continuing.
2. Changes are written to the local `aidlc-docs/` files.
3. The agent can then commit the updated files to git.

---

## Cross-Reference Preservation

The sync script preserves Beads cross-reference headers (`<!-- beads-issue: ... -->`, `<!-- beads-review: ... -->`) through a round-trip mechanism:

1. **On push**: Headers are stripped from the top of the markdown and appended as a metadata block at the end of the Outline document body (below a `---` separator).
2. **On pull**: The metadata block is detected, stripped from the end, and restored to the top of the file in the canonical format.

This ensures that editing in Outline's WYSIWYG editor does not corrupt the Beads cross-references.

---

## Sync State

The sync script maintains state in `.beads/outline-sync-state.json`:

```json
{
  "collection_id": "outline-collection-uuid",
  "documents": {
    "aidlc-docs/inception/requirements/requirements.md": {
      "outline_id": "outline-document-uuid",
      "last_push_hash": "abc123...",
      "last_pull_hash": "abc123..."
    }
  },
  "last_sync": "2026-02-15T12:00:00Z"
}
```

This file is stored inside `.beads/` which is excluded from git (except the JSONL export). The sync state is local to each developer's machine.

---

## Conflict Resolution

When both sides have changed:

1. **Local wins by default** during `push` -- local content overwrites Outline.
2. **Outline wins by default** during `pull` -- Outline content overwrites local.
3. **Full `sync` pushes first, then pulls** -- last edit wins.

For critical documents, review the `status` output before syncing to detect conflicts.

---

## Security Considerations

- Outline API keys should be stored in `outline/.env`, which is excluded from git via `.gitignore`.
- The self-hosted Outline instance runs on your infrastructure -- no data leaves your network.
- API keys can be scoped to specific operations (e.g., `documents.*` only).
- Consider placing Outline behind a reverse proxy with TLS for production use.

---

## Alternatives Considered

See the plan document for a full comparison of options evaluated:

| Option | Verdict |
|---|---|
| MkDocs Material (read-only rendering) | Good for read-only review, no editing |
| Dhub / TinaCMS (git-backed CMS) | Good git integration, less polished UX |
| HackMD (collaborative editor) | Not true WYSIWYG, sync limits on free tier |
| Notion / Google Docs | Lossy conversion, vendor lock-in |
| **Outline (chosen)** | **Best WYSIWYG UX + full API + self-hosted** |
