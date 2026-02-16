"""Gibbon -- rework specialist for rejected review gates."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)
from orchestrator.lib.bonobo import AuditLog, FileGuard

logger = logging.getLogger("agents.gibbon")

MAX_REWORK_ITERATIONS = 3


class Gibbon(BaseAgent):
    """Rework specialist invoked when a review gate is rejected.

    Flow:
    1. Receive rework request with original artifact + rejection feedback
    2. Load context and apply corrections
    3. Resubmit for review
    4. If rejected again, retry up to MAX_REWORK_ITERATIONS
    5. After max iterations, escalate to Harmbe
    """

    agent_type = "Gibbon"
    agent_mail_identity = "Gibbon"

    system_prompt = (
        "You are Gibbon, the rework specialist for the Gorilla Troop "
        "orchestration system. You receive rejected artifacts together with "
        "review feedback and produce corrected versions. Preserve the "
        "structure, headers, and intent of the original artifact while "
        "addressing every point raised in the feedback. Output ONLY the "
        "corrected artifact content (markdown body without the beads-issue / "
        "beads-review header comments -- those are managed separately)."
    )

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Apply rework corrections to a rejected artifact.

        Expects dispatch.instructions to be a JSON string with:
            review_gate_id: str -- the review gate that was rejected
            feedback: str -- reviewer feedback / rejection reason
            artifact_path: str -- path to the artifact to rework
            retry_count: int -- current iteration (0-based, default 0)
        """
        logger.info(
            "[Gibbon] Starting rework for stage='%s' issue='%s'",
            dispatch.stage_name,
            dispatch.beads_issue_id,
        )

        # ------------------------------------------------------------------
        # 1. Parse rework context
        # ------------------------------------------------------------------
        rework_ctx = _parse_rework_context(dispatch)
        review_gate_id = rework_ctx.get(
            "review_gate_id", dispatch.review_gate_id or ""
        )
        feedback = rework_ctx.get("feedback", "")
        artifact_path_str = rework_ctx.get("artifact_path", "")
        retry_count = int(rework_ctx.get("retry_count", 0))

        if not artifact_path_str:
            error_msg = "No artifact_path provided in rework request"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        if not feedback:
            error_msg = "No feedback provided in rework request"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        logger.info(
            "[Gibbon] Rework iteration %d/%d for artifact '%s' (gate: %s)",
            retry_count + 1,
            MAX_REWORK_ITERATIONS,
            artifact_path_str,
            review_gate_id,
        )

        # ------------------------------------------------------------------
        # 2. Check retry budget
        # ------------------------------------------------------------------
        if retry_count >= MAX_REWORK_ITERATIONS:
            logger.warning(
                "[Gibbon] Max rework iterations (%d) exceeded, escalating to Harmbe",
                MAX_REWORK_ITERATIONS,
            )
            await self._escalate_to_harmbe(
                dispatch, artifact_path_str, feedback, retry_count
            )
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=(
                    f"Rework exhausted after {MAX_REWORK_ITERATIONS} iterations. "
                    f"Escalated to Harmbe."
                ),
                status="needs_rework",
                rework_reason=(
                    f"Max rework iterations ({MAX_REWORK_ITERATIONS}) exceeded"
                ),
            )

        # ------------------------------------------------------------------
        # 3. Read the original artifact
        # ------------------------------------------------------------------
        artifact_path = Path(dispatch.workspace_root) / artifact_path_str
        try:
            original_content = artifact_path.read_text(encoding="utf-8")
            logger.info(
                "[Gibbon] Read artifact: %s (%d chars)",
                artifact_path,
                len(original_content),
            )
        except FileNotFoundError:
            error_msg = f"Artifact not found: {artifact_path}"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )
        except Exception as exc:
            error_msg = f"Failed to read artifact {artifact_path}: {exc}"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        # ------------------------------------------------------------------
        # 4. Load additional context (reference docs, prior artifacts)
        # ------------------------------------------------------------------
        extra_context = ""
        try:
            extra_context = await self._load_context(dispatch)
        except Exception as exc:
            logger.warning("[Gibbon] Could not load extra context: %s", exc)

        # ------------------------------------------------------------------
        # 5. Build rework prompt and invoke LLM
        # ------------------------------------------------------------------
        prompt = (
            "You are performing a rework correction on a rejected artifact.\n\n"
            f"## Review Gate\n{review_gate_id}\n\n"
            f"## Rejection Feedback\n{feedback}\n\n"
            f"## Original Artifact\n```markdown\n{original_content}\n```\n\n"
        )
        if extra_context.strip():
            prompt += f"## Additional Context\n{extra_context}\n\n"

        prompt += (
            f"## Rework Iteration\nThis is attempt {retry_count + 1} of "
            f"{MAX_REWORK_ITERATIONS}.\n\n"
            "Address every point in the rejection feedback. Preserve the "
            "document structure and beads header comments. Output the complete "
            "corrected artifact content."
        )

        llm_response = await self._invoke_llm(prompt)
        logger.info(
            "[Gibbon] LLM rework response received (%d chars)", len(llm_response)
        )

        # Strip any markdown code fences the LLM may wrap around the response
        corrected_content = _strip_code_fences(llm_response)

        if not corrected_content.strip():
            error_msg = "LLM returned empty rework content"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        # ------------------------------------------------------------------
        # 6. Write the corrected artifact via Bonobo FileGuard
        # ------------------------------------------------------------------
        try:
            audit_log = AuditLog(
                mail_client=self._mail, project_key=dispatch.project_key
            )
            root = Path(dispatch.workspace_root) if dispatch.workspace_root else None
            file_guard = FileGuard(audit_log, workspace_root=root)
            written_path = file_guard.write_file(
                artifact_path,
                corrected_content,
                self.agent_mail_identity,
                overwrite=True,
            )
            logger.info("[Gibbon] Corrected artifact written: %s", written_path)
        except (PermissionError, OSError) as exc:
            error_msg = f"Failed to write corrected artifact: {exc}"
            logger.error("[Gibbon] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        # ------------------------------------------------------------------
        # 7. Return completion
        # ------------------------------------------------------------------
        summary = (
            f"Rework iteration {retry_count + 1}/{MAX_REWORK_ITERATIONS} complete. "
            f"Corrected artifact written to {artifact_path_str}."
        )
        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=[artifact_path_str],
            summary=summary,
            status="completed",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _escalate_to_harmbe(
        self,
        dispatch: DispatchMessage,
        artifact_path: str,
        feedback: str,
        retry_count: int,
    ) -> None:
        """Send escalation message to Harmbe when rework budget is exhausted."""
        if not self._mail:
            logger.warning(
                "[Gibbon] No mail client available for Harmbe escalation"
            )
            return

        try:
            self._mail.send_message(
                dispatch.project_key,
                self.agent_mail_identity,
                ["Harmbe"],
                f"[ESCALATION] Rework exhausted for {dispatch.beads_issue_id}",
                (
                    f"**Stage**: {dispatch.stage_name}\n"
                    f"**Issue**: {dispatch.beads_issue_id}\n"
                    f"**Artifact**: {artifact_path}\n"
                    f"**Iterations Attempted**: {retry_count}\n"
                    f"**Max Allowed**: {MAX_REWORK_ITERATIONS}\n\n"
                    f"**Latest Feedback**:\n{feedback}\n\n"
                    "Gibbon was unable to produce an accepted artifact after "
                    f"{MAX_REWORK_ITERATIONS} attempts. Human review is required."
                ),
                thread_id=f"{dispatch.beads_issue_id}-rework-escalation",
                importance="high",
            )
            logger.info(
                "[Gibbon] Escalation sent to Harmbe for issue %s",
                dispatch.beads_issue_id,
            )
        except Exception as exc:
            logger.warning(
                "[Gibbon] Failed to send escalation to Harmbe: %s", exc
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_rework_context(dispatch: DispatchMessage) -> dict:
    """Extract rework context from dispatch instructions."""
    if not dispatch.instructions:
        return {}
    try:
        data = json.loads(dispatch.instructions)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    # Treat as plain feedback text
    return {"feedback": dispatch.instructions}


def _strip_code_fences(text: str) -> str:
    """Remove surrounding markdown code fences if present.

    LLMs sometimes wrap their output in ```markdown ... ``` blocks.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (e.g. ```markdown or ```)
        first_newline = stripped.index("\n") if "\n" in stripped else len(stripped)
        stripped = stripped[first_newline + 1:]
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped
