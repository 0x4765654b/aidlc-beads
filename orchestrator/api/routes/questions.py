"""Q&A answer handler -- list and answer pending questions."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.api.deps import get_ws_manager, get_beads_client, get_mail_client
from orchestrator.api.models import (
    QuestionResponse,
    QuestionDetailResponse,
    AnswerRequest,
    AnswerResultResponse,
)
from orchestrator.api.websocket import ConnectionManager

logger = logging.getLogger("api.questions")

router = APIRouter(prefix="/api/questions", tags=["questions"])

# Pattern to extract options like "A) Option text" or "B) Another option"
_OPTION_PATTERN = re.compile(r"^([A-Z])\)\s+(.+)$", re.MULTILINE)

# Pattern to extract stage name from thread parent or title
_STAGE_PATTERN = re.compile(r"QUESTION:\s*(\S+)")


def _parse_options(description: str) -> list[str]:
    """Parse multiple-choice options from a question description.

    Looks for lines matching "A) Option text", "B) Option text", etc.

    Args:
        description: Full question description text.

    Returns:
        List of option strings like ["A) Option 1", "B) Option 2"].
    """
    return [
        f"{m.group(1)}) {m.group(2)}"
        for m in _OPTION_PATTERN.finditer(description)
    ]


def _extract_stage(title: str) -> str | None:
    """Extract stage name from a question title like 'QUESTION: Stage - Topic'."""
    match = _STAGE_PATTERN.search(title)
    if match:
        return match.group(1).strip().rstrip(" -")
    return None


@router.get("/", response_model=list[QuestionResponse])
async def list_questions(
    project_key: str | None = None,
) -> list[QuestionResponse]:
    """List pending Q&A questions.

    Queries Beads for open Q&A issues via bd list --label type:qa --status open.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    try:
        issues = beads.list_issues(label="type:qa", status="open")
    except Exception as e:
        logger.error("Failed to list questions: %s", e)
        raise HTTPException(status_code=502, detail=f"Beads query failed: {e}")

    results: list[QuestionResponse] = []
    for issue in issues:
        stage_name = _extract_stage(issue.title)
        results.append(
            QuestionResponse(
                issue_id=issue.id,
                title=issue.title,
                project_key=project_key or "",
                description=issue.description or "",
                stage_name=stage_name,
                created_at=issue.created_at,
                status=issue.status,
            )
        )

    return results


@router.get("/{issue_id}", response_model=QuestionDetailResponse)
async def get_question_detail(
    issue_id: str,
) -> QuestionDetailResponse:
    """Get full question details with parsed options.

    Loads the issue from Beads and parses the description for
    multiple-choice options.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    try:
        issue = beads.show_issue(issue_id)
    except Exception as e:
        logger.error("Failed to show issue %s: %s", issue_id, e)
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found: {e}")

    if issue is None:
        raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")

    options = _parse_options(issue.description or "")
    stage_name = _extract_stage(issue.title)

    return QuestionDetailResponse(
        issue_id=issue.id,
        title=issue.title,
        project_key="",
        description=issue.description or "",
        options=options,
        stage_name=stage_name,
        blocking_issue=None,
        created_at=issue.created_at,
    )


@router.post("/{issue_id}/answer", response_model=AnswerResultResponse)
async def answer_question(
    issue_id: str,
    body: AnswerRequest,
    ws: ConnectionManager = Depends(get_ws_manager),
) -> AnswerResultResponse:
    """Answer a pending question.

    1. Adds the answer as a comment on the Beads issue.
    2. Closes the Q&A issue in Beads.
    3. Checks if any blocked stages are now unblocked.
    4. Broadcasts question_answered WebSocket event.
    """
    beads = get_beads_client()
    if beads is None:
        raise HTTPException(
            status_code=503,
            detail="Beads client unavailable. Ensure bd CLI is on PATH.",
        )

    # Add the answer as notes and close the issue
    try:
        beads.update_issue(issue_id, append_notes=f"ANSWER: {body.answer}")
        beads.close_issue(issue_id, reason=f"Answered: {body.answer}")
    except Exception as e:
        logger.error("Failed to answer question %s: %s", issue_id, e)
        raise HTTPException(status_code=502, detail=f"Beads update failed: {e}")

    # Check for newly unblocked stages
    unblocked_stages: list[str] = []
    try:
        ready_issues = beads.ready()
        unblocked_stages = [issue.id for issue in ready_issues]
    except Exception as e:
        logger.warning("Could not check for unblocked stages: %s", e)

    # Notify via Agent Mail that a question was answered
    mail = get_mail_client()
    if mail is not None:
        try:
            mail.send_message(
                "",
                "Harmbe",
                ["ProjectMinder"],
                f"Question answered: {issue_id}",
                f"Q&A issue {issue_id} answered: {body.answer}\n"
                f"Unblocked stages: {unblocked_stages or 'none'}",
                thread_id=f"{issue_id}-qa",
            )
        except Exception as e:
            logger.warning("Failed to send Q&A notification: %s", e)

    await ws.broadcast(
        "question_answered",
        "",
        {"issue_id": issue_id, "answer": body.answer},
    )

    logger.info("Question answered: %s -> %s", issue_id, body.answer[:80])
    return AnswerResultResponse(
        issue_id=issue_id,
        answer=body.answer,
        unblocked_stages=unblocked_stages,
        message=f"Question {issue_id} answered. {len(unblocked_stages)} stages unblocked.",
    )
