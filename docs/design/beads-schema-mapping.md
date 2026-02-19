# Beads Issue Schema Mapping for AIDLC

## Issue Prefix

`ab-` (aidlc-beads)

---

## Phase Epic Template

```bash
bd create "INCEPTION PHASE" -t epic -p 1 \
  --description "Planning and architecture phase. Determines WHAT to build and WHY." \
  --labels "phase:inception" \
  --acceptance "All inception stages completed or intentionally skipped. Human approval received at each gate."
```

---

## Inception Stage Issues

### Always-Execute Stages

#### Workspace Detection
```bash
bd create "Workspace Detection" -t task -p 1 \
  --description "Analyze workspace state, detect project type (greenfield/brownfield), scan for existing code." \
  --labels "phase:inception,stage:workspace-detection,always" \
  --acceptance "Workspace state recorded. Project type determined. Next stage identified."
# Parent: Inception epic
# No review gate (informational only, auto-proceeds)
```

#### Requirements Analysis
```bash
bd create "Requirements Analysis" -t task -p 1 \
  --description "Gather and validate requirements. Generate clarifying questions. Produce requirements document." \
  --labels "phase:inception,stage:requirements-analysis,always" \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nartifact: aidlc-docs/inception/requirements/requirement-verification-questions.md" \
  --acceptance "Requirements document generated. All clarifying questions answered. Human review approved."
# Parent: Inception epic
# Blocked by: Workspace Detection (or Reverse Engineering if brownfield)
```

#### Requirements Review Gate
```bash
bd create "REVIEW: Requirements Analysis - Awaiting Approval" -t task -p 0 \
  --description "Human must review requirements document and approve before proceeding." \
  --labels "phase:inception,type:review-gate" \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md" \
  --assignee human \
  --acceptance "Human has reviewed and approved the requirements document."
# Parent: Inception epic
# Blocked by: Requirements Analysis
# Blocks: User Stories (or Workflow Planning if stories skipped)
```

#### Workflow Planning
```bash
bd create "Workflow Planning" -t task -p 1 \
  --description "Determine which stages to execute. Perform scope analysis, risk assessment. Create execution plan." \
  --labels "phase:inception,stage:workflow-planning,always" \
  --notes "artifact: aidlc-docs/inception/plans/execution-plan.md" \
  --acceptance "Execution plan generated. All conditional stages marked execute/skip with rationale."
# Parent: Inception epic
# Blocked by: REVIEW: Requirements (or REVIEW: User Stories if stories executed)
```

#### Workflow Planning Review Gate
```bash
bd create "REVIEW: Workflow Planning - Awaiting Approval" -t task -p 0 \
  --description "Human must review execution plan and approve stage selections before construction begins." \
  --labels "phase:inception,type:review-gate" \
  --notes "artifact: aidlc-docs/inception/plans/execution-plan.md" \
  --assignee human \
  --acceptance "Human has reviewed and approved the execution plan."
# Parent: Inception epic
# Blocked by: Workflow Planning
# Blocks: First construction stage (or Application Design / Units Generation if executing)
```

### Conditional Stages

#### Reverse Engineering (Brownfield Only)
```bash
bd create "Reverse Engineering" -t task -p 2 \
  --description "Analyze existing codebase. Document architecture, components, and technology stack." \
  --labels "phase:inception,stage:reverse-engineering,conditional" \
  --notes "artifact: aidlc-docs/inception/reverse-engineering/architecture.md\nartifact: aidlc-docs/inception/reverse-engineering/component-inventory.md\nartifact: aidlc-docs/inception/reverse-engineering/technology-stack.md" \
  --acceptance "Codebase analysis complete. Architecture, components, and tech stack documented."
```

#### User Stories
```bash
bd create "User Stories" -t task -p 2 \
  --description "Create user personas and user stories with acceptance criteria." \
  --labels "phase:inception,stage:user-stories,conditional" \
  --notes "artifact: aidlc-docs/inception/user-stories/stories.md\nartifact: aidlc-docs/inception/user-stories/personas.md" \
  --acceptance "User stories generated with acceptance criteria. Personas defined."
```

#### Application Design
```bash
bd create "Application Design" -t task -p 2 \
  --description "High-level component identification, method definitions, business rules, and service layer design." \
  --labels "phase:inception,stage:application-design,conditional" \
  --notes "artifact: aidlc-docs/inception/application-design/components.md" \
  --acceptance "Components, methods, business rules, and services defined."
```

#### Units Generation
```bash
bd create "Units Generation" -t task -p 2 \
  --description "Decompose the system into units of work. Define unit boundaries, dependencies, and story mapping." \
  --labels "phase:inception,stage:units-generation,conditional" \
  --notes "artifact: aidlc-docs/inception/application-design/unit-of-work.md" \
  --acceptance "Units of work defined with clear boundaries and dependency ordering."
```

Each conditional stage has a corresponding review gate following the same pattern as the always-execute stages.

---

## Construction Stage Issues (Per-Unit)

For each unit of work, create a sub-epic under the Construction phase epic:

```bash
bd create "[Unit Name] - Construction" -t epic -p 1 \
  --description "Design, implement, and test [unit name]." \
  --labels "phase:construction,unit:[unit-slug]"
```

Then create stage tasks as children of the unit sub-epic, following the same pattern as Inception stages.

---

## Q&A Issues

```bash
bd create "QUESTION: [Stage] - [Brief Topic]" -t message -p 0 \
  --thread [parent-stage-issue-id] \
  --description "Question text here.\n\nA) Option 1\nB) Option 2\nC) Option 3\nD) Other (please describe)" \
  --labels "type:qa,phase:[phase]" \
  --assignee human
```

The Q&A issue blocks the parent stage task until the human answers (updates notes with answer and closes the issue).

---

## Label Taxonomy

### Phase Labels
- `phase:inception`
- `phase:construction`
- `phase:operations`

### Stage Labels
- `stage:workspace-detection`
- `stage:reverse-engineering`
- `stage:requirements-analysis`
- `stage:user-stories`
- `stage:workflow-planning`
- `stage:application-design`
- `stage:units-generation`
- `stage:functional-design`
- `stage:nfr-requirements`
- `stage:nfr-design`
- `stage:infrastructure-design`
- `stage:code-generation`
- `stage:build-and-test`

### Type Labels
- `type:review-gate`
- `type:qa`

### Execution Labels
- `always` (stage always executes)
- `conditional` (stage may be skipped)

### Project Labels
- `project:greenfield`
- `project:brownfield`
