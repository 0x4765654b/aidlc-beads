"""Harmbe -- Silverback supervisor agent and sole human interface."""

from __future__ import annotations

import logging
from typing import Any

from orchestrator.agents.base import BaseAgent

logger = logging.getLogger("agents.harmbe")


class Harmbe(BaseAgent):
    """Silverback supervisor: sole point of contact for human users.

    Multi-channel hybrid agent with persistent state:
    - Chat UI (real-time)
    - CLI (gt command)
    - Agent Mail (async notifications)

    Responsibilities:
    - Project registry management
    - Route human decisions (approvals, Q&A, skip permissions)
    - Escalation handler
    - Notification management

    Does NOT: Execute AIDLC stages, create artifacts, invoke OS tools.
    """

    agent_type = "Harmbe"
    agent_mail_identity = "Harmbe"
    system_prompt = (
        "You are Harmbe, the Silverback supervisor of the Gorilla Troop multi-agent system. "
        "You are the sole point of contact for human users. You manage projects, route human "
        "decisions (approvals, Q&A answers, skip permissions), handle escalations from Curious "
        "George, and manage notifications. You delegate all AIDLC work to Project Minder agents. "
        "Be concise, professional, and helpful. When presenting information, use structured "
        "formats. When asking questions, provide clear options."
    )

    async def _execute(self, context: dict[str, Any] | None = None) -> str:
        """Execute Harmbe's main logic based on the incoming context.

        Routes to the appropriate handler based on what triggered execution:
        - Chat messages from humans
        - Escalations from CuriousGeorge
        - Review/Q&A routing
        - Project status queries

        Args:
            context: Dict with keys like 'action', 'message', 'source_agent', etc.

        Returns:
            Response string for the human or requesting agent.
        """
        if context is None:
            context = {}

        action = context.get("action", "chat")

        if action == "chat":
            return await self._handle_chat(context)
        elif action == "escalation":
            return await self._handle_escalation(context)
        elif action == "status":
            return await self._handle_status(context)
        elif action == "route_review":
            return await self._handle_route_review(context)
        elif action == "route_question":
            return await self._handle_route_question(context)
        elif action == "delegate":
            return await self._handle_delegate(context)
        else:
            return await self._handle_chat(context)

    async def _handle_chat(self, context: dict[str, Any]) -> str:
        """Handle a direct chat message from a human.

        Invokes the LLM with conversation context to produce a helpful response.
        """
        message = context.get("message", "")
        conversation_history = context.get("conversation_history", "")

        prompt_parts = [self.system_prompt, "\n\n"]

        if conversation_history:
            prompt_parts.append(
                f"## Conversation History\n\n{conversation_history}\n\n"
            )

        # Add project status context if available
        project_state = await self._get_project_state()
        if project_state:
            prompt_parts.append(
                f"## Current Project State\n\n{project_state}\n\n"
            )

        prompt_parts.append(f"## Human Message\n\n{message}\n\n")
        prompt_parts.append(
            "Respond helpfully and concisely. If the human is asking about "
            "project status, review gates, or questions, provide specific details. "
            "If they need to take action, explain what to do."
        )

        prompt = "".join(prompt_parts)

        try:
            response = await self._invoke_llm(prompt)
            return response
        except Exception as e:
            logger.error("Harmbe LLM invocation failed: %s", e)
            return f"I encountered an error processing your request: {e}"

    async def _handle_escalation(self, context: dict[str, Any]) -> str:
        """Handle an escalation from CuriousGeorge or another agent.

        Formats the escalation for human attention and notifies via Agent Mail.
        """
        source_agent = context.get("source_agent", "unknown")
        error_message = context.get("error_message", "No details provided")
        affected_issue = context.get("affected_issue_id", "")
        investigation = context.get("investigation_summary", "")

        prompt = (
            f"{self.system_prompt}\n\n"
            f"## Escalation from {source_agent}\n\n"
            f"**Error**: {error_message}\n"
            f"**Affected Issue**: {affected_issue}\n"
            f"**Investigation Summary**: {investigation}\n\n"
            "Summarize this escalation for the human. Explain what happened, "
            "what was tried, and what the human needs to do to resolve it. "
            "Suggest specific actions."
        )

        try:
            response = await self._invoke_llm(prompt)
        except Exception as e:
            logger.error("Escalation LLM failed: %s", e)
            response = (
                f"**Escalation from {source_agent}**\n\n"
                f"Error: {error_message}\n"
                f"Issue: {affected_issue}\n\n"
                "Please investigate manually."
            )

        # Notify via Agent Mail
        await self._send_notification(
            subject=f"Escalation from {source_agent}",
            body=response,
            recipients=["Harmbe"],
            importance="high",
        )

        logger.info(
            "Escalation handled from %s for issue %s",
            source_agent,
            affected_issue,
        )
        return response

    async def _handle_status(self, context: dict[str, Any]) -> str:
        """Get project status summary."""
        project_state = await self._get_project_state()

        prompt = (
            f"{self.system_prompt}\n\n"
            f"## Project State\n\n{project_state}\n\n"
            "Provide a clear, structured status summary. Include: "
            "current phase, completed stages, in-progress work, "
            "pending human actions, and what's next."
        )

        try:
            return await self._invoke_llm(prompt)
        except Exception as e:
            logger.error("Status LLM failed: %s", e)
            return project_state or "Unable to retrieve project status."

    async def _handle_route_review(self, context: dict[str, Any]) -> str:
        """Route a review gate notification to the human."""
        issue_id = context.get("issue_id", "")
        artifact_path = context.get("artifact_path", "")

        return (
            f"**Review Required**: {issue_id}\n\n"
            f"Artifact: `{artifact_path}`\n\n"
            "Please review the artifact and approve or reject the review gate."
        )

    async def _handle_route_question(self, context: dict[str, Any]) -> str:
        """Route a Q&A question to the human."""
        issue_id = context.get("issue_id", "")
        question = context.get("question", "")

        return (
            f"**Question**: {issue_id}\n\n"
            f"{question}\n\n"
            "Please select an option or provide a custom answer."
        )

    async def _handle_delegate(self, context: dict[str, Any]) -> str:
        """Delegate AIDLC work to ProjectMinder.

        Harmbe does not execute AIDLC stages directly. It routes
        work requests to the appropriate ProjectMinder.
        """
        project_key = context.get("project_key", "")
        stage_name = context.get("stage_name", "")

        await self._send_notification(
            subject=f"Delegate stage: {stage_name}",
            body=f"Please execute stage '{stage_name}' for project '{project_key}'.",
            recipients=["ProjectMinder"],
        )

        return f"Delegated stage '{stage_name}' to ProjectMinder."

    async def _get_project_state(self) -> str:
        """Query Beads for current project state.

        Returns a formatted string of the project state, or empty string if unavailable.
        """
        try:
            from orchestrator.lib.beads.client import list_issues, ready

            all_issues = list_issues()
            ready_issues = ready()

            in_progress = [i for i in all_issues if i.status == "in_progress"]
            done = [i for i in all_issues if i.status == "done"]
            open_issues = [i for i in all_issues if i.status == "open"]
            review_gates = [
                i for i in open_issues
                if any("type:review-gate" in l for l in i.labels)
            ]
            questions = [
                i for i in open_issues
                if any("type:qa" in l for l in i.labels)
            ]

            parts = [
                f"**Total Issues**: {len(all_issues)}",
                f"**Done**: {len(done)}",
                f"**In Progress**: {len(in_progress)}",
                f"**Open**: {len(open_issues)}",
                f"**Ready (unblocked)**: {len(ready_issues)}",
                f"**Pending Reviews**: {len(review_gates)}",
                f"**Pending Questions**: {len(questions)}",
            ]

            if in_progress:
                parts.append("\n**Currently In Progress:**")
                for issue in in_progress:
                    parts.append(f"  - {issue.id}: {issue.title}")

            if ready_issues:
                parts.append("\n**Ready for Work:**")
                for issue in ready_issues:
                    parts.append(f"  - {issue.id}: {issue.title}")

            if review_gates:
                parts.append("\n**Pending Human Reviews:**")
                for issue in review_gates:
                    parts.append(f"  - {issue.id}: {issue.title}")

            if questions:
                parts.append("\n**Pending Human Answers:**")
                for issue in questions:
                    parts.append(f"  - {issue.id}: {issue.title}")

            return "\n".join(parts)
        except Exception as e:
            logger.warning("Could not query Beads state: %s", e)
            return ""

    async def _send_notification(
        self,
        subject: str,
        body: str,
        recipients: list[str],
        importance: str = "normal",
    ) -> None:
        """Send a notification via Agent Mail."""
        try:
            from orchestrator.lib.agent_mail.client import AgentMailClient

            mail = AgentMailClient()
            mail.send_message(
                "",  # project key
                self.agent_mail_identity,
                recipients,
                subject,
                body,
                importance=importance,
            )
            mail.close()
        except Exception as e:
            logger.warning("Failed to send notification: %s", e)
