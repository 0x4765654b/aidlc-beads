"""Review gate routes -- list, view, approve, reject review gates."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.api.deps import (
    get_ws_manager,
    get_beads_client,
    get_mail_client,
    get_engine,
    get_registry,
    resolve_project_workspace,
)
from orchestrator.api.models import (
    ReviewGateResponse,
    ReviewDetailResponse,
    ReviewDecision,
    ReviewResultResponse,
)
from orchestrator.api.websocket import ConnectionManager
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.project_registry import ProjectRegistry

logger = logging.getLogger("api.review")

router = APIRouter(prefix="/api/review", tags=["review"])

# Artifact path pattern in issue notes
_ARTIFACT_PATTERN = re.compile(r"artifact:\s*(.+?)(?:\n|$)")


def _extract_artifact_path(notes: str | None) -> str | None:
    """Extract artifact path from issue notes."""
    if not notes:
        return None
    match = _ARTIFACT_PATTERN.search(notes)
    return match.group(1).strip() if match else None


def _extract_stage_name(title: str) -> str:
    """Extract stage name from review gate title like 'REVIEW: Stage Name - ...'."""
    if title.startswith("REVIEW:"):
        parts = title[7:].strip().split("-", 1)
        return parts[0].strip()
    return ""


@router.get("/", response_model=list[ReviewGateResponse])
async def list_review_gates(
    project_key: str | None = None,
    registry: ProjectRegistry = Depends(get_registry),
) -> list[ReviewGateResponse]:
    """List pending review gates.

    Queries Beads for open review gate issues via bd list --label type:review-gate --status open.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    ws = resolve_project_workspace(registry, project_key)

    try:
        issues = beads.list_issues(workspace=ws, label="type:review-gate", status="open")
    except Exception as e:
        logger.error("Failed to list review gates: %s", e)
        raise HTTPException(status_code=502, detail=f"Beads query failed: {e}")

    results: list[ReviewGateResponse] = []
    for issue in issues:
        artifact_path = _extract_artifact_path(issue.notes)
        stage_name = _extract_stage_name(issue.title)

        # Filter by project_key label if requested — skip issues that
        # don't carry the exact project:<key> label (including unlabelled ones)
        if project_key:
            if f"project:{project_key}" not in issue.labels:
                continue

        results.append(
            ReviewGateResponse(
                issue_id=issue.id,
                title=issue.title,
                project_key=project_key or "",
                stage_name=stage_name,
                artifact_path=artifact_path,
                created_at=issue.created_at,
                status=issue.status,
            )
        )

    return results


@router.get("/{issue_id}", response_model=ReviewDetailResponse)
async def get_review_detail(
    issue_id: str,
    project_key: str | None = None,
    registry: ProjectRegistry = Depends(get_registry),
) -> ReviewDetailResponse:
    """Get full review gate details including artifact content.

    Loads the artifact file referenced in the issue notes.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    ws = resolve_project_workspace(registry, project_key)

    try:
        issue = beads.show_issue(issue_id, workspace=ws)
    except Exception as e:
        logger.error("Failed to show issue %s: %s", issue_id, e)
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found: {e}")

    if issue is None:
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")

    artifact_path = _extract_artifact_path(issue.notes)
    artifact_content = None
    stage_name = _extract_stage_name(issue.title)

    if artifact_path:
        # Try to read the artifact file
        try:
            from orchestrator.lib.scribe.workspace import find_workspace_root
            workspace_root = find_workspace_root()
            full_path = Path(workspace_root) / artifact_path
            if full_path.exists():
                artifact_content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Could not read artifact at %s: %s", artifact_path, e)

    return ReviewDetailResponse(
        issue_id=issue.id,
        title=issue.title,
        project_key="",
        stage_name=stage_name,
        artifact_path=artifact_path,
        artifact_content=artifact_content,
        status=issue.status,
        notes=issue.notes,
    )


@router.post("/{issue_id}/approve", response_model=ReviewResultResponse)
async def approve_review(
    issue_id: str,
    body: ReviewDecision,
    project_key: str | None = None,
    ws: ConnectionManager = Depends(get_ws_manager),
    engine: AgentEngine = Depends(get_engine),
    registry: ProjectRegistry = Depends(get_registry),
) -> ReviewResultResponse:
    """Approve a review gate.

    1. Updates Beads issue to done.
    2. If edited_content provided, writes back to artifact file.
    3. Notifies Project Minder via Agent Mail.
    4. Broadcasts review_approved WebSocket event.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    proj_ws = resolve_project_workspace(registry, project_key)

    # Update issue status to done
    try:
        notes = f"APPROVED. Feedback: {body.feedback}" if body.feedback else "APPROVED."
        beads.update_issue(issue_id, workspace=proj_ws, status="done", append_notes=notes)
    except Exception as e:
        logger.error("Failed to approve review %s: %s", issue_id, e)
        raise HTTPException(status_code=502, detail=f"Beads update failed: {e}")

    # Write edited content back to artifact if provided
    if body.edited_content:
        try:
            issue = beads.show_issue(issue_id, workspace=proj_ws)
            artifact_path = _extract_artifact_path(issue.notes)
            if artifact_path and proj_ws:
                full_path = Path(proj_ws) / artifact_path
                if full_path.exists():
                    full_path.write_text(body.edited_content, encoding="utf-8")
                    logger.info("Updated artifact content at %s", artifact_path)
        except Exception as e:
            logger.warning("Could not write edited content: %s", e)

    # Notify via Agent Mail
    mail = get_mail_client()
    if mail is not None:
        try:
            mail.send_message(
                "",  # project key determined from context
                "Harmbe",
                ["ProjectMinder"],
                f"Review approved: {issue_id}",
                f"Review gate {issue_id} has been approved.\nFeedback: {body.feedback or 'None'}",
                thread_id=f"{issue_id}-review",
            )
        except Exception as e:
            logger.warning("Failed to send approval notification: %s", e)

    await ws.broadcast(
        "review_approved", "", {"issue_id": issue_id}
    )

    # Spawn ProjectMinder to advance the pipeline to the next stage
    try:
        await engine.spawn_agent(
            "ProjectMinder",
            context={
                "project_key": project_key or "",
                "workspace_root": proj_ws or "",
                "action": "advance",
                "approved_review_id": issue_id,
            },
            project_key=project_key or "",
        )
        logger.info("ProjectMinder dispatched to advance pipeline after approval of %s", issue_id)
    except Exception as e:
        logger.warning("Could not spawn ProjectMinder after approval of %s: %s", issue_id, e)

    logger.info("Review approved: %s", issue_id)
    return ReviewResultResponse(
        issue_id=issue_id,
        decision="approved",
        next_action="dispatched_next_stage",
        message=f"Review gate {issue_id} approved. Next stage will be dispatched.",
    )


@router.post("/{issue_id}/reject", response_model=ReviewResultResponse)
async def reject_review(
    issue_id: str,
    body: ReviewDecision,
    project_key: str | None = None,
    ws: ConnectionManager = Depends(get_ws_manager),
    engine: AgentEngine = Depends(get_engine),
    registry: ProjectRegistry = Depends(get_registry),
) -> ReviewResultResponse:
    """Reject a review gate (request changes).

    1. Adds feedback as a comment on the Beads issue.
    2. Dispatches Gibbon (rework agent) with the feedback.
    3. Broadcasts review_rejected WebSocket event.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    proj_ws = resolve_project_workspace(registry, project_key)

    # Add rejection feedback to the issue
    try:
        beads.update_issue(
            issue_id,
            workspace=proj_ws,
            append_notes=f"REJECTED: {body.feedback}",
        )
    except Exception as e:
        logger.error("Failed to add rejection feedback to %s: %s", issue_id, e)
        raise HTTPException(status_code=502, detail=f"Beads update failed: {e}")

    # Read the issue to get artifact info for Gibbon
    artifact_path = None
    try:
        issue = beads.show_issue(issue_id, workspace=proj_ws)
        artifact_path = _extract_artifact_path(issue.notes)
    except Exception as e:
        logger.warning("Could not read issue for Gibbon context: %s", e)

    # Spawn Gibbon rework agent via the engine
    try:
        await engine.spawn_agent(
            "Gibbon",
            context={
                "review_gate_id": issue_id,
                "feedback": body.feedback,
                "artifact_path": artifact_path or "",
            },
            task_id=issue_id,
        )
        logger.info("Gibbon rework agent dispatched for %s", issue_id)
    except Exception as e:
        logger.warning("Could not spawn Gibbon agent: %s", e)

    await ws.broadcast(
        "review_rejected",
        "",
        {"issue_id": issue_id, "feedback": body.feedback},
    )

    logger.info("Review rejected: %s (feedback: %s)", issue_id, body.feedback[:80])
    return ReviewResultResponse(
        issue_id=issue_id,
        decision="rejected",
        next_action="dispatched_rework",
        message=f"Review gate {issue_id} rejected. Gibbon rework agent dispatched.",
    )
