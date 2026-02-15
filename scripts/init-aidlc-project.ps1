# AIDLC-Beads Project Initialization Script
# Usage: .\scripts\init-aidlc-project.ps1 [-ProjectType greenfield|brownfield]
#
# This script initializes Beads and creates the base AIDLC issue structure.
# It is meant as a reference/helper -- agents can also create issues manually
# following the workspace-detection-beads.md rule file.

param(
    [ValidateSet("greenfield", "brownfield")]
    [string]$ProjectType = "greenfield"
)

$ErrorActionPreference = "Stop"

Write-Host "=== AIDLC-Beads Project Initialization ===" -ForegroundColor Cyan
Write-Host "Project Type: $ProjectType"
Write-Host ""

# Step 1: Initialize Beads
Write-Host "[1/5] Initializing Beads..." -ForegroundColor Yellow
bd init --prefix ab
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: bd init failed. Is Beads installed? Run: npm install -g @beads/bd" -ForegroundColor Red
    exit 1
}
Write-Host "  Beads initialized with prefix 'ab-'" -ForegroundColor Green

# Step 2: Create directory structure
Write-Host "[2/5] Creating artifact directory structure..." -ForegroundColor Yellow
$dirs = @(
    "aidlc-docs/inception/requirements",
    "aidlc-docs/inception/user-stories",
    "aidlc-docs/inception/reverse-engineering",
    "aidlc-docs/inception/application-design",
    "aidlc-docs/inception/plans",
    "aidlc-docs/construction",
    "aidlc-docs/operations"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "  Created aidlc-docs/ directory tree" -ForegroundColor Green

# Step 3: Create phase epics
Write-Host "[3/5] Creating phase epics..." -ForegroundColor Yellow

$inceptionId = bd create "INCEPTION PHASE" -t epic -p 1 `
    --description "Planning and architecture. Determines WHAT to build and WHY." `
    --labels "phase:inception,project:$ProjectType" `
    --acceptance "All inception stages completed or skipped. Human approval at each gate." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id

$constructionId = bd create "CONSTRUCTION PHASE" -t epic -p 1 `
    --description "Design, implementation, build and test. Determines HOW to build it." `
    --labels "phase:construction" `
    --acceptance "All units designed, implemented, built, and tested." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id

$operationsId = bd create "OPERATIONS PHASE" -t epic -p 3 `
    --description "Deployment and monitoring. Placeholder for future workflows." `
    --labels "phase:operations" `
    --acceptance "Deployment and monitoring configured." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id

Write-Host "  Inception:    $inceptionId" -ForegroundColor Green
Write-Host "  Construction: $constructionId" -ForegroundColor Green
Write-Host "  Operations:   $operationsId" -ForegroundColor Green

# Step 4: Create inception stages
Write-Host "[4/5] Creating inception stage issues..." -ForegroundColor Yellow

# Workspace Detection
$wdId = bd create "Workspace Detection" -t task -p 1 `
    --description "Analyze workspace state, detect project type." `
    --labels "phase:inception,stage:workspace-detection,always" `
    --acceptance "Workspace state recorded. Project type determined." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Workspace Detection: $wdId"

# Requirements Analysis
$raId = bd create "Requirements Analysis" -t task -p 1 `
    --description "Gather and validate requirements. Produce requirements document." `
    --labels "phase:inception,stage:requirements-analysis,always" `
    --acceptance "Requirements document generated. Human review approved." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Requirements Analysis: $raId"

# Requirements Review Gate
$raReviewId = bd create "REVIEW: Requirements Analysis - Awaiting Approval" -t task -p 0 `
    --description "Human reviews requirements document." `
    --labels "phase:inception,type:review-gate" `
    --assignee human `
    --acceptance "Human approved requirements." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Requirements Review: $raReviewId"

# User Stories (conditional)
$usId = bd create "User Stories" -t task -p 2 `
    --description "Create user personas and stories with acceptance criteria." `
    --labels "phase:inception,stage:user-stories,conditional" `
    --acceptance "Stories and personas generated." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  User Stories: $usId"

# User Stories Review Gate
$usReviewId = bd create "REVIEW: User Stories - Awaiting Approval" -t task -p 0 `
    --description "Human reviews user stories." `
    --labels "phase:inception,type:review-gate" `
    --assignee human `
    --acceptance "Human approved stories." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  User Stories Review: $usReviewId"

# Workflow Planning
$wpId = bd create "Workflow Planning" -t task -p 1 `
    --description "Determine which stages to execute. Create execution plan." `
    --labels "phase:inception,stage:workflow-planning,always" `
    --acceptance "Execution plan generated." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Workflow Planning: $wpId"

# Workflow Planning Review Gate
$wpReviewId = bd create "REVIEW: Workflow Planning - Awaiting Approval" -t task -p 0 `
    --description "Human reviews execution plan." `
    --labels "phase:inception,type:review-gate" `
    --assignee human `
    --acceptance "Human approved execution plan." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Workflow Planning Review: $wpReviewId"

# Application Design (conditional)
$adId = bd create "Application Design" -t task -p 2 `
    --description "Component identification, methods, business rules, service design." `
    --labels "phase:inception,stage:application-design,conditional" `
    --acceptance "Components and services defined." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Application Design: $adId"

# Application Design Review Gate
$adReviewId = bd create "REVIEW: Application Design - Awaiting Approval" -t task -p 0 `
    --description "Human reviews application design." `
    --labels "phase:inception,type:review-gate" `
    --assignee human `
    --acceptance "Human approved design." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Application Design Review: $adReviewId"

# Units Generation (conditional)
$ugId = bd create "Units Generation" -t task -p 2 `
    --description "Decompose system into units of work." `
    --labels "phase:inception,stage:units-generation,conditional" `
    --acceptance "Units defined with boundaries and dependencies." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Units Generation: $ugId"

# Units Generation Review Gate
$ugReviewId = bd create "REVIEW: Units Generation - Awaiting Approval" -t task -p 0 `
    --description "Human reviews unit decomposition." `
    --labels "phase:inception,type:review-gate" `
    --assignee human `
    --acceptance "Human approved units." `
    --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
Write-Host "  Units Generation Review: $ugReviewId"

# Brownfield-only: Reverse Engineering
if ($ProjectType -eq "brownfield") {
    $reId = bd create "Reverse Engineering" -t task -p 2 `
        --description "Analyze existing codebase. Document architecture and tech stack." `
        --labels "phase:inception,stage:reverse-engineering,conditional" `
        --acceptance "Codebase analysis complete." `
        --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
    Write-Host "  Reverse Engineering: $reId"

    $reReviewId = bd create "REVIEW: Reverse Engineering - Awaiting Approval" -t task -p 0 `
        --description "Human reviews codebase analysis." `
        --labels "phase:inception,type:review-gate" `
        --assignee human `
        --acceptance "Human approved analysis." `
        --json 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty id
    Write-Host "  Reverse Engineering Review: $reReviewId"
}

Write-Host ""

# Step 5: Wire dependencies
Write-Host "[5/5] Wiring dependency chain..." -ForegroundColor Yellow

# Core chain: WD -> RA -> RA Review -> WP -> WP Review
bd dep add $raId $wdId --type blocks 2>$null
bd dep add $raReviewId $raId --type blocks 2>$null
bd dep add $wpId $raReviewId --type blocks 2>$null
bd dep add $wpReviewId $wpId --type blocks 2>$null

# Conditional stages get their review gates wired
bd dep add $usReviewId $usId --type blocks 2>$null
bd dep add $adReviewId $adId --type blocks 2>$null
bd dep add $ugReviewId $ugId --type blocks 2>$null

# Parent all stages to Inception epic
$allStageIds = @($wdId, $raId, $raReviewId, $usId, $usReviewId, $wpId, $wpReviewId, $adId, $adReviewId, $ugId, $ugReviewId)
foreach ($stageId in $allStageIds) {
    if ($stageId) {
        bd dep add $stageId $inceptionId --type parent 2>$null
    }
}

if ($ProjectType -eq "brownfield" -and $reId) {
    bd dep add $reReviewId $reId --type blocks 2>$null
    bd dep add $reId $wdId --type blocks 2>$null
    bd dep add $raId $reReviewId --type blocks 2>$null
    bd dep add $reId $inceptionId --type parent 2>$null
    bd dep add $reReviewId $inceptionId --type parent 2>$null
}

Write-Host "  Dependency chain wired" -ForegroundColor Green

# Sync
Write-Host ""
Write-Host "Syncing Beads database..." -ForegroundColor Yellow
bd sync 2>$null

Write-Host ""
Write-Host "=== Initialization Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project initialized with:"
Write-Host "  - 3 phase epics (Inception, Construction, Operations)"
Write-Host "  - Inception stages with review gates and dependency chain"
Write-Host "  - Artifact directories under aidlc-docs/"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run 'bd ready --json' to see available work"
Write-Host "  2. Start with Workspace Detection (already created)"
Write-Host "  3. Follow the rules in aidlc-beads-rules/ for each stage"
Write-Host ""
