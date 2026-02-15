# AIDLC-Beads Workflow Guide

What to expect when using the AI-Driven Development Life Cycle with Beads.

---

## Who This Guide Is For

This guide is for everyone involved in an AIDLC-Beads project:

- **Product owners and business stakeholders** who define what to build and approve deliverables.
- **Technical leads** who oversee architecture decisions and review designs.
- **Developers** who work alongside AI agents during construction.
- **Anyone new to the process** who wants to understand what happens and when.

You do not need to be technical to follow this guide. The sections below walk through the entire lifecycle in plain language.

---

## The Big Picture

AIDLC is a structured process where an AI agent builds your software in phases, pausing at defined checkpoints to get your input and approval. Think of it like hiring a contractor who draws up plans, shows them to you for sign-off, and only starts building after you agree.

The process has three phases:

1. **Inception** -- The AI figures out WHAT to build and WHY. It produces planning documents (requirements, user stories, designs) that you review and approve.
2. **Construction** -- The AI figures out HOW to build it. It designs each component, writes the code, and runs tests. You review the designs before code is written.
3. **Operations** -- Deployment and monitoring (future; not yet automated).

At every step, the AI pauses and waits for you. Nothing moves forward without your explicit approval.

---

## What You Will Experience

### Phase 1: Inception (Planning)

Inception is where you and the AI align on what the project should accomplish. Here is the typical sequence.

#### Step 1: You Describe What You Want

You tell the AI agent what you want to build. This can be a brief description, a detailed specification, or anything in between. The AI will ask clarifying questions if it needs more information.

**What to expect:** The AI may file formal questions as Beads issues. You will see these as tasks assigned to you. Each question has multiple-choice options -- pick the best answer, or choose "Other" and write your own.

#### Step 2: Workspace Detection (Automatic)

The AI scans your project to understand what already exists -- files, frameworks, dependencies. For a brand-new project, this step is quick. For an existing codebase (brownfield), the AI may also perform a reverse engineering analysis.

**What to expect:** This step runs automatically. No approval is needed. The AI simply records what it found.

#### Step 3: Requirements Analysis

The AI produces a **Requirements Document** based on your description and any Q&A answers. This document lists:

- What the system should do (functional requirements)
- How well it should do it (non-functional requirements like performance, security, accessibility)
- Assumptions and constraints
- Open questions, if any remain

**What to expect:** The AI will notify you that the requirements document is ready for review. You will find it in Outline (the web-based document viewer) under the "AIDLC Documents" collection.

**Your job:** Read the document. Does it capture what you want? Is anything missing or wrong? Then either:

- **Approve** it (the AI moves on to the next step), or
- **Request changes** (the AI revises the document and asks you to review again).

#### Step 4: User Stories (If Applicable)

If the project benefits from user stories, the AI creates personas (fictional users) and writes stories in the format: "As a [persona], I want [action], so that [benefit]." Each story includes acceptance criteria.

**What to expect:** Another document appears in Outline for your review. Same approve-or-revise flow as requirements.

#### Step 5: Workflow Planning

The AI creates an **Execution Plan** that lists every construction unit (component, service, module) it intends to build, in what order, and which optional design stages it recommends.

**What to expect:** This is your chance to adjust scope. You can tell the AI to skip units, reorder them, or add ones it missed. Review the plan in Outline and approve when satisfied.

#### Step 6: Application Design and Units Generation (If Applicable)

For larger projects, the AI may produce a high-level architecture and break the system into discrete units of work. Each unit becomes its own track in the Construction phase.

**What to expect:** More documents in Outline, more review gates. For simple projects, the AI may recommend skipping these stages -- it will ask your permission before doing so.

---

### Phase 2: Construction (Building)

Construction works through each unit identified in the execution plan. For each unit, the AI follows a design-then-build pattern.

#### For Each Unit of Work

1. **Functional Design** -- The AI designs the unit's behavior: data models, API contracts, component structure, business rules. You review the design document.

2. **NFR Requirements and Design** -- If the unit has non-functional concerns (performance targets, security constraints, scalability needs), the AI documents them and designs solutions. You review.

3. **Infrastructure Design** -- If the unit needs infrastructure (databases, queues, cloud services), the AI designs it. You review.

4. **Code Generation** -- The AI writes the code, following the approved designs. You (or a technical reviewer) review the code.

5. **Build and Test** -- The AI builds the project and runs tests. You review the results.

**What to expect:** Each design step produces a document in Outline. Each step has a review gate. The AI will not write code until you have approved the designs. This prevents expensive rework.

**How long does it take?** Each unit's design-and-build cycle can take minutes to hours depending on complexity. The AI works continuously between review gates -- your responsiveness at review gates is the main factor in overall speed.

---

### Phase 3: Operations (Future)

Deployment, monitoring, and operational concerns. This phase is a placeholder for future automation. Currently, deployment is handled manually after Construction completes.

---

## The Review Gate Experience

Review gates are the core interaction point between you and the AI. Here is what a typical review gate looks and feels like.

### 1. You Receive a Notification

The AI completes a stage and tells you:

> "Requirements Analysis is complete. The requirements document is available for review in Outline. Review gate ID: ab-a1b2.5"

### 2. You Open the Document

Open your web browser and go to Outline (typically `http://localhost:3000`). Navigate to **AIDLC Documents** and find the document. It will be formatted with headings, bullet lists, tables -- like a normal document, not raw code.

### 3. You Read and React

- **If it looks good:** Approve it.
  ```
  bd update ab-a1b2.5 --status done --notes "Approved."
  ```

- **If you want changes:** Describe what needs to change. You can also edit the document directly in Outline.
  ```
  bd update ab-a1b2.5 --notes "Changes needed: Add mobile app requirements. Clarify offline mode."
  ```

- **If you want to edit yourself:** Make changes directly in Outline's editor, then approve the review gate. The AI will pick up your edits automatically.

### 4. The AI Continues

Once you approve, the AI picks up where it left off and starts the next stage. If you requested changes, the AI revises the document and notifies you again.

### Key Point: Nothing Happens Without Your Say-So

The AI is designed to stop and wait at every review gate. It will never skip ahead. If you take a break for a day, a week, or a month, the project simply pauses until you return. Run `bd ready --json` at any time to see what is waiting for you.

---

## Questions From the AI

Sometimes the AI needs your input to proceed. When this happens:

1. The AI files a **question** as a Beads issue with multiple-choice answers.
2. You see the question in `bd ready --json` (assigned to you).
3. You answer by updating the issue:
   ```
   bd update ab-XXXX --status done --notes "Answer: B"
   ```
4. The AI picks up your answer and continues.

Questions are always structured with options (A, B, C, etc.) plus an "Other" option for freeform answers. You never need to guess what format the AI expects.

---

## How Long Does the Whole Process Take?

It depends on project complexity, but here are typical timeframes:

| Phase | AI Working Time | Human Review Time | Total Elapsed |
|---|---|---|---|
| **Inception** (simple project) | 15-30 minutes | 30-60 minutes of reading | 1-2 hours |
| **Inception** (complex project) | 1-3 hours | 2-4 hours of reading | Half a day to a full day |
| **Construction** (per unit, simple) | 30-60 minutes | 15-30 minutes of review | 1-2 hours |
| **Construction** (per unit, complex) | 2-4 hours | 1-2 hours of review | Half a day |

The biggest variable is human review time. The AI works fast. Your review throughput determines overall project speed.

**Tip:** Review promptly. The AI cannot proceed past a review gate until you approve. If questions or review gates pile up, the project stalls.

---

## Tools You Will Use

### For Non-Technical Users

| Tool | What It Is | When You Use It |
|---|---|---|
| **Outline** (web browser) | WYSIWYG document viewer and editor | Reading, commenting on, and editing documents |
| **Beads CLI** (`bd` commands) | Workflow command tool | Approving stages, answering questions, checking status |

### For Technical Users (Additional)

| Tool | What It Is | When You Use It |
|---|---|---|
| **Git** | Version control | Viewing diffs, history, branching |
| **Text editor / IDE** | Code and markdown editing | Reviewing code, reading raw artifacts |
| **sync-outline.py** | Outline sync script | Pushing/pulling documents between git and Outline |

### The Minimum You Need to Know

If you only learn two commands, learn these:

```bash
# What needs my attention?
bd ready --json

# Approve a review gate
bd update <issue-id> --status done --notes "Approved."
```

Everything else is documented in the [Human Interaction Guide](design/human-interaction-guide.md).

---

## Common Scenarios

### "I approved something by mistake"

Reopen the review gate:

```bash
bd update <issue-id> --status open --notes "Reopened: need to reconsider section 3."
```

The AI will pause and wait for you to re-review.

### "The AI skipped a stage I wanted"

The AI always asks before skipping optional stages. But if a stage was skipped and you change your mind:

```bash
bd update <stage-id> --status open --notes "Re-enabled: we do need user stories."
bd update <review-gate-id> --status open
```

### "I want to change requirements after they were approved"

You can reopen any previous stage. The AI will re-execute it, incorporating your new input. Be aware that changes to early stages (like requirements) may cascade into later stages that need re-doing.

### "I want to edit a document myself instead of describing changes"

Open the document in Outline, make your edits using the visual editor, then approve the review gate. The AI will pull your changes when it resumes.

### "I am not sure what state the project is in"

```bash
# See everything
bd list --pretty

# See only what is waiting for you
bd ready --assignee human --json
```

### "Multiple people need to review"

Outline supports multiple users. Everyone can read and comment on the same document. One person should be designated to issue the final `bd update` approval command.

---

## Glossary

| Term | Meaning |
|---|---|
| **AIDLC** | AI-Driven Development Life Cycle -- the structured process this system follows |
| **Beads** | A git-backed issue tracker that manages workflow state, dependencies, and approvals |
| **`bd`** | The Beads command-line tool |
| **Stage** | A single step in the workflow (e.g., Requirements Analysis, Code Generation) |
| **Review Gate** | A checkpoint where the AI pauses and waits for human approval |
| **Artifact** | A document produced by a stage (e.g., requirements.md, functional-design.md) |
| **Outline** | A web-based wiki with WYSIWYG editing, used to review and edit artifacts |
| **Inception** | The planning phase -- figuring out WHAT to build |
| **Construction** | The building phase -- figuring out HOW to build it |
| **Unit** | A discrete component or module that gets its own design-and-build cycle |
| **Q&A Issue** | A question filed by the AI that blocks progress until you answer it |
| **Cross-reference** | The link between a Beads issue and its markdown artifact file |

---

## Further Reading

- [Human Interaction Guide](design/human-interaction-guide.md) -- Detailed reference for all human actions
- [Outline Integration](design/outline-integration.md) -- Technical setup for the Outline review UI
- [Architecture Design](design/architecture-c-detailed-design.md) -- How the system is built
- [Cross-Reference Contract](design/cross-reference-contract.md) -- How documents link to workflow issues
