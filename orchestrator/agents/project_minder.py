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

        if action == "initialize":
            return await self._initialize_project()
        elif action == "advance":
            return await self._advance_workflow()
        elif action == "handle_completion":
            return await self._handle_completion(context)
        elif action == "recommend_skip":
            return await self._recommend_skip(context)
        elif action == "check_review_gates":
            return await self._check_review_gates()
        else:
            return await self._advance_workflow()

    async def _initialize_project(self) -> str:
        """Scaffold the Beads issue graph for a new project.

        Creates phase epics, inception stage issues, review gates,
        and wires up the dependency chain so that ``bd ready`` returns
        the first actionable stage (workspace-detection).

        After scaffolding, advances the workflow to dispatch Scout.
        """
        logger.info("[INIT] _initialize_project starting for project_key=%s, workspace=%s",
                    self._project_key, self._workspace_root)

        from orchestrator.lib.beads.client import (
            create_issue,
            add_dependency,
            list_issues,
        )
        logger.info("[INIT] Beads client imported successfully")

        # Guard: skip if the project already has OPEN inception issues
        try:
            existing = list_issues(label="phase:inception", status="open")
            project_issues = [
                i for i in existing
                if f"project:{self._project_key}" in i.labels
            ]
            if project_issues:
                logger.warning(
                    "[INIT] Project %s already has %d open inception issues — skipping scaffold",
                    self._project_key,
                    len(project_issues),
                )
                return await self._advance_workflow()
        except Exception as e:
            logger.warning("[INIT] Could not check existing issues: %s", e)

        project_label = f"project:{self._project_key}"
        logger.info("[INIT] Scaffolding Beads issue graph with label: %s", project_label)

        # -- Phase Epics -------------------------------------------------------
        try:
            inception_epic = create_issue(
                "INCEPTION PHASE",
                issue_type="epic",
                priority=1,
                description="Planning and architecture. Determines WHAT to build and WHY.",
                labels=f"phase:inception,{project_label}",
                acceptance="All inception stages completed or skipped with explicit user approval.",
            )
            create_issue(  # Construction epic — stages added during Workflow Planning
                "CONSTRUCTION PHASE",
                issue_type="epic",
                priority=1,
                description="Design, implementation, build and test. Determines HOW to build it.",
                labels=f"phase:construction,{project_label}",
                acceptance="All units designed, implemented, built, and tested.",
            )
            create_issue(
                "OPERATIONS PHASE",
                issue_type="epic",
                priority=3,
                description="Deployment and monitoring. Placeholder for future workflows.",
                labels=f"phase:operations,{project_label}",
            )
        except Exception as e:
            logger.error("[INIT] FAILED to create phase epics for %s: %s", self._project_key, e, exc_info=True)
            return f"Initialization failed: could not create phase epics: {e}"

        logger.info("[INIT] Phase epics created (inception=%s)", inception_epic.id)

        # -- Always-execute inception stages -----------------------------------
        try:
            # Workspace Detection
            ws_detect = create_issue(
                "Workspace Detection",
                priority=1,
                description="Analyze workspace state, detect project type (greenfield/brownfield).",
                labels=f"phase:inception,stage:workspace-detection,always,{project_label}",
                acceptance="Workspace state recorded. Project type determined.",
            )
            add_dependency(ws_detect.id, inception_epic.id, dep_type="parent")

            # Requirements Analysis
            req_analysis = create_issue(
                "Requirements Analysis",
                priority=1,
                description="Gather and validate requirements. Generate clarifying questions. Produce requirements document.",
                labels=f"phase:inception,stage:requirements-analysis,always,{project_label}",
                notes="artifact: aidlc-docs/inception/requirements/requirements.md",
                acceptance="Requirements document generated. All questions answered. Human review approved.",
            )
            add_dependency(req_analysis.id, inception_epic.id, dep_type="parent")
            add_dependency(req_analysis.id, ws_detect.id)

            # Requirements Review Gate
            req_review = create_issue(
                "REVIEW: Requirements Analysis - Awaiting Approval",
                priority=0,
                description="Human reviews requirements document and approves.",
                labels=f"phase:inception,type:review-gate,{project_label}",
                notes="artifact: aidlc-docs/inception/requirements/requirements.md",
                assignee="human",
                acceptance="Human approved requirements.",
            )
            add_dependency(req_review.id, inception_epic.id, dep_type="parent")
            add_dependency(req_review.id, req_analysis.id)

            # Workflow Planning
            wf_planning = create_issue(
                "Workflow Planning",
                priority=1,
                description="Determine which stages to execute. Create execution plan.",
                labels=f"phase:inception,stage:workflow-planning,always,{project_label}",
                notes="artifact: aidlc-docs/inception/plans/execution-plan.md",
                acceptance="Execution plan generated. Stages marked execute/skip with explicit user approval.",
            )
            add_dependency(wf_planning.id, inception_epic.id, dep_type="parent")
            add_dependency(wf_planning.id, req_review.id)

            # Workflow Planning Review Gate
            wp_review = create_issue(
                "REVIEW: Workflow Planning - Awaiting Approval",
                priority=0,
                description="Human reviews execution plan and approves stage selections.",
                labels=f"phase:inception,type:review-gate,{project_label}",
                notes="artifact: aidlc-docs/inception/plans/execution-plan.md",
                assignee="human",
                acceptance="Human approved execution plan.",
            )
            add_dependency(wp_review.id, inception_epic.id, dep_type="parent")
            add_dependency(wp_review.id, wf_planning.id)

        except Exception as e:
            logger.error("[INIT] FAILED to create always-execute stages for %s: %s", self._project_key, e, exc_info=True)
            return f"Initialization failed: could not create inception stages: {e}"

        logger.info("[INIT] Always-execute stages created (ws_detect=%s, req=%s, wf=%s)",
                    ws_detect.id, req_analysis.id, wf_planning.id)

        # -- Conditional inception stages --------------------------------------
        # Created without wiring to the main chain; dependencies are set during
        # Workflow Planning when the AI determines execute/skip per stage.
        conditional_stages = [
            ("Reverse Engineering", "reverse-engineering",
             "Analyze existing codebase. Document architecture, components, tech stack."),
            ("User Stories", "user-stories",
             "Create user personas and stories with acceptance criteria."),
            ("Application Design", "application-design",
             "High-level component identification, methods, business rules, service design."),
            ("Units Generation", "units-generation",
             "Decompose system into units of work with boundaries and dependencies."),
        ]
        for title, stage_slug, description in conditional_stages:
            try:
                stage = create_issue(
                    title,
                    priority=2,
                    description=description,
                    labels=f"phase:inception,stage:{stage_slug},conditional,{project_label}",
                )
                add_dependency(stage.id, inception_epic.id, dep_type="parent")

                review = create_issue(
                    f"REVIEW: {title} - Awaiting Approval",
                    priority=0,
                    description=f"Human reviews {title.lower()} artifacts.",
                    labels=f"phase:inception,type:review-gate,{project_label}",
                    assignee="human",
                )
                add_dependency(review.id, inception_epic.id, dep_type="parent")
                add_dependency(review.id, stage.id)
            except Exception as e:
                logger.warning("Could not create conditional stage '%s': %s", title, e)

        logger.info(
            "Scaffolded AIDLC issue graph for project %s (inception epic: %s)",
            self._project_key,
            inception_epic.id,
        )

        # Advance to dispatch the first ready stage (workspace-detection)
        return await self._advance_workflow()

    async def _advance_workflow(self) -> str:
        """Determine the next stage and dispatch it to the appropriate Chimp.

        Uses `bd ready --json` to find unblocked stages, then sends a
        DispatchMessage to the Chimp that handles that stage.
        """
        # Query Beads for ready stages
        ready_issues = await self._get_ready_issues()
        logger.info("[ADVANCE] bd ready returned %d issues", len(ready_issues))

        if not ready_issues:
            # Check if everything is done
            all_done = await self._check_all_done()
            if all_done:
                logger.info("[ADVANCE] All stages complete")
                return "All stages complete. Project finished."
            logger.warning("[ADVANCE] No stages ready — pipeline stalled")
            return "No stages ready. Waiting on review gates or Q&A."

        # Pick the highest-priority ready stage (skip epics/non-stage issues)
        next_issue = None
        stage_name = ""
        for candidate in ready_issues:
            stage_name = self._extract_stage_name(candidate)
            if stage_name:
                next_issue = candidate
                break
            logger.debug(
                "Skipping non-stage issue %s: %s", candidate.id, candidate.title
            )

        if not next_issue:
            logger.warning("[ADVANCE] No actionable stages in %d ready issues", len(ready_issues))
            return "No actionable stages ready. Waiting on dependencies."

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

        Sends the DispatchMessage through Agent Mail and spawns the
        Chimp agent via the engine so it actually executes.
        """
        # Notify via Agent Mail (informational)
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

        # Spawn the Chimp agent via the engine
        if self._engine is not None:
            try:
                await self._engine.spawn_agent(
                    chimp_type,
                    context={"dispatch": dispatch},
                    project_key=self._project_key,
                    task_id=dispatch.beads_issue_id,
                )
                logger.info("Spawned %s for stage '%s'", chimp_type, dispatch.stage_name)
            except Exception as e:
                logger.warning("Could not spawn %s agent: %s", chimp_type, e)
        else:
            logger.warning(
                "No engine reference — cannot spawn %s for stage '%s'",
                chimp_type,
                dispatch.stage_name,
            )
