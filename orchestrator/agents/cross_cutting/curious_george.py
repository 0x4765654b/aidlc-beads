"""CuriousGeorge -- error investigator and correction agent."""

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
from orchestrator.lib.beads.client import show_issue

logger = logging.getLogger("agents.curious_george")


class CuriousGeorge(BaseAgent):
    """Error investigator invoked when any agent encounters a failure.

    Named after the famously curious monkey who gets into trouble
    but always finds a way out.

    Flow:
    1. Receive error report from any agent
    2. Investigate: read logs, check Beads state, examine files
    3. Attempt correction if within scope
    4. Escalate to Harmbe if unresolvable
    """

    agent_type = "CuriousGeorge"
    agent_mail_identity = "CuriousGeorge"

    system_prompt = (
        "You are CuriousGeorge, the error investigator for the Gorilla Troop "
        "orchestration system. You receive error reports from other agents, "
        "analyse root causes, and suggest corrective actions. Be thorough but "
        "concise. When you can identify a concrete fix, output a JSON block "
        'with {"fix_suggested": true, "fix_description": "...", "target_agent": "..."}. '
        'When the error is beyond your scope, output {"fix_suggested": false, '
        '"escalation_reason": "..."}.'
    )

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Investigate an error report and attempt correction or escalate.

        Expects dispatch context to contain (via instructions JSON):
            error_message: str -- the error description
            source_agent: str -- which agent encountered the error
            affected_issue_id: str -- the Beads issue affected
        """
        logger.info(
            "[CuriousGeorge] Starting investigation for dispatch stage='%s'",
            dispatch.stage_name,
        )

        # ------------------------------------------------------------------
        # 1. Parse error context from dispatch instructions
        # ------------------------------------------------------------------
        error_context = _parse_error_context(dispatch)
        error_message = error_context.get("error_message", "Unknown error")
        source_agent = error_context.get("source_agent", "Unknown")
        affected_issue_id = error_context.get(
            "affected_issue_id", dispatch.beads_issue_id
        )

        logger.info(
            "[CuriousGeorge] Investigating error from %s: %s (issue: %s)",
            source_agent,
            error_message[:120],
            affected_issue_id,
        )

        # ------------------------------------------------------------------
        # 2. Gather investigation evidence
        # ------------------------------------------------------------------
        evidence_parts: list[str] = []

        # 2a. Load any log / context artifacts attached to the dispatch
        try:
            context_text = await self._load_context(dispatch)
            if context_text.strip():
                evidence_parts.append(f"## Attached Context\n{context_text}")
        except Exception as exc:
            logger.warning("[CuriousGeorge] Failed to load context: %s", exc)
            evidence_parts.append(f"## Context Load Error\n{exc}")

        # 2b. Check Beads issue state
        beads_state = await _safe_show_issue(affected_issue_id, workspace=dispatch.workspace_root or None)
        if beads_state:
            evidence_parts.append(
                f"## Beads Issue State\n"
                f"- ID: {beads_state.id}\n"
                f"- Title: {beads_state.title}\n"
                f"- Status: {beads_state.status}\n"
                f"- Assignee: {beads_state.assignee}\n"
                f"- Labels: {beads_state.labels}\n"
                f"- Notes: {beads_state.notes or '(none)'}\n"
            )
        else:
            evidence_parts.append(
                f"## Beads Issue State\nCould not retrieve issue {affected_issue_id}."
            )

        # 2c. Examine referenced artifact files (best-effort)
        examined_files = _examine_artifact_files(dispatch)
        if examined_files:
            evidence_parts.append(f"## Examined Files\n{examined_files}")

        evidence = "\n\n".join(evidence_parts)

        # ------------------------------------------------------------------
        # 3. Build investigation prompt and invoke LLM
        # ------------------------------------------------------------------
        prompt = (
            "Investigate the following error report and provide your analysis.\n\n"
            f"## Error Report\n"
            f"- **Source Agent**: {source_agent}\n"
            f"- **Error Message**: {error_message}\n"
            f"- **Affected Issue**: {affected_issue_id}\n"
            f"- **Stage**: {dispatch.stage_name}\n\n"
            f"{evidence}\n\n"
            "Respond with a JSON object containing your analysis:\n"
            '- "root_cause": a brief description of the root cause\n'
            '- "fix_suggested": true/false\n'
            '- "fix_description": what to do (if fix_suggested is true)\n'
            '- "target_agent": which agent should apply the fix (if any)\n'
            '- "escalation_reason": why escalation is needed (if fix_suggested is false)\n'
        )

        llm_response = await self._invoke_llm(prompt)
        logger.info(
            "[CuriousGeorge] LLM analysis received (%d chars)", len(llm_response)
        )

        # ------------------------------------------------------------------
        # 4. Parse LLM response and act
        # ------------------------------------------------------------------
        analysis = _parse_llm_analysis(llm_response)
        fix_suggested = analysis.get("fix_suggested", False)
        fix_description = analysis.get("fix_description", "")
        target_agent = analysis.get("target_agent", source_agent)
        escalation_reason = analysis.get("escalation_reason", "")
        root_cause = analysis.get("root_cause", "Unknown")

        if fix_suggested and self._mail:
            # 4a. Send correction suggestion to the source agent
            logger.info(
                "[CuriousGeorge] Suggesting fix to %s: %s",
                target_agent,
                fix_description[:100],
            )
            try:
                self._mail.send_message(
                    dispatch.project_key,
                    self.agent_mail_identity,
                    [target_agent],
                    f"[FIX] Error correction for {affected_issue_id}",
                    (
                        f"**Root Cause**: {root_cause}\n\n"
                        f"**Suggested Fix**: {fix_description}\n\n"
                        f"**Original Error**: {error_message}\n"
                    ),
                    thread_id=f"{affected_issue_id}-error",
                    importance="high",
                )
            except Exception as mail_exc:
                logger.warning(
                    "[CuriousGeorge] Failed to send fix to %s: %s",
                    target_agent,
                    mail_exc,
                )

            summary = (
                f"Investigation complete. Root cause: {root_cause}. "
                f"Fix suggested to {target_agent}: {fix_description}"
            )
            status = "completed"

        else:
            # 4b. Escalate to Harmbe
            logger.info(
                "[CuriousGeorge] Escalating to Harmbe: %s",
                escalation_reason[:100],
            )
            if self._mail:
                try:
                    self._mail.send_message(
                        dispatch.project_key,
                        self.agent_mail_identity,
                        ["Harmbe"],
                        f"[ESCALATION] Unresolvable error in {affected_issue_id}",
                        (
                            f"**Source Agent**: {source_agent}\n"
                            f"**Root Cause**: {root_cause}\n"
                            f"**Error**: {error_message}\n"
                            f"**Escalation Reason**: {escalation_reason}\n\n"
                            f"**Full LLM Analysis**:\n{llm_response}\n"
                        ),
                        thread_id=f"{affected_issue_id}-escalation",
                        importance="high",
                    )
                except Exception as mail_exc:
                    logger.warning(
                        "[CuriousGeorge] Failed to send escalation to Harmbe: %s",
                        mail_exc,
                    )

            summary = (
                f"Investigation complete. Root cause: {root_cause}. "
                f"Escalated to Harmbe: {escalation_reason}"
            )
            status = "completed"

        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=[],
            summary=summary,
            status=status,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_error_context(dispatch: DispatchMessage) -> dict:
    """Extract error context from dispatch instructions (JSON or plain text)."""
    if not dispatch.instructions:
        return {}
    try:
        return json.loads(dispatch.instructions)
    except (json.JSONDecodeError, TypeError):
        # Treat plain text as the error message itself
        return {"error_message": dispatch.instructions}


async def _safe_show_issue(issue_id: str, workspace: str | None = None):
    """Attempt to retrieve a Beads issue, returning None on failure."""
    if not issue_id:
        return None
    try:
        return show_issue(issue_id, workspace=workspace)
    except Exception as exc:
        logger.debug("[CuriousGeorge] Could not fetch issue %s: %s", issue_id, exc)
        return None


def _examine_artifact_files(dispatch: DispatchMessage) -> str:
    """Best-effort read of referenced artifact files for investigation context."""
    parts: list[str] = []
    all_paths = dispatch.input_artifacts + dispatch.reference_docs
    for artifact_path in all_paths:
        full_path = Path(dispatch.workspace_root) / artifact_path
        if full_path.exists() and full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8")
                # Truncate large files for investigation
                preview = content[:2000]
                if len(content) > 2000:
                    preview += f"\n... (truncated, {len(content)} chars total)"
                parts.append(f"### {artifact_path}\n```\n{preview}\n```")
            except Exception as exc:
                parts.append(f"### {artifact_path}\n(read error: {exc})")
        else:
            parts.append(f"### {artifact_path}\n(file not found)")
    return "\n\n".join(parts)


def _parse_llm_analysis(response: str) -> dict:
    """Extract JSON analysis from the LLM response.

    Tries to find a JSON object in the response text. Falls back to
    a conservative 'escalate' result if parsing fails.
    """
    # Try to find JSON in the response
    try:
        # Look for the first { ... } block
        start = response.index("{")
        # Find matching closing brace
        depth = 0
        for i in range(start, len(response)):
            if response[i] == "{":
                depth += 1
            elif response[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(response[start : i + 1])
    except (ValueError, json.JSONDecodeError):
        pass

    # Fallback: could not parse structured response
    logger.warning("[CuriousGeorge] Could not parse JSON from LLM response, escalating")
    return {
        "root_cause": "Analysis available but could not be structured",
        "fix_suggested": False,
        "escalation_reason": "LLM response could not be parsed into actionable fix",
    }
