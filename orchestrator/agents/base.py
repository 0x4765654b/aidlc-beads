"""BaseAgent -- common base class for all Gorilla Troop agents."""

from __future__ import annotations

import logging
from typing import Any

from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)
from orchestrator.agents.retry import with_retry
from orchestrator.agents.tool_registry import ToolGuard

logger = logging.getLogger("agents.base")

# Strands SDK is optional -- agents degrade gracefully without it
try:
    from strands import Agent as StrandsAgent
    from strands.models import BedrockModel

    STRANDS_AVAILABLE = True
except ImportError:
    StrandsAgent = None  # type: ignore[assignment, misc]
    BedrockModel = None  # type: ignore[assignment, misc]
    STRANDS_AVAILABLE = False


class BaseAgent:
    """Base class for all Gorilla Troop agents.

    Subclasses override `_execute()` to implement their stage-specific logic.
    The base class handles dispatch routing, retry, error reporting, and audit.

    When the Strands Agents SDK is installed, each agent creates a real
    ``strands.Agent`` backed by Amazon Bedrock (Claude Opus 4.6 via the
    ``ai3_d`` AWS profile).  Without Strands, agents still function but
    ``_invoke_llm()`` returns a placeholder response.
    """

    agent_type: str = "BaseAgent"
    agent_mail_identity: str = "BaseAgent"
    model_id: str = "us.anthropic.claude-opus-4-6-v1"

    # Subclasses set this to provide a system prompt for the Strands Agent
    system_prompt: str = ""

    def __init__(
        self,
        agent_type: str | None = None,
        model_id: str | None = None,
        mail_client: Any | None = None,
        engine: Any | None = None,
        bedrock_config: Any | None = None,
    ) -> None:
        if agent_type:
            self.agent_type = agent_type
            self.agent_mail_identity = agent_type
        if model_id:
            self.model_id = model_id
        self._mail = mail_client
        self._engine = engine
        self._tool_guard = ToolGuard()
        self._strands_agent: Any | None = None
        self._bedrock_config = bedrock_config

        if STRANDS_AVAILABLE and bedrock_config is not None:
            self._init_strands_agent(bedrock_config)

    async def handle_dispatch(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Main entry point: receive a dispatch, execute with retry, return completion.

        Args:
            dispatch: The dispatch message from Project Minder.

        Returns:
            CompletionMessage with results or error details.
        """
        logger.info(
            "[%s] Handling dispatch for stage '%s' (issue: %s)",
            self.agent_type,
            dispatch.stage_name,
            dispatch.beads_issue_id,
        )

        try:
            result = await with_retry(self._execute, dispatch)
            return result
        except Exception as e:
            logger.error(
                "[%s] Failed to execute stage '%s': %s",
                self.agent_type,
                dispatch.stage_name,
                e,
            )
            await self._report_error(e, dispatch)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary="",
                status="failed",
                error_detail=str(e),
            )

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Subclass override: perform the actual stage work.

        Args:
            dispatch: The dispatch message.

        Returns:
            CompletionMessage with results.
        """
        raise NotImplementedError(
            f"{self.agent_type} must implement _execute()"
        )

    async def _load_context(self, dispatch: DispatchMessage) -> str:
        """Load input artifacts and reference docs into a context string.

        Args:
            dispatch: The dispatch message containing artifact paths.

        Returns:
            Concatenated content of all input artifacts and reference docs.
        """
        from pathlib import Path

        parts: list[str] = []
        all_paths = dispatch.input_artifacts + dispatch.reference_docs

        for artifact_path in all_paths:
            path = Path(dispatch.workspace_root) / artifact_path
            if path.exists():
                content = path.read_text(encoding="utf-8")
                parts.append(f"--- {artifact_path} ---\n{content}\n")
            else:
                parts.append(f"--- {artifact_path} --- (not found)\n")

        return "\n".join(parts)

    async def _report_error(
        self, error: Exception, dispatch: DispatchMessage
    ) -> None:
        """Send error report to Curious George via Agent Mail.

        Args:
            error: The exception that occurred.
            dispatch: The dispatch context.
        """
        if self._mail:
            try:
                self._mail.send_message(
                    dispatch.project_key,
                    self.agent_mail_identity,
                    ["CuriousGeorge"],
                    f"[ERROR] {self.agent_type}: {type(error).__name__}",
                    (
                        f"**Agent**: {self.agent_type}\n"
                        f"**Stage**: {dispatch.stage_name}\n"
                        f"**Issue**: {dispatch.beads_issue_id}\n"
                        f"**Error**: {error}\n"
                    ),
                    thread_id=f"{dispatch.beads_issue_id}-error",
                    importance="high",
                )
            except Exception as mail_err:
                logger.warning("Failed to send error report to CuriousGeorge: %s", mail_err)

    def _init_strands_agent(self, bedrock_config: Any) -> None:
        """Initialize the underlying Strands Agent with Bedrock model.

        Args:
            bedrock_config: A BedrockConfig instance from orchestrator.config.
        """
        if not STRANDS_AVAILABLE:
            logger.warning(
                "[%s] strands-agents not installed -- LLM calls disabled",
                self.agent_type,
            )
            return

        try:
            model = bedrock_config.create_bedrock_model()
            self._strands_agent = StrandsAgent(
                model=model,
                system_prompt=self.system_prompt or f"You are {self.agent_type}, a Gorilla Troop agent.",
                callback_handler=None,
            )
            logger.info(
                "[%s] Strands agent initialized (model=%s, profile=%s)",
                self.agent_type,
                bedrock_config.model_id,
                bedrock_config.aws_profile,
            )
        except Exception as e:
            logger.error(
                "[%s] Failed to initialize Strands agent: %s", self.agent_type, e
            )
            self._strands_agent = None

    async def _invoke_llm(self, prompt: str) -> str:
        """Send a prompt to the Strands Agent and return the text response.

        If Strands is not available or not initialized, returns a placeholder.

        Args:
            prompt: The full prompt to send to the LLM.

        Returns:
            The LLM's text response.
        """
        if self._strands_agent is None:
            logger.info(
                "[%s] No Strands agent -- returning placeholder response",
                self.agent_type,
            )
            return f"[{self.agent_type} placeholder] Strands agent not initialized."

        import asyncio

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._strands_agent, prompt)
        response_text = str(result)
        logger.info(
            "[%s] LLM response received (%d chars)",
            self.agent_type,
            len(response_text),
        )
        return response_text

    def _get_tools(self) -> list[str]:
        """Return tool names this agent is authorized to use."""
        return self._tool_guard.get_allowed_tools(self.agent_type)

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if this agent is authorized to use a specific tool."""
        return self._tool_guard.validate_tool_access(self.agent_type, tool_name)
