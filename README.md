# AIDLC-Beads

Replacing AIDLC markdown-based workflow tracking with [Beads](https://github.com/steveyegge/beads), a git-backed graph issue tracker for AI agents.

## Architecture

This project implements **Architecture C: Hybrid with Clean Contract**, which splits responsibility between two systems:

- **Beads** manages workflow state, task dependencies, human approval gates, Q&A, audit trail, and multi-agent coordination.
- **Markdown** remains the format for rich document artifacts (requirements, designs, user stories, test plans) that humans review.

A cross-reference contract links the two systems -- Beads issues reference artifact file paths, and markdown files include Beads issue IDs in their headers.

See [docs/design/architecture-c-detailed-design.md](docs/design/architecture-c-detailed-design.md) for the full design specification.

## Prerequisites

- [Beads CLI](https://github.com/steveyegge/beads) (`bd`) installed
- Git
- An AI coding agent (Cursor, Claude Code, Sourcegraph Amp, etc.)
- Docker and Docker Compose (for Outline review UI -- optional but recommended)
- Python 3.11+ (for Outline sync script -- optional)

### Install Beads

```bash
# npm
npm install -g @beads/bd

# Homebrew (macOS/Linux)
brew install beads

# Go
go install github.com/steveyegge/beads/cmd/bd@latest
```

## Creating a New Project from This Template

This repository is a **template** for running the AIDLC workflow with Beads on any project. To use it, copy the template files into your target project's working folder, initialize, and go.

### Step 1: Create Your Project Folder

Create a new directory for your project (or use an existing one):

```bash
mkdir my-project
cd my-project
git init
```

### Step 2: Copy Template Files

Copy the following files and directories from this repository into your new project folder. The easiest way is to clone this repo and then copy what you need.

**Windows (PowerShell):**

```powershell
# Clone the template repo (if you haven't already)
git clone https://github.com/harmjeff/aidlc-beads.git C:\temp\aidlc-beads-template

# Copy template files into your project
$template = "C:\temp\aidlc-beads-template"
$project  = "C:\path\to\my-project"

# Core files (required)
Copy-Item "$template\AGENTS.md"     "$project\AGENTS.md"
Copy-Item "$template\LICENSE"       "$project\LICENSE"
Copy-Item "$template\.gitignore"    "$project\.gitignore"
Copy-Item "$template\.gitmodules"   "$project\.gitmodules"

# Directories (required)
Copy-Item "$template\aidlc-beads-rules" "$project\aidlc-beads-rules" -Recurse
Copy-Item "$template\scripts"           "$project\scripts"           -Recurse
Copy-Item "$template\templates"         "$project\templates"         -Recurse

# Directories (recommended -- design docs, reference rules, and Outline config)
Copy-Item "$template\docs"              "$project\docs"              -Recurse
Copy-Item "$template\outline"           "$project\outline"           -Recurse

# Initialize the aidlc-workflows submodule (original AIDLC rules reference)
cd $project
git submodule add https://github.com/awslabs/aidlc-workflows.git aidlc-workflows
git submodule update --init --recursive
```

**macOS/Linux (bash):**

```bash
# Clone the template repo (if you haven't already)
git clone https://github.com/harmjeff/aidlc-beads.git /tmp/aidlc-beads-template

# Copy template files into your project
TEMPLATE="/tmp/aidlc-beads-template"
PROJECT="/path/to/my-project"

# Core files (required)
cp "$TEMPLATE/AGENTS.md"     "$PROJECT/AGENTS.md"
cp "$TEMPLATE/LICENSE"       "$PROJECT/LICENSE"
cp "$TEMPLATE/.gitignore"    "$PROJECT/.gitignore"
cp "$TEMPLATE/.gitmodules"   "$PROJECT/.gitmodules"

# Directories (required)
cp -r "$TEMPLATE/aidlc-beads-rules" "$PROJECT/aidlc-beads-rules"
cp -r "$TEMPLATE/scripts"           "$PROJECT/scripts"
cp -r "$TEMPLATE/templates"         "$PROJECT/templates"

# Directories (recommended -- design docs, reference rules, and Outline config)
cp -r "$TEMPLATE/docs"              "$PROJECT/docs"
cp -r "$TEMPLATE/outline"           "$PROJECT/outline"

# Initialize the aidlc-workflows submodule (original AIDLC rules reference)
cd "$PROJECT"
git submodule add https://github.com/awslabs/aidlc-workflows.git aidlc-workflows
git submodule update --init --recursive
```

#### What Each Piece Does

| File / Directory | Required | Purpose |
|---|---|---|
| `AGENTS.md` | **Yes** | Top-level agent instructions, core rules, `bd` CLI reference |
| `aidlc-beads-rules/` | **Yes** | Beads-adapted AIDLC stage rules (agent reads these during each stage) |
| `scripts/` | **Yes** | Initialization scripts that create Beads issues and wire dependencies |
| `templates/` | **Yes** | Artifact header template for markdown documents |
| `.gitignore` | **Yes** | Excludes `.beads/*.db` and other generated files from git |
| `.gitmodules` | **Yes** | References the `aidlc-workflows` submodule |
| `LICENSE` | Recommended | MIT license |
| `docs/` | Recommended | Architecture specs, schema mapping, human interaction guide |
| `outline/` | Recommended | Docker Compose config for Outline review UI |
| `aidlc-workflows/` | Recommended | Original AIDLC rules (git submodule, referenced by beads-rules) |

> **Do NOT copy** `.beads/`, `aidlc-docs/`, or `.claude/`. These are project-specific and will be generated fresh during initialization.

### Step 3: Initialize Beads and Create the AIDLC Issue Graph

Run the initialization script from your new project folder:

**Windows (PowerShell):**

```powershell
# For a new project with no existing code:
.\scripts\init-aidlc-project.ps1 -ProjectType greenfield

# For a project with existing code to analyze:
.\scripts\init-aidlc-project.ps1 -ProjectType brownfield
```

**macOS/Linux:**

```bash
# For a new project with no existing code:
chmod +x ./scripts/init-aidlc-project.sh
./scripts/init-aidlc-project.sh greenfield

# For a project with existing code to analyze:
./scripts/init-aidlc-project.sh brownfield
```

This script will:
1. Initialize Beads with the `ab-` issue prefix
2. Create the `aidlc-docs/` directory structure for artifacts
3. Create 3 phase epics (Inception, Construction, Operations)
4. Create all Inception stage issues with review gates
5. Wire the dependency chain so stages execute in order
6. Sync the Beads database

After initialization, commit the initial state:

```bash
git add .
git commit -m "Initialize AIDLC-Beads project"
```

### Step 4: Start Working with Your Agent

Open your project in your AI coding agent (Cursor, Claude Code, etc.) and tell the agent what you want to build. The agent will read `AGENTS.md` and follow the AIDLC workflow automatically.

To verify everything is set up correctly:

```bash
# See what's ready for work
bd ready --json

# See the full issue graph
bd list --pretty
```

The first ready task will be **Workspace Detection**, followed by **Requirements Analysis**.

### Step 5: Set Up Outline for Document Review (Optional but Recommended)

Outline provides a web-based WYSIWYG interface so non-technical stakeholders can review and edit artifacts without using a text editor or command line.

```bash
# Configure Outline
cd outline/
cp .env.example .env
# Edit .env -- set secrets and auth provider (see docs/design/outline-integration.md)

# Start Outline
docker compose up -d

# Install sync dependencies and initialize
pip install -r scripts/requirements.txt
# Create an API key at http://localhost:3000/settings/api, add to .env
python scripts/sync-outline.py init
```

See [docs/design/outline-integration.md](docs/design/outline-integration.md) for detailed setup.

### Step 6: Review and Approve at Each Gate

As the agent completes each stage, it will pause at **review gates** and ask you to review the generated artifacts. Documents are automatically pushed to Outline for browser-based review.

**Non-technical reviewers:** Open Outline in your browser, navigate to the "AIDLC Documents" collection, and review the formatted document. Use comments for feedback.

**To approve and let the agent continue:**

```bash
bd update <review-gate-id> --status done --notes "Approved."
```

**To request changes instead:**

```bash
bd update <review-gate-id> --notes "Changes needed: [describe what to change]"
```

See [docs/design/human-interaction-guide.md](docs/design/human-interaction-guide.md) for all human interaction patterns.

---

## Quick Start (Existing Setup)

If your project already has AIDLC-Beads initialized (`.beads/` directory exists):

### 1. Check What's Ready

```bash
bd ready --json
```

### 2. Let Your Agent Work

Point your agent at `AGENTS.md` and the rules in `aidlc-beads-rules/`. The agent will follow the AIDLC workflow, creating artifacts in `aidlc-docs/` and tracking progress in Beads.

### 3. Review and Approve

When the agent creates a review gate, review the document in Outline (or the raw markdown file) and approve:

```bash
bd update <review-gate-id> --status done --notes "Approved."
```

See [docs/design/human-interaction-guide.md](docs/design/human-interaction-guide.md) for all human interaction patterns.

## Project Structure

```
aidlc-beads/
├── AGENTS.md                        # Top-level agent instructions
├── README.md                        # This file
├── aidlc-beads-rules/               # Beads-adapted AIDLC agent rules
│   ├── common/
│   │   ├── beads-integration.md     # Core Beads integration rules
│   │   └── session-continuity-beads.md  # Session resume via Beads
│   └── inception/
│       ├── workspace-detection-beads.md     # Init + workspace scan
│       ├── requirements-analysis-beads.md   # Requirements with Beads gates
│       └── workflow-planning-beads.md       # Execution plan with Beads deps
├── aidlc-workflows/                 # Original AIDLC rules (git submodule)
├── docs/
│   ├── workflow-guide.md                      # Start here: what to expect
│   └── design/
│       ├── architecture-c-detailed-design.md  # Full architecture spec
│       ├── beads-schema-mapping.md            # Issue schema mapping
│       ├── cross-reference-contract.md        # Cross-ref conventions
│       ├── human-interaction-guide.md         # Human interaction patterns
│       └── outline-integration.md             # Outline Wiki setup and design
├── outline/
│   ├── docker-compose.yml           # Outline + Postgres + Redis
│   └── .env.example                 # Environment variable template
├── templates/
│   └── artifact-header.md           # Markdown header template
├── scripts/
│   ├── init-aidlc-project.ps1       # Windows initialization
│   ├── init-aidlc-project.sh        # Linux/macOS initialization
│   ├── sync-outline.py              # Bidirectional Outline sync
│   └── requirements.txt             # Python dependencies for sync
└── .beads/                          # Beads database (auto-created)
```

## How It Works

### The AIDLC Lifecycle

The AI-DLC (AI-Driven Development Life Cycle) has three phases:

1. **Inception** -- Planning and architecture (WHAT and WHY)
2. **Construction** -- Design, implementation, and testing (HOW)
3. **Operations** -- Deployment and monitoring (future)

Each phase contains stages that may be always-execute or conditional. Every stage that produces artifacts has a **review gate** requiring human approval before proceeding.

### What Beads Replaces

| Before (Markdown) | After (Beads) |
|---|---|
| `aidlc-state.md` (workflow state) | Beads issue statuses and dependency graph |
| `audit.md` (interaction log) | Beads event log (automatic) |
| Execution plan checkboxes | Beads issue statuses (done/open/in_progress) |
| Stage ordering (implicit in rules) | Beads `blocks` dependencies (explicit) |
| Human approval (chat-based) | Beads review gate issues (structured) |
| Q&A (separate .md files) | Beads message issues (or .md with tracking issue) |

### What Stays as Markdown

- Requirements documents
- User stories and personas
- Functional designs
- NFR designs
- Infrastructure designs
- Execution plans
- All rich document artifacts that humans need to review

These documents live in `aidlc-docs/` as markdown files (source of truth) and are synced to an **Outline Wiki** instance so non-technical users can review and edit them through a WYSIWYG web interface.

## Multi-Agent Support

Beads enables multiple agents to work on an AIDLC project simultaneously:

- **Single agent**: `bd ready --json` picks the next task.
- **Parallel agents**: Multiple agents claim different units during Construction.
- **Swarm mode**: A coordinator files all issues; workers claim and complete them independently.

Hash-based issue IDs and Dolt-powered merges prevent conflicts across branches and agents.

## Documentation

- **[Workflow Guide](docs/workflow-guide.md)** -- Start here. What to expect when using the system, end to end.
- [Human Interaction Guide](docs/design/human-interaction-guide.md) -- Reference for all human actions (approvals, Q&A, edits)
- [Outline Integration](docs/design/outline-integration.md) -- WYSIWYG review UI setup and design
- [Architecture C Detailed Design](docs/design/architecture-c-detailed-design.md) -- Full technical specification
- [Beads Schema Mapping](docs/design/beads-schema-mapping.md) -- How AIDLC maps to Beads issues
- [Cross-Reference Contract](docs/design/cross-reference-contract.md) -- Linking Beads and markdown

## References

- [AIDLC Workflows](https://github.com/harmjeff/aidlc-workflows) -- Original AIDLC rules
- [Beads](https://github.com/steveyegge/beads) -- Git-backed issue tracker for AI agents
- [Introducing Beads](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a) -- Origin article
- [Beads Best Practices](https://steve-yegge.medium.com/beads-best-practices-2db636b9760c) -- Usage guidance

## License

See [LICENSE](LICENSE) for details.
