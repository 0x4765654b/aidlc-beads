"""Gorilla Troop wiring -- connects agents, engine, and Bedrock configuration.

This module is the integration point that creates real Strands-backed agents
and registers them with the AgentEngine. Import and call ``wire_engine()``
at application startup.
"""

from __future__ import annotations

import logging
from typing import Any

from orchestrator.config import BedrockConfig, get_config
from orchestrator.engine.agent_engine import AgentEngine, AgentInstance
from orchestrator.agents.base import BaseAgent, STRANDS_AVAILABLE
from orchestrator.agents.harmbe import Harmbe
from orchestrator.agents.project_minder import ProjectMinder
from orchestrator.agents.troop import Troop
from orchestrator.agents.chimps.scout import Scout
from orchestrator.agents.chimps.sage import Sage
from orchestrator.agents.chimps.bard import Bard
from orchestrator.agents.chimps.planner import Planner
from orchestrator.agents.chimps.architect import Architect
from orchestrator.agents.chimps.steward import Steward
from orchestrator.agents.chimps.forge import Forge
from orchestrator.agents.chimps.crucible import Crucible

logger = logging.getLogger("wiring")

# All agent classes keyed by their agent_type
AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "Harmbe": Harmbe,
    "ProjectMinder": ProjectMinder,
    "Scout": Scout,
    "Sage": Sage,
    "Bard": Bard,
    "Planner": Planner,
    "Architect": Architect,
    "Steward": Steward,
    "Forge": Forge,
    "Crucible": Crucible,
    "Troop": Troop,
}


def create_agent(
    agent_type: str,
    bedrock_config: BedrockConfig | None = None,
    mail_client: Any | None = None,
    engine: Any | None = None,
) -> BaseAgent:
    """Create an agent instance with Strands/Bedrock wiring.

    Args:
        agent_type: The agent role name (e.g., "Harmbe", "Scout").
        bedrock_config: Bedrock configuration. Uses global config if None.
        mail_client: Optional Agent Mail client for inter-agent messaging.
        engine: Optional reference to the AgentEngine.

    Returns:
        A configured BaseAgent subclass instance.

    Raises:
        ValueError: If agent_type is not in the registry.
    """
    cls = AGENT_CLASSES.get(agent_type)
    if cls is None:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Available: {', '.join(sorted(AGENT_CLASSES.keys()))}"
        )

    config = bedrock_config or get_config().bedrock
    return cls(
        mail_client=mail_client,
        engine=engine,
        bedrock_config=config,
    )


def _make_runner(
    agent_type: str,
    bedrock_config: BedrockConfig,
    mail_client: Any | None = None,
):
    """Create an AgentRunner closure for a given agent type.

    The runner creates a fresh agent instance per invocation, so each
    task gets its own Strands Agent and conversation context.
    """

    async def runner(instance: AgentInstance, context: dict) -> dict:
        from orchestrator.lib.context.dispatch import DispatchMessage

        agent = create_agent(
            agent_type,
            bedrock_config=bedrock_config,
            mail_client=mail_client,
        )

        dispatch = context.get("dispatch")
        if dispatch and isinstance(dispatch, DispatchMessage):
            completion = await agent.handle_dispatch(dispatch)
            return {
                "status": completion.status,
                "summary": completion.summary,
                "output_artifacts": completion.output_artifacts,
            }

        # Simple prompt mode (e.g., for Harmbe chat)
        prompt = context.get("prompt", "")
        if prompt:
            response = await agent._invoke_llm(prompt)
            return {"response": response}

        return {"error": "No dispatch or prompt in context"}

    return runner


def wire_engine(
    engine: AgentEngine,
    bedrock_config: BedrockConfig | None = None,
    mail_client: Any | None = None,
) -> None:
    """Register all agent runners with the engine.

    Call this at application startup to connect the AgentEngine
    to real Strands-backed agent implementations.

    Args:
        engine: The AgentEngine instance to configure.
        bedrock_config: Bedrock configuration. Uses global config if None.
        mail_client: Optional Agent Mail client.
    """
    config = bedrock_config or get_config().bedrock

    logger.info(
        "Wiring engine: model=%s, profile=%s, strands=%s",
        config.model_id,
        config.aws_profile,
        STRANDS_AVAILABLE,
    )

    for agent_type in AGENT_CLASSES:
        runner = _make_runner(agent_type, config, mail_client)
        engine.register_runner(agent_type, runner)
        logger.debug("Registered runner for %s", agent_type)

    logger.info("Engine wired with %d agent types", len(AGENT_CLASSES))
