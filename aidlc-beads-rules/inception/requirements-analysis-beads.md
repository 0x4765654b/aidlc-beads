# Requirements Analysis (Beads-Adapted)

**Purpose**: Gather and validate requirements. Produce requirements document.

**Reference**: See `aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/inception/requirements-analysis.md` for the original stage definition.

**Assume the role** of a product owner.

**Adaptive Phase**: Always executes. Detail level adapts to problem complexity.

---

## Prerequisites

Check with Beads that predecessor stages are complete:

```bash
bd list --labels "stage:workspace-detection" --json
# Verify status: done

# If brownfield:
bd list --labels "stage:reverse-engineering" --json
# Verify status: done (or SKIPPED if greenfield)
```

## Step 1: Claim the Stage

```bash
bd update <requirements-analysis-id> --claim
```

## Step 2: Load Prior Context

Load artifacts from completed predecessor stages:

```bash
# Get workspace detection notes
bd show <workspace-detection-id> --json
# Extract project type, languages, build system from notes

# If brownfield, load reverse engineering artifacts
bd show <reverse-engineering-id> --json
# Extract artifact paths from notes, read each file
```

## Step 3: Analyze User Request

Follow the original AIDLC requirements analysis steps:

1. **Request Clarity**: Clear / Vague / Incomplete
2. **Request Type**: New Feature / Bug Fix / Refactoring / etc.
3. **Initial Scope Estimate**: Single File / Component / System-wide / etc.
4. **Initial Complexity Estimate**: Trivial / Simple / Moderate / Complex

## Step 4: Determine Requirements Depth

Based on analysis, determine: Minimal / Standard / Comprehensive

## Step 5: Assess Current Requirements

Analyze whatever the user has provided (intent statements, existing docs, pasted content).

## Step 6: Generate Clarifying Questions

If questions are needed (they almost always are):

### Option A: Q&A via Beads Issues (Preferred for Few Questions)

For 1-3 focused questions, file them as Beads Q&A issues:

```bash
bd create "QUESTION: Requirements - [Topic 1]" -t message -p 0 \
  --thread <requirements-analysis-id> \
  --description "[Question text]\n\nA) [Option 1]\nB) [Option 2]\nC) [Option 3]\nX) Other (please describe)" \
  --labels "type:qa,phase:inception" \
  --assignee human
```

### Option B: Q&A via Markdown File (Preferred for Many Questions)

For 4+ questions, create a question file AND a tracking Beads issue:

1. Create the question file at `aidlc-docs/inception/requirements/requirement-verification-questions.md`:

```markdown
<!-- beads-issue: <requirements-analysis-id> -->
<!-- beads-review: <requirements-review-gate-id> -->
# Requirements Clarification Questions

Please answer the following questions to help clarify the requirements.

## Question 1
[Question text]

A) [Option 1]
B) [Option 2]
X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 2
...
```

2. File a Beads issue to track it:

```bash
bd create "QUESTION: Requirements - Clarification Questions Filed" -t message -p 0 \
  --thread <requirements-analysis-id> \
  --description "Created requirement-verification-questions.md with [N] questions. Waiting for human answers." \
  --notes "artifact: aidlc-docs/inception/requirements/requirement-verification-questions.md" \
  --labels "type:qa,phase:inception" \
  --assignee human
```

3. Inform the user:

```markdown
I've created requirement-verification-questions.md with [N] questions.
Please answer each question by filling in the letter choice after the [Answer]: tag.
If none of the options match, choose Other and describe your preference.
Let me know when you're done.
```

### GATE: Await User Answers

**DO NOT proceed to Step 7 until:**
- All Beads Q&A issues are answered and closed, OR
- The question file has all `[Answer]:` tags filled in

Check Q&A status:
```bash
bd list --labels "type:qa" --status open --json
```

If any Q&A issues are still open, STOP and wait.

## Step 7: Analyze Answers for Contradictions

Follow the original AIDLC contradiction/ambiguity detection process.

If contradictions found, file follow-up Q&A issues or create a clarification file (same pattern as Step 6).

## Step 8: Generate Requirements Document

Create `aidlc-docs/inception/requirements/requirements.md`:

```markdown
<!-- beads-issue: <requirements-analysis-id> -->
<!-- beads-review: <requirements-review-gate-id> -->
# Requirements Document

## Intent Analysis
- **User Request**: [summary]
- **Request Type**: [type]
- **Scope Estimate**: [scope]
- **Complexity Estimate**: [complexity]

## Functional Requirements
...

## Non-Functional Requirements
...
```

## Step 9: Update Beads Issue

```bash
bd update <requirements-analysis-id> --status done \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nartifact: aidlc-docs/inception/requirements/requirement-verification-questions.md\nDepth: [minimal|standard|comprehensive]. [N] functional and [M] non-functional requirements identified."

# Update the review gate with artifact reference
bd update <requirements-review-gate-id> \
  --notes "artifact: aidlc-docs/inception/requirements/requirements.md\nPlease review the requirements document."
```

## Step 10: Sync and Present Completion

```bash
bd sync
```

Present the standard AIDLC completion message:

```markdown
# Requirements Analysis Complete

Requirements analysis has identified [project type/complexity]:
- [Key functional requirements as bullet points]
- [Key non-functional requirements as bullet points]
- [Architectural considerations if relevant]

> **REVIEW REQUIRED:**
> Please examine the requirements document at: `aidlc-docs/inception/requirements/requirements.md`

> **WHAT'S NEXT?**
>
> **You may:**
>
> **Request Changes** - Ask for modifications to the requirements
> [IF User Stories will be skipped:]
> **Add User Stories** - Include User Stories stage (currently planned to skip)
> **Approve & Continue** - Approve requirements and proceed to **[next stage]**
>
> To approve: `bd update <requirements-review-gate-id> --status done --notes "Approved."`
```

## Step 11: Wait for Human Approval

**STOP** here. Do not proceed until the review gate is closed.

Check:
```bash
bd show <requirements-review-gate-id> --json
# Wait for status: done
```

When the review gate is closed:
- If notes contain change requests → address changes, update artifact, re-present for review.
- If approved → proceed to the next stage (determined by `bd ready --json`).
