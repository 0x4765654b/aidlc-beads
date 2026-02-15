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

### Install Beads

```bash
# npm
npm install -g @beads/bd

# Homebrew (macOS/Linux)
brew install beads

# Go
go install github.com/steveyegge/beads/cmd/bd@latest
```

## Quick Start

### 1. Initialize a New AIDLC Project

**Using the setup script:**

```powershell
# Windows (PowerShell)
.\scripts\init-aidlc-project.ps1 -ProjectType greenfield
```

```bash
# macOS/Linux
./scripts/init-aidlc-project.sh greenfield
```

**Or manually:**

```bash
bd init --prefix ab
# Then follow aidlc-beads-rules/inception/workspace-detection-beads.md
```

### 2. Check What's Ready

```bash
bd ready --json
```

### 3. Let Your Agent Work

Point your agent at `AGENTS.md` and the rules in `aidlc-beads-rules/`. The agent will follow the AIDLC workflow, creating artifacts in `aidlc-docs/` and tracking progress in Beads.

### 4. Review and Approve

When the agent creates a review gate, review the referenced markdown artifact and approve:

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
│   └── design/
│       ├── architecture-c-detailed-design.md  # Full architecture spec
│       ├── beads-schema-mapping.md            # Issue schema mapping
│       ├── cross-reference-contract.md        # Cross-ref conventions
│       └── human-interaction-guide.md         # Human interaction patterns
├── templates/
│   └── artifact-header.md           # Markdown header template
├── scripts/
│   ├── init-aidlc-project.ps1       # Windows initialization
│   └── init-aidlc-project.sh        # Linux/macOS initialization
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

## Multi-Agent Support

Beads enables multiple agents to work on an AIDLC project simultaneously:

- **Single agent**: `bd ready --json` picks the next task.
- **Parallel agents**: Multiple agents claim different units during Construction.
- **Swarm mode**: A coordinator files all issues; workers claim and complete them independently.

Hash-based issue IDs and Dolt-powered merges prevent conflicts across branches and agents.

## Design Documents

- [Architecture C Detailed Design](docs/design/architecture-c-detailed-design.md) -- Full specification
- [Beads Schema Mapping](docs/design/beads-schema-mapping.md) -- How AIDLC maps to Beads issues
- [Cross-Reference Contract](docs/design/cross-reference-contract.md) -- Linking Beads and markdown
- [Human Interaction Guide](docs/design/human-interaction-guide.md) -- All human workflows

## References

- [AIDLC Workflows](https://github.com/harmjeff/aidlc-workflows) -- Original AIDLC rules
- [Beads](https://github.com/steveyegge/beads) -- Git-backed issue tracker for AI agents
- [Introducing Beads](https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a) -- Origin article
- [Beads Best Practices](https://steve-yegge.medium.com/beads-best-practices-2db636b9760c) -- Usage guidance

## License

See [LICENSE](LICENSE) for details.
