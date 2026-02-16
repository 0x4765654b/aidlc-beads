<!-- beads-issue: gt-15 -->
<!-- beads-review: gt-10 -->
# System Architecture

## System Overview

AIDLC-Beads is a template repository that provides the scaffolding for running AI-driven software development projects. It is not an application itself -- it is a framework of rules, scripts, templates, and infrastructure that AI agents follow to produce software with human oversight.

The system has three architectural layers:
1. **Workflow Layer**: AIDLC rules and Beads-adapted rules that define what AI agents do at each stage
2. **State Layer**: Beads issue tracker for workflow state, with JSONL export for Git portability
3. **Review Layer**: Outline Wiki for human-friendly document review, synced bidirectionally with Git-based markdown artifacts

## Architecture Diagram

```mermaid
graph TB
    subgraph workflowLayer [Workflow Layer]
        OriginalRules["Original AIDLC Rules<br/>(aidlc-workflows/ submodule)"]
        BeadsRules["Beads-Adapted Rules<br/>(aidlc-beads-rules/)"]
        Templates["Artifact Templates<br/>(templates/)"]
    end

    subgraph stateLayer [State Layer]
        BeadsCLI["Beads CLI (bd)"]
        BeadsDB["SQLite / JSONL<br/>(.beads/)"]
        IssueGraph["Issue Graph<br/>(epics, stages, review gates, deps)"]
    end

    subgraph artifactLayer [Artifact Layer]
        AidlcDocs["Markdown Artifacts<br/>(aidlc-docs/)"]
        AppCode["Application Code<br/>(workspace root)"]
    end

    subgraph reviewLayer [Review Layer]
        SyncScript["sync-outline.py"]
        OutlineWiki["Outline Wiki<br/>(Docker: outline + postgres + redis)"]
    end

    subgraph versionControl [Version Control]
        GitRepo["Git Repository"]
    end

    BeadsRules -->|"references"| OriginalRules
    BeadsRules -->|"uses"| Templates
    BeadsCLI --> BeadsDB
    BeadsCLI --> IssueGraph
    BeadsDB -->|"bd sync exports"| GitRepo
    AidlcDocs -->|"tracked in"| GitRepo
    AppCode -->|"tracked in"| GitRepo
    SyncScript -->|"reads/writes"| AidlcDocs
    SyncScript -->|"pushes/pulls"| OutlineWiki
    AidlcDocs -->|"cross-referenced via headers"| IssueGraph
```

![System Architecture](images/system-architecture.png)

## Component Descriptions

### Original AIDLC Rules (`aidlc-workflows/`)
- **Purpose**: Defines the complete AIDLC methodology -- all stages, their content, quality standards, and process
- **Dependencies**: None (standalone, imported as Git submodule)
- **Type**: Reference documentation (Git submodule)
- **Key files**: `aws-aidlc-rules/core-workflow.md` (orchestrator), `aws-aidlc-rule-details/` (per-stage details)

### Beads-Adapted Rules (`aidlc-beads-rules/`)
- **Purpose**: Wraps original AIDLC rules with Beads-specific integration instructions
- **Dependencies**: Original AIDLC rules (referenced, not duplicated)
- **Type**: Agent instruction files
- **Key files**: `common/beads-integration.md` (shared protocols), `inception/*.md` (per-stage rules)

### Beads Database (`.beads/`)
- **Purpose**: Stores workflow state -- issues, dependencies, events, metadata
- **Dependencies**: Beads CLI (`bd`)
- **Type**: Data store (SQLite + JSONL)
- **Key files**: `issues.jsonl` (Git-tracked export), `config.yaml` (configuration)

### Markdown Artifacts (`aidlc-docs/`)
- **Purpose**: Rich document artifacts produced by each AIDLC stage
- **Dependencies**: None (plain markdown)
- **Type**: Document store
- **Structure**: `inception/` (requirements, user stories, design) and `construction/` (per-unit design and code summaries)

### Outline Sync Script (`scripts/sync-outline.py`)
- **Purpose**: Bidirectional sync between Git markdown and Outline Wiki
- **Dependencies**: `requests`, `python-dotenv`, `pyyaml`, `rich` (via `scripts/requirements.txt`)
- **Type**: CLI tool (Python)
- **Key features**: Header preservation, content-hash change detection, sync state in `.beads/outline-sync-state.json`

### Initialization Scripts (`scripts/init-aidlc-project.*`)
- **Purpose**: Automated project setup
- **Dependencies**: Beads CLI (`bd`)
- **Type**: Shell scripts (PowerShell + Bash)
- **Creates**: Directory structure, phase epics, stage issues, review gates, dependency chain

### Outline Infrastructure (`outline/`)
- **Purpose**: Self-hosted wiki for document review
- **Dependencies**: Docker, PostgreSQL, Redis
- **Type**: Docker Compose service stack

## Data Flow

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant Rules as AIDLC Rules
    participant Beads as Beads (bd CLI)
    participant Docs as aidlc-docs/
    participant Sync as sync-outline.py
    participant Outline as Outline Wiki
    participant Human as Human Reviewer

    Note over Agent,Human: Stage Execution Flow
    Agent->>Beads: bd ready --json (find unblocked work)
    Agent->>Beads: bd update --claim (claim stage)
    Agent->>Rules: Read stage rule file
    Agent->>Docs: Read upstream artifacts for context
    Agent->>Docs: Create stage artifacts (with headers)
    Agent->>Beads: bd update --status done --notes "artifact: path"
    Agent->>Sync: python sync-outline.py push
    Sync->>Outline: Create/update document

    Note over Agent,Human: Review Gate Flow
    Agent->>Beads: bd create "REVIEW: ..." (review gate)
    Agent->>Human: Notify: artifact ready for review
    Human->>Outline: Review and optionally edit document
    Human->>Beads: bd update <review-id> --status done
    Agent->>Sync: python sync-outline.py pull (get edits)
    Agent->>Beads: bd ready --json (next stage unblocked)
```

![Data Flow](images/data-flow.png)

## Integration Points

- **Beads CLI (`bd`)**: Primary tool for workflow state management. Used by AI agents and humans.
- **Outline API**: RESTful API at `http://localhost:3000/api`. Used by sync-outline.py for document CRUD.
- **Git**: Version control for all artifacts and Beads JSONL export. Standard git operations.
- **AWS MCP Servers**: Configured in `.mcp.json` for AWS service integration (Bedrock, CDK, CloudWatch, etc.)

## Infrastructure Components

- **Outline Wiki**: Docker container (`docker.getoutline.com/outlinewiki/outline:latest`), port 3000
- **PostgreSQL 16**: Docker container (`postgres:16-alpine`), Outline database backend
- **Redis 7**: Docker container (`redis:7-alpine`), Outline session/cache store
- **No cloud infrastructure**: Currently a local-only system. Cloud deployment is not implemented.
