"""ProjectMinder -- Beta Ape that owns the AIDLC workflow graph."""

from __future__ import annotations

import logging
from typing import Any

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import DispatchMessage, build_dispatch

logger = logging.getLogger("agents.project_minder")

# Map stage names to the Chimp agent type that handles them
STAGE_TO_CHIMP: dict[str, str] = {
    "workspace-detection": "Scout",
    "reverse-engineering": "Scout",
    "requirements-analysis": "Sage",
    "functional-design": "Sage",
    "user-stories": "Bard",
    "workflow-planning": "Planner",
    "units-generation": "Planner",
    "application-design": "Architect",
    "infrastructure-design": "Architect",
    "nfr-requirements": "Steward",
    "nfr-design": "Steward",
    "code-generation": "Forge",
    "build-and-test": "Crucible",
}


class ProjectMinder(BaseAgent):
    """Beta Ape: owns the AIDLC dependency graph for a single project.

    Pattern: Graph (stage dependency graph with conditional edges)

    Responsibilities:
    - Determine stage execution order via Beads state
    - Dispatch stages to Chimps via Context Dispatch Protocol
    - Manage review gate lifecycle
    - Handle conditional stage skip recommendations
    - File Agent Mail file reservations before dispatching Chimps
    - Track overall project progress

    Does NOT: Create artifacts, interact with humans directly.
    """

    agent_type = "ProjectMinder"
    agent_mail_identity = "ProjectMinder"
    system_prompt = (
        "You are Project Minder, the Beta Ape of the Gorilla Troop. You own the AIDLC "
        "dependency graph for a single project. Use 'bd ready --json' to determine the next "
        "stage, then dispatch the appropriate Chimp agent with a Context Dispatch Message. "
        "Manage review gate lifecycle, recommend conditional stage skips to Harmbe, and track "
        "overall project progress. You communicate with Chimps via Agent Mail dispatch messages."
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._project_key: str = ""
        self._workspace_root: str = ""

    async def _execute(self, context: dict[str, Any] | None = None) -> str:
        """Execute ProjectMinder's main loop.

        Checks Beads for the next ready stage, dispatches the appropriate
        Chimp, and manages the review gate lifecycle.

        Args:
            context: Optional dict with 'project_key', 'workspace_root', etc.

        Returns:
            Summary of actions taken.
        """
        if context is None:
            context = {}

        self._project_key = context.get("project_key", self._project_key)
        self._workspace_root = context.get("workspace_root", self._workspace_root)
        action = context.get("action", "advance")

        if action == "advance":
            return await self._advance_workflow()
        elif action == "handle_completion":
            return await self._handle_completion(context)
        elif action == "recommend_skip":
            return await self._recommend_skip(context)
        elif action == "check_review_gates":
            return await self._check_review_gates()
        else:
            return await self._advance_workflow()

    async def _advance_workflow(self) -> str:
        """Determine the next stage and dispatch it to the appropriate Chimp.

        Uses `bd ready --json` to find unblocked stages, then sends a
        DispatchMessage to the Chimp that handles that stage.
        """
        # Query Beads for ready stages
        ready_issues = await self._get_ready_issues()

        if not ready_issues:
            # Check if everything is done
            all_done = await self._check_all_done()
            if all_done:
                return "All stages complete. Project finished."
            return "No stages ready. Waiting on review gates or Q&A."

        # Pick the highest-priority ready stage
        next_issue = ready_issues[0]
        stage_name = self._extract_stage_name(next_issue)

        if not stage_name:
            logger.warning(
                "Could not determine stage name for issue %s: %s",
                next_issue.id,
                next_issue.title,
            )
            return f"Could not determine stage for issue {next_issue.id}"

        # Find the right chimp
        chimp_type = STAGE_TO_CHIMP.get(stage_name)
        if not chimp_type:
            logger.warning("No chimp mapped for stage '%s'", stage_name)
            return f"No agent mapped for stage '{stage_name}'"

        # Gather input artifacts from predecessor issues
        input_artifacts = await self._gather_input_artifacts(next_issue)

        # Build the dispatch message
        dispatch = build_dispatch(
            stage_name=stage_name,
            beads_issue_id=next_issue.id,
            phase=self._determine_phase(next_issue),
            workspace_root=self._workspace_root,
            project_key=self._project_key,
            input_artifacts=input_artifacts,
        )

        # Claim the issue
        await self._claim_issue(next_issue.id)

        # Dispatch to the chimp via the engine
        await self._dispatch_to_chimp(chimp_type, dispatch)

        logger.info(
            "Dispatched stage '%s' (issue %s) to %s",
            stage_name,
            next_issue.id,
            chimp_type,
        )
        return f"Dispatched '{stage_name}' to {chimp_type} (issue {next_issue.id})"

    async def _handle_completion(self, context: dict[str, Any]) -> str:
        """Handle a completion message from a Chimp.

        Updates the Beads issue, triggers review gate if needed,
        and advances to the next stage.
        """
        issue_id = context.get("beads_issue_id", "")
        status = context.get("status", "completed")
        summary = context.get("summary", "")
        artifacts = context.get("output_artifacts", [])

        try:
            from orchestrator.lib.beads.client import update_issue

            # Update the stage issue as done
            notes_parts = [f"Completed: {summary}"]
            for artifact in artifacts:
                notes_parts.append(f"artifact: {artifact}")
            notes = "\n".join(notes_parts)

            if status == "completed":
                update_issue(issue_id, status="done", append_notes=notes)
                logger.info("Stage %s completed successfully", issue_id)
            elif status == "needs_rework":
                update_issue(
                    issue_id,
                    append_notes=f"NEEDS REWORK: {context.get('rework_reason', '')}",
                )
                logger.info("Stage %s needs rework", issue_id)
                # The review gate will handle the rework flow
        except Exception as e:
            logger.error("Failed to update completion for %s: %s", issue_id, e)
            return f"Error updating issue {issue_id}: {e}"

        # Try to advance to the next stage
        return await self._advance_workflow()

    async def _recommend_skip(self, context: dict[str, Any]) -> str:
        """Recommend a stage skip to Harmbe for human approval.

        ProjectMinder identifies stages that may be skippable based on
        project context and sends a recommendation to Harmbe.
        """
        stage_name = context.get("stage_name", "")
        issue_id = context.get("issue_id", "")
        rationale = context.get("rationale", "")

        # Send skip recommendation to Harmbe via Agent Mail
        try:
            from orchestrator.lib.agent_mail.client import AgentMailClient

            mail = AgentMailClient()
            mail.send_message(
                self._project_key,
                self.agent_mail_identity,
                ["Harmbe"],
                f"Skip recommendation: {stage_name}",
                (
                    f"**Stage**: {stage_name}\n"
                    f"**Issue**: {issue_id}\n"
                    f"**Rationale**: {rationale}\n\n"
                    "Please confirm or deny this skip recommendation."
                ),
                importance="normal",
            )
            mail.close()
        except Exception as e:
            logger.warning("Failed to send skip recommendation: %s", e)

        logger.info("Skip recommendation sent for stage '%s'", stage_name)
        return f"Skip recommendation for '{stage_name}' sent to Harmbe."

    async def _check_review_gates(self) -> str:
        """Check for review gates that need attention."""
        try:
            from orchestrator.lib.beads.client import list_issues

            issues = list_issues(label="type:review-gate", status="open")

            if not issues:
                return "No pending review gates."

            parts = ["**Pending Review Gates:**"]
            for issue in issues:
                parts.append(f"  - {issue.id}: {issue.title}")

            return "\n".join(parts)
        except Exception as e:
            logger.error("Failed to check review gates: %s", e)
            return f"Error checking review gates: {e}"

    async def _get_ready_issues(self) -> list:
        """Get ready (unblocked) issues from Beads."""
        try:
            from orchestrator.lib.beads.client import ready
            return ready()
        except Exception as e:
            logger.error("Failed to get ready issues: %s", e)
            return []

    async def _check_all_done(self) -> bool:
        """Check if all non-review, non-epic issues are done."""
        try:
            from orchestrator.lib.beads.client import list_issues

            all_issues = list_issues()
            for issue in all_issues:
                if issue.issue_type == "epic":
                    continue
                if issue.status not in ("done", "closed"):
                    return False
            return True
        except Exception:
            return False

    def _extract_stage_name(self, issue) -> str:
        """Extract the stage name from a Beads issue's labels.

        Looks for labels like 'stage:workspace-detection'.
        """
        for label in issue.labels:
            if label.startswith("stage:"):
                return label[6:]
        return ""

    def _determine_phase(self, issue) -> str:
        """Determine the phase from an issue's labels."""
        for label in issue.labels:
            if label.startswith("phase:"):
                return label[6:]
        return "inception"

    async def _gather_input_artifacts(self, issue) -> list[str]:
        """Gather input artifact paths from predecessor issues.

        Reads predecessor issues' notes for 'artifact:' references.
        """
        import re

        artifacts: list[str] = []
        artifact_pattern = re.compile(r"artifact:\s*(.+?)(?:\n|$)")

        try:
            from orchestrator.lib.beads.client import list_issues

            # Get all done issues to find potential predecessors
            done_issues = [i for i in list_issues() if i.status == "done"]

            for done_issue in done_issues:
                if done_issue.notes:
                    for match in artifact_pattern.finditer(done_issue.notes):
                        path = match.group(1).strip()
                        if path and path not in artifacts:
                            artifacts.append(path)
        except Exception as e:
            logger.warning("Failed to gather input artifacts: %s", e)

        return artifacts

    async def _claim_issue(self, issue_id: str) -> None:
        """Claim a Beads issue (set status to in_progress)."""
        try:
            from orchestrator.lib.beads.client import update_issue
            update_issue(issue_id, status="in_progress")
        except Exception as e:
            logger.warning("Failed to claim issue %s: %s", issue_id, e)

    async def _dispatch_to_chimp(
        self, chimp_type: str, dispatch: DispatchMessage
    ) -> None:
        """Dispatch a stage to a Chimp via the agent engine.

        Sends the DispatchMessage through Agent Mail and triggers
        the engine to spawn the Chimp.
        """
        try:
            from orchestrator.lib.agent_mail.client import AgentMailClient

            mail = AgentMailClient()
            mail.send_message(
                self._project_key,
                self.agent_mail_identity,
                [chimp_type],
                f"Dispatch: {dispatch.stage_name}",
                (
                    f"Stage: {dispatch.stage_name}\n"
                    f"Issue: {dispatch.beads_issue_id}\n"
                    f"Phase: {dispatch.phase}\n"
                    f"Input artifacts: {', '.join(dispatch.input_artifacts)}"
                ),
                thread_id=f"{dispatch.beads_issue_id}-dispatch",
            )
            mail.close()
        except Exception as e:
            logger.warning("Failed to send dispatch message: %s", e)
