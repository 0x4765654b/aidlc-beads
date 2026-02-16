"""BaseChimp -- shared base for all 8 Chimp specialist agents."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)

logger = logging.getLogger("agents.chimp")

# Root of the prompt files relative to the package
_PROMPTS_ROOT = Path(__file__).resolve().parent.parent.parent / "prompts"


class BaseChimp(BaseAgent):
    """Base class for all Chimp agents.

    Adds Scribe integration, prompt loading, and standard dispatch/completion flow.
    Subclasses override `_do_stage_work()` only if they need custom logic
    beyond the standard prompt-driven LLM flow.
    """

    # Stages this chimp handles (subclass overrides)
    handled_stages: list[str] = []

    def _load_prompt(self) -> str:
        """Load the system prompt from orchestrator/prompts/{agent_type}/prompt.md.

        Returns:
            The prompt file content, or a fallback prompt if the file is missing.
        """
        agent_dir = self.agent_type.lower()
        prompt_path = _PROMPTS_ROOT / agent_dir / "prompt.md"

        if prompt_path.exists():
            content = prompt_path.read_text(encoding="utf-8")
            logger.info(
                "[%s] Loaded prompt from %s (%d chars)",
                self.agent_type,
                prompt_path,
                len(content),
            )
            return content

        logger.warning(
            "[%s] Prompt file not found at %s, using fallback",
            self.agent_type,
            prompt_path,
        )
        return (
            f"You are {self.agent_type}, a specialist agent in the Gorilla Troop system. "
            f"You handle the following stages: {', '.join(self.handled_stages)}. "
            f"Follow the AIDLC workflow rules and produce markdown artifacts with beads headers."
        )

    def _build_stage_prompt(self, dispatch: DispatchMessage, context: str) -> str:
        """Build the full prompt for LLM invocation.

        Combines the system prompt, dispatch instructions, and loaded context
        into a single prompt string.

        Args:
            dispatch: The dispatch message with stage info.
            context: Loaded input artifact content.

        Returns:
            Complete prompt string for the LLM.
        """
        system_prompt = self._load_prompt()

        parts = [system_prompt, "\n\n---\n\n## Current Task\n"]

        parts.append(f"**Stage**: {dispatch.stage_name}\n")
        parts.append(f"**Phase**: {dispatch.phase}\n")
        parts.append(f"**Beads Issue**: {dispatch.beads_issue_id}\n")

        if dispatch.review_gate_id:
            parts.append(f"**Review Gate**: {dispatch.review_gate_id}\n")
        if dispatch.unit_name:
            parts.append(f"**Unit**: {dispatch.unit_name}\n")
        if dispatch.instructions:
            parts.append(f"\n**Instructions**: {dispatch.instructions}\n")

        parts.append(f"\n**Workspace Root**: {dispatch.workspace_root}\n")
        parts.append(f"**Project Key**: {dispatch.project_key}\n")

        if context.strip():
            parts.append("\n---\n\n## Input Context (Loaded Artifacts)\n\n")
            parts.append(context)

        parts.append(
            "\n\n---\n\n## Instructions\n\n"
            f"Execute the **{dispatch.stage_name}** stage. "
            "Follow the stage-specific instructions from your prompt. "
            "Produce the required artifacts and register them with the Beads issue. "
            "When complete, provide a summary of what was produced."
        )

        return "".join(parts)

    def _parse_artifacts_from_response(self, response: str) -> list[str]:
        """Extract artifact paths from the LLM response.

        Looks for patterns like:
        - artifact: path/to/file.md
        - Created artifact at: path/to/file.md
        - File written: path/to/file.md

        Args:
            response: The LLM response text.

        Returns:
            List of artifact paths found.
        """
        patterns = [
            re.compile(r"artifact:\s*(.+\.md)", re.IGNORECASE),
            re.compile(r"(?:created|wrote|generated)\s+(?:artifact\s+)?(?:at|to)[:\s]+(.+\.(?:md|py))", re.IGNORECASE),
            re.compile(r"file\s+(?:written|created)[:\s]+(.+\.(?:md|py))", re.IGNORECASE),
        ]

        artifacts: list[str] = []
        for pattern in patterns:
            for match in pattern.finditer(response):
                path = match.group(1).strip().strip("`\"'")
                if path and path not in artifacts:
                    artifacts.append(path)

        return artifacts

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Standard Chimp execution flow.

        1. Load context from input artifacts
        2. Build prompt with system prompt + context + dispatch
        3. Invoke LLM
        4. Parse output artifacts from response
        5. Build and return completion message
        """
        context = await self._load_context(dispatch)

        logger.info(
            "[%s] Executing stage '%s' with %d input artifacts",
            self.agent_type,
            dispatch.stage_name,
            len(dispatch.input_artifacts),
        )

        result = await self._do_stage_work(dispatch, context)
        return result

    async def _do_stage_work(
        self, dispatch: DispatchMessage, context: str
    ) -> CompletionMessage:
        """Standard prompt-driven stage execution.

        Loads the prompt, injects context and dispatch info, invokes the LLM,
        parses output artifacts, and returns a completion message.

        Subclasses can override this for custom logic.

        Args:
            dispatch: The dispatch message.
            context: Loaded input artifact content.

        Returns:
            CompletionMessage with output artifacts and summary.
        """
        prompt = self._build_stage_prompt(dispatch, context)

        # Invoke the LLM
        response = await self._invoke_llm(prompt)

        # Parse artifact paths from the response
        artifacts = self._parse_artifacts_from_response(response)

        # Determine status based on response
        status = "completed"
        rework_reason = None

        if any(kw in response.lower() for kw in ["error:", "failed:", "cannot proceed"]):
            status = "needs_rework"
            rework_reason = "LLM response indicates issues that may need attention."

        # Build a summary from the first few lines of the response
        lines = response.strip().split("\n")
        summary_lines = [l for l in lines[:5] if l.strip()]
        summary = " ".join(summary_lines)
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=artifacts,
            summary=summary,
            status=status,
            rework_reason=rework_reason,
        )

    def can_handle_stage(self, stage_name: str) -> bool:
        """Check if this chimp handles the given stage."""
        return stage_name in self.handled_stages
