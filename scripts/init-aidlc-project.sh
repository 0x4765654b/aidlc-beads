#!/usr/bin/env bash
# AIDLC-Beads Project Initialization Script
# Usage: ./scripts/init-aidlc-project.sh [greenfield|brownfield]
#
# This script initializes Beads and creates the base AIDLC issue structure.
# It is meant as a reference/helper -- agents can also create issues manually
# following the workspace-detection-beads.md rule file.

set -euo pipefail

PROJECT_TYPE="${1:-greenfield}"

if [[ "$PROJECT_TYPE" != "greenfield" && "$PROJECT_TYPE" != "brownfield" ]]; then
    echo "Usage: $0 [greenfield|brownfield]"
    exit 1
fi

echo "=== AIDLC-Beads Project Initialization ==="
echo "Project Type: $PROJECT_TYPE"
echo ""

# Helper to extract issue ID from bd create --json output
extract_id() {
    echo "$1" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4
}

# Step 1: Initialize Beads
echo "[1/5] Initializing Beads..."
bd init --prefix ab

# Configure beads.role to suppress "beads.role not configured" warnings
git config beads.role maintainer
echo "  Beads initialized with prefix 'ab-'"
echo "  Configured beads.role = maintainer"

# Step 2: Create directory structure
echo "[2/5] Creating artifact directory structure..."
mkdir -p aidlc-docs/inception/requirements
mkdir -p aidlc-docs/inception/user-stories
mkdir -p aidlc-docs/inception/reverse-engineering
mkdir -p aidlc-docs/inception/application-design
mkdir -p aidlc-docs/inception/plans
mkdir -p aidlc-docs/construction
mkdir -p aidlc-docs/operations
echo "  Created aidlc-docs/ directory tree"

# Step 3: Create phase epics
echo "[3/5] Creating phase epics..."

INCEPTION_OUT=$(bd create "INCEPTION PHASE" -t epic -p 1 \
    --description "Planning and architecture. Determines WHAT to build and WHY." \
    --labels "phase:inception,project:$PROJECT_TYPE" \
    --acceptance "All inception stages completed or skipped with explicit user approval. Human approval at each gate." \
    --json)
INCEPTION_ID=$(extract_id "$INCEPTION_OUT")

CONSTRUCTION_OUT=$(bd create "CONSTRUCTION PHASE" -t epic -p 1 \
    --description "Design, implementation, build and test. Determines HOW to build it." \
    --labels "phase:construction" \
    --acceptance "All units designed, implemented, built, and tested." \
    --json)
CONSTRUCTION_ID=$(extract_id "$CONSTRUCTION_OUT")

OPERATIONS_OUT=$(bd create "OPERATIONS PHASE" -t epic -p 3 \
    --description "Deployment and monitoring. Placeholder for future workflows." \
    --labels "phase:operations" \
    --acceptance "Deployment and monitoring configured." \
    --json)
OPERATIONS_ID=$(extract_id "$OPERATIONS_OUT")

echo "  Inception:    $INCEPTION_ID"
echo "  Construction: $CONSTRUCTION_ID"
echo "  Operations:   $OPERATIONS_ID"

# Step 4: Create inception stages
echo "[4/5] Creating inception stage issues..."

# Workspace Detection
WD_OUT=$(bd create "Workspace Detection" -t task -p 1 \
    --description "Analyze workspace state, detect project type." \
    --labels "phase:inception,stage:workspace-detection,always" \
    --acceptance "Workspace state recorded. Project type determined." \
    --json)
WD_ID=$(extract_id "$WD_OUT")
echo "  Workspace Detection: $WD_ID"

# Requirements Analysis
RA_OUT=$(bd create "Requirements Analysis" -t task -p 1 \
    --description "Gather and validate requirements. Produce requirements document." \
    --labels "phase:inception,stage:requirements-analysis,always" \
    --acceptance "Requirements document generated. Human review approved." \
    --json)
RA_ID=$(extract_id "$RA_OUT")
echo "  Requirements Analysis: $RA_ID"

# Requirements Review Gate
RA_REVIEW_OUT=$(bd create "REVIEW: Requirements Analysis - Awaiting Approval" -t task -p 0 \
    --description "Human reviews requirements document." \
    --labels "phase:inception,type:review-gate" \
    --assignee human \
    --acceptance "Human approved requirements." \
    --json)
RA_REVIEW_ID=$(extract_id "$RA_REVIEW_OUT")
echo "  Requirements Review: $RA_REVIEW_ID"

# User Stories (conditional)
US_OUT=$(bd create "User Stories" -t task -p 2 \
    --description "Create user personas and stories with acceptance criteria." \
    --labels "phase:inception,stage:user-stories,conditional" \
    --acceptance "Stories and personas generated." \
    --json)
US_ID=$(extract_id "$US_OUT")
echo "  User Stories: $US_ID"

# User Stories Review Gate
US_REVIEW_OUT=$(bd create "REVIEW: User Stories - Awaiting Approval" -t task -p 0 \
    --description "Human reviews user stories." \
    --labels "phase:inception,type:review-gate" \
    --assignee human \
    --acceptance "Human approved stories." \
    --json)
US_REVIEW_ID=$(extract_id "$US_REVIEW_OUT")
echo "  User Stories Review: $US_REVIEW_ID"

# Workflow Planning
WP_OUT=$(bd create "Workflow Planning" -t task -p 1 \
    --description "Determine which stages to execute. Create execution plan." \
    --labels "phase:inception,stage:workflow-planning,always" \
    --acceptance "Execution plan generated." \
    --json)
WP_ID=$(extract_id "$WP_OUT")
echo "  Workflow Planning: $WP_ID"

# Workflow Planning Review Gate
WP_REVIEW_OUT=$(bd create "REVIEW: Workflow Planning - Awaiting Approval" -t task -p 0 \
    --description "Human reviews execution plan." \
    --labels "phase:inception,type:review-gate" \
    --assignee human \
    --acceptance "Human approved execution plan." \
    --json)
WP_REVIEW_ID=$(extract_id "$WP_REVIEW_OUT")
echo "  Workflow Planning Review: $WP_REVIEW_ID"

# Application Design (conditional)
AD_OUT=$(bd create "Application Design" -t task -p 2 \
    --description "Component identification, methods, business rules, service design." \
    --labels "phase:inception,stage:application-design,conditional" \
    --acceptance "Components and services defined." \
    --json)
AD_ID=$(extract_id "$AD_OUT")
echo "  Application Design: $AD_ID"

# Application Design Review Gate
AD_REVIEW_OUT=$(bd create "REVIEW: Application Design - Awaiting Approval" -t task -p 0 \
    --description "Human reviews application design." \
    --labels "phase:inception,type:review-gate" \
    --assignee human \
    --acceptance "Human approved design." \
    --json)
AD_REVIEW_ID=$(extract_id "$AD_REVIEW_OUT")
echo "  Application Design Review: $AD_REVIEW_ID"

# Units Generation (conditional)
UG_OUT=$(bd create "Units Generation" -t task -p 2 \
    --description "Decompose system into units of work." \
    --labels "phase:inception,stage:units-generation,conditional" \
    --acceptance "Units defined with boundaries and dependencies." \
    --json)
UG_ID=$(extract_id "$UG_OUT")
echo "  Units Generation: $UG_ID"

# Units Generation Review Gate
UG_REVIEW_OUT=$(bd create "REVIEW: Units Generation - Awaiting Approval" -t task -p 0 \
    --description "Human reviews unit decomposition." \
    --labels "phase:inception,type:review-gate" \
    --assignee human \
    --acceptance "Human approved units." \
    --json)
UG_REVIEW_ID=$(extract_id "$UG_REVIEW_OUT")
echo "  Units Generation Review: $UG_REVIEW_ID"

# Brownfield: Reverse Engineering
if [[ "$PROJECT_TYPE" == "brownfield" ]]; then
    RE_OUT=$(bd create "Reverse Engineering" -t task -p 2 \
        --description "Analyze existing codebase. Document architecture and tech stack." \
        --labels "phase:inception,stage:reverse-engineering,conditional" \
        --acceptance "Codebase analysis complete." \
        --json)
    RE_ID=$(extract_id "$RE_OUT")
    echo "  Reverse Engineering: $RE_ID"

    RE_REVIEW_OUT=$(bd create "REVIEW: Reverse Engineering - Awaiting Approval" -t task -p 0 \
        --description "Human reviews codebase analysis." \
        --labels "phase:inception,type:review-gate" \
        --assignee human \
        --acceptance "Human approved analysis." \
        --json)
    RE_REVIEW_ID=$(extract_id "$RE_REVIEW_OUT")
    echo "  Reverse Engineering Review: $RE_REVIEW_ID"
fi

echo ""

# Step 5: Wire dependencies
echo "[5/5] Wiring dependency chain..."

# Core chain: WD -> RA -> RA Review -> WP -> WP Review
bd dep add "$RA_ID" "$WD_ID" --type blocks
bd dep add "$RA_REVIEW_ID" "$RA_ID" --type blocks
bd dep add "$WP_ID" "$RA_REVIEW_ID" --type blocks
bd dep add "$WP_REVIEW_ID" "$WP_ID" --type blocks

# Conditional stage review gates
bd dep add "$US_REVIEW_ID" "$US_ID" --type blocks
bd dep add "$AD_REVIEW_ID" "$AD_ID" --type blocks
bd dep add "$UG_REVIEW_ID" "$UG_ID" --type blocks

# Parent all stages to Inception
for ID in $WD_ID $RA_ID $RA_REVIEW_ID $US_ID $US_REVIEW_ID $WP_ID $WP_REVIEW_ID $AD_ID $AD_REVIEW_ID $UG_ID $UG_REVIEW_ID; do
    bd dep add "$ID" "$INCEPTION_ID" --type parent
done

# Brownfield wiring
if [[ "$PROJECT_TYPE" == "brownfield" ]]; then
    bd dep add "$RE_REVIEW_ID" "$RE_ID" --type blocks
    bd dep add "$RE_ID" "$WD_ID" --type blocks
    bd dep add "$RA_ID" "$RE_REVIEW_ID" --type blocks
    bd dep add "$RE_ID" "$INCEPTION_ID" --type parent
    bd dep add "$RE_REVIEW_ID" "$INCEPTION_ID" --type parent
fi

echo "  Dependency chain wired"

# Sync
echo ""
echo "Syncing Beads database..."
bd sync

echo ""
echo "=== Initialization Complete ==="
echo ""
echo "Project initialized with:"
echo "  - 3 phase epics (Inception, Construction, Operations)"
echo "  - Inception stages with review gates and dependency chain"
echo "  - Artifact directories under aidlc-docs/"
echo ""
echo "Next steps:"
echo "  1. Run 'bd ready --json' to see available work"
echo "  2. Start with Workspace Detection"
echo "  3. Follow the rules in aidlc-beads-rules/ for each stage"
echo ""
echo "Optional - Set up Outline for non-technical reviewers:"
echo "  1. cd outline && cp .env.example .env (then edit .env)"
echo "  2. docker compose up -d"
echo "  3. Create API key at http://localhost:3000/settings/api"
echo "  4. pip install -r scripts/requirements.txt"
echo "  5. python scripts/sync-outline.py init"
echo "  See docs/design/outline-integration.md for details."
echo ""
