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

# Use Continue so stderr warnings from bd don't become terminating errors.
# We check $LASTEXITCODE explicitly after each bd command instead.
$ErrorActionPreference = "Continue"

Write-Host "=== AIDLC-Beads Project Initialization ===" -ForegroundColor Cyan
Write-Host "Project Type: $ProjectType"
Write-Host ""

# Helper: run a bd command, capture stdout JSON, suppress stderr warnings.
# Returns the parsed JSON object, or $null on failure.
function Invoke-BdCreate {
    param([string[]]$BdArgs)

    # Merge stderr into stdout so we can filter it
    $allOutput = & bd @BdArgs 2>&1

    # Separate stdout strings from stderr ErrorRecord objects
    $stdoutLines = $allOutput | Where-Object { $_ -is [string] }
    $stderrLines = $allOutput | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] }

    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $stderrLines) {
            Write-Host "  bd warning: $line" -ForegroundColor DarkYellow
        }
        Write-Host "  ERROR: bd command failed (exit code $LASTEXITCODE)" -ForegroundColor Red
        return $null
    }

    # Join ALL stdout lines to reconstruct multi-line JSON, then parse.
    # bd outputs warnings to stderr (already filtered out) and JSON to stdout.
    $jsonText = ($stdoutLines -join "`n").Trim()

    # If stdout contains non-JSON preamble lines (e.g., status messages before the JSON),
    # extract just the JSON object: from the first '{' to the last '}'.
    if ($jsonText -and $jsonText.Contains('{')) {
        $startIdx = $jsonText.IndexOf('{')
        $endIdx = $jsonText.LastIndexOf('}')
        if ($startIdx -ge 0 -and $endIdx -gt $startIdx) {
            $jsonText = $jsonText.Substring($startIdx, $endIdx - $startIdx + 1)
        }
    }

    if ($jsonText) {
        try {
            return ($jsonText | ConvertFrom-Json)
        } catch {
            Write-Host "  ERROR: Failed to parse JSON from bd output:" -ForegroundColor Red
            Write-Host "  $jsonText" -ForegroundColor DarkYellow
            return $null
        }
    }

    # No JSON output -- print stderr for debugging
    foreach ($line in $stderrLines) {
        Write-Host "  bd warning: $line" -ForegroundColor DarkYellow
    }
    return $null
}

# Helper: run a bd command silently (no JSON output expected), suppress stderr.
function Invoke-BdSilent {
    param([string[]]$BdArgs)
    & bd @BdArgs 2>&1 | Out-Null
}

# Step 1: Initialize Beads
Write-Host "[1/5] Initializing Beads..." -ForegroundColor Yellow
& bd init --prefix ab 2>&1 | ForEach-Object {
    if ($_ -is [string]) { Write-Host "  $_" }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: bd init failed. Is Beads installed?" -ForegroundColor Red
    Write-Host "  Install with: npm install -g @beads/bd" -ForegroundColor Red
    Write-Host "  Or: go install github.com/steveyegge/beads/cmd/bd@latest" -ForegroundColor Red
    exit 1
}

# Configure beads.role to suppress the "beads.role not configured" warning
git config beads.role maintainer 2>&1 | Out-Null
Write-Host "  Beads initialized with prefix 'ab-'" -ForegroundColor Green
Write-Host "  Configured beads.role = maintainer" -ForegroundColor Green

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

$inception = Invoke-BdCreate @("create", "INCEPTION PHASE", "-t", "epic", "-p", "1",
    "--description", "Planning and architecture. Determines WHAT to build and WHY.",
    "--labels", "phase:inception,project:$ProjectType",
    "--acceptance", "All inception stages completed or skipped with explicit user approval. Human approval at each gate.",
    "--json")
$inceptionId = $inception.id

$construction = Invoke-BdCreate @("create", "CONSTRUCTION PHASE", "-t", "epic", "-p", "1",
    "--description", "Design, implementation, build and test. Determines HOW to build it.",
    "--labels", "phase:construction",
    "--acceptance", "All units designed, implemented, built, and tested.",
    "--json")
$constructionId = $construction.id

$operations = Invoke-BdCreate @("create", "OPERATIONS PHASE", "-t", "epic", "-p", "3",
    "--description", "Deployment and monitoring. Placeholder for future workflows.",
    "--labels", "phase:operations",
    "--acceptance", "Deployment and monitoring configured.",
    "--json")
$operationsId = $operations.id

if (-not $inceptionId -or -not $constructionId -or -not $operationsId) {
    Write-Host "ERROR: Failed to create phase epics. Check bd output above." -ForegroundColor Red
    exit 1
}

Write-Host "  Inception:    $inceptionId" -ForegroundColor Green
Write-Host "  Construction: $constructionId" -ForegroundColor Green
Write-Host "  Operations:   $operationsId" -ForegroundColor Green

# Step 4: Create inception stages
Write-Host "[4/5] Creating inception stage issues..." -ForegroundColor Yellow

# Workspace Detection
$wd = Invoke-BdCreate @("create", "Workspace Detection", "-t", "task", "-p", "1",
    "--description", "Analyze workspace state, detect project type.",
    "--labels", "phase:inception,stage:workspace-detection,always",
    "--acceptance", "Workspace state recorded. Project type determined.",
    "--json")
$wdId = $wd.id
Write-Host "  Workspace Detection: $wdId"

# Requirements Analysis
$ra = Invoke-BdCreate @("create", "Requirements Analysis", "-t", "task", "-p", "1",
    "--description", "Gather and validate requirements. Produce requirements document.",
    "--labels", "phase:inception,stage:requirements-analysis,always",
    "--acceptance", "Requirements document generated. Human review approved.",
    "--json")
$raId = $ra.id
Write-Host "  Requirements Analysis: $raId"

# Requirements Review Gate
$raReview = Invoke-BdCreate @("create", "REVIEW: Requirements Analysis - Awaiting Approval", "-t", "task", "-p", "0",
    "--description", "Human reviews requirements document.",
    "--labels", "phase:inception,type:review-gate",
    "--assignee", "human",
    "--acceptance", "Human approved requirements.",
    "--json")
$raReviewId = $raReview.id
Write-Host "  Requirements Review: $raReviewId"

# User Stories (conditional)
$us = Invoke-BdCreate @("create", "User Stories", "-t", "task", "-p", "2",
    "--description", "Create user personas and stories with acceptance criteria.",
    "--labels", "phase:inception,stage:user-stories,conditional",
    "--acceptance", "Stories and personas generated.",
    "--json")
$usId = $us.id
Write-Host "  User Stories: $usId"

# User Stories Review Gate
$usReview = Invoke-BdCreate @("create", "REVIEW: User Stories - Awaiting Approval", "-t", "task", "-p", "0",
    "--description", "Human reviews user stories.",
    "--labels", "phase:inception,type:review-gate",
    "--assignee", "human",
    "--acceptance", "Human approved stories.",
    "--json")
$usReviewId = $usReview.id
Write-Host "  User Stories Review: $usReviewId"

# Workflow Planning
$wp = Invoke-BdCreate @("create", "Workflow Planning", "-t", "task", "-p", "1",
    "--description", "Determine which stages to execute. Create execution plan.",
    "--labels", "phase:inception,stage:workflow-planning,always",
    "--acceptance", "Execution plan generated.",
    "--json")
$wpId = $wp.id
Write-Host "  Workflow Planning: $wpId"

# Workflow Planning Review Gate
$wpReview = Invoke-BdCreate @("create", "REVIEW: Workflow Planning - Awaiting Approval", "-t", "task", "-p", "0",
    "--description", "Human reviews execution plan.",
    "--labels", "phase:inception,type:review-gate",
    "--assignee", "human",
    "--acceptance", "Human approved execution plan.",
    "--json")
$wpReviewId = $wpReview.id
Write-Host "  Workflow Planning Review: $wpReviewId"

# Application Design (conditional)
$ad = Invoke-BdCreate @("create", "Application Design", "-t", "task", "-p", "2",
    "--description", "Component identification, methods, business rules, service design.",
    "--labels", "phase:inception,stage:application-design,conditional",
    "--acceptance", "Components and services defined.",
    "--json")
$adId = $ad.id
Write-Host "  Application Design: $adId"

# Application Design Review Gate
$adReview = Invoke-BdCreate @("create", "REVIEW: Application Design - Awaiting Approval", "-t", "task", "-p", "0",
    "--description", "Human reviews application design.",
    "--labels", "phase:inception,type:review-gate",
    "--assignee", "human",
    "--acceptance", "Human approved design.",
    "--json")
$adReviewId = $adReview.id
Write-Host "  Application Design Review: $adReviewId"

# Units Generation (conditional)
$ug = Invoke-BdCreate @("create", "Units Generation", "-t", "task", "-p", "2",
    "--description", "Decompose system into units of work.",
    "--labels", "phase:inception,stage:units-generation,conditional",
    "--acceptance", "Units defined with boundaries and dependencies.",
    "--json")
$ugId = $ug.id
Write-Host "  Units Generation: $ugId"

# Units Generation Review Gate
$ugReview = Invoke-BdCreate @("create", "REVIEW: Units Generation - Awaiting Approval", "-t", "task", "-p", "0",
    "--description", "Human reviews unit decomposition.",
    "--labels", "phase:inception,type:review-gate",
    "--assignee", "human",
    "--acceptance", "Human approved units.",
    "--json")
$ugReviewId = $ugReview.id
Write-Host "  Units Generation Review: $ugReviewId"

# Brownfield-only: Reverse Engineering
$reId = $null
$reReviewId = $null
if ($ProjectType -eq "brownfield") {
    $re = Invoke-BdCreate @("create", "Reverse Engineering", "-t", "task", "-p", "2",
        "--description", "Analyze existing codebase. Document architecture and tech stack.",
        "--labels", "phase:inception,stage:reverse-engineering,conditional",
        "--acceptance", "Codebase analysis complete.",
        "--json")
    $reId = $re.id
    Write-Host "  Reverse Engineering: $reId"

    $reReview = Invoke-BdCreate @("create", "REVIEW: Reverse Engineering - Awaiting Approval", "-t", "task", "-p", "0",
        "--description", "Human reviews codebase analysis.",
        "--labels", "phase:inception,type:review-gate",
        "--assignee", "human",
        "--acceptance", "Human approved analysis.",
        "--json")
    $reReviewId = $reReview.id
    Write-Host "  Reverse Engineering Review: $reReviewId"
}

Write-Host ""

# Step 5: Wire dependencies
Write-Host "[5/5] Wiring dependency chain..." -ForegroundColor Yellow

# Core chain: WD -> RA -> RA Review -> WP -> WP Review
Invoke-BdSilent @("dep", "add", $raId, $wdId, "--type", "blocks")
Invoke-BdSilent @("dep", "add", $raReviewId, $raId, "--type", "blocks")
Invoke-BdSilent @("dep", "add", $wpId, $raReviewId, "--type", "blocks")
Invoke-BdSilent @("dep", "add", $wpReviewId, $wpId, "--type", "blocks")

# Conditional stages get their review gates wired
Invoke-BdSilent @("dep", "add", $usReviewId, $usId, "--type", "blocks")
Invoke-BdSilent @("dep", "add", $adReviewId, $adId, "--type", "blocks")
Invoke-BdSilent @("dep", "add", $ugReviewId, $ugId, "--type", "blocks")

# Parent all stages to Inception epic
$allStageIds = @($wdId, $raId, $raReviewId, $usId, $usReviewId, $wpId, $wpReviewId, $adId, $adReviewId, $ugId, $ugReviewId)
foreach ($stageId in $allStageIds) {
    if ($stageId) {
        Invoke-BdSilent @("dep", "add", $stageId, $inceptionId, "--type", "parent")
    }
}

if ($ProjectType -eq "brownfield" -and $reId) {
    Invoke-BdSilent @("dep", "add", $reReviewId, $reId, "--type", "blocks")
    Invoke-BdSilent @("dep", "add", $reId, $wdId, "--type", "blocks")
    Invoke-BdSilent @("dep", "add", $raId, $reReviewId, "--type", "blocks")
    Invoke-BdSilent @("dep", "add", $reId, $inceptionId, "--type", "parent")
    Invoke-BdSilent @("dep", "add", $reReviewId, $inceptionId, "--type", "parent")
}

Write-Host "  Dependency chain wired" -ForegroundColor Green

# Sync
Write-Host ""
Write-Host "Syncing Beads database..." -ForegroundColor Yellow
Invoke-BdSilent @("sync")

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
