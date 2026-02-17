"""Agent Engine -- lifecycle management for agent instances."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("engine.agent_engine")


@dataclass
class EngineConfig:
    """Configuration for the Agent Engine."""

    max_concurrent_agents: int = 4
    agent_timeout_seconds: int = 3600  # 1 hour
    model_id: str = "anthropic.claude-opus-4-6"
    aws_region: str = "us-east-1"


@dataclass
class AgentInstance:
    """A running agent instance."""

    agent_id: str
    agent_type: str
    status: str = "starting"  # starting, running, stopping, stopped, error
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    project_key: str = ""
    current_task: str | None = None  # Beads issue ID

    def is_active(self) -> bool:
        return self.status in ("starting", "running")


# Type alias for the agent execution function
AgentRunner = Callable[[AgentInstance, dict], Coroutine[Any, Any, dict]]


class AgentEngine:
    """Manages agent lifecycle: spawn, track, and stop agent instances.

    Uses asyncio for concurrent agent management with a configurable
    concurrency limit.
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        self._agents: dict[str, AgentInstance] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_agents)
        self._shutdown_event = asyncio.Event()
        self._runners: dict[str, AgentRunner] = {}

    def register_runner(self, agent_type: str, runner: AgentRunner) -> None:
        """Register an execution function for an agent type.

        Args:
            agent_type: The agent role name (e.g., "Scout").
            runner: Async function that executes the agent's work.
        """
        self._runners[agent_type] = runner

    async def spawn_agent(
        self,
        agent_type: str,
        context: dict,
        *,
        project_key: str = "",
        task_id: str | None = None,
    ) -> AgentInstance:
        """Spawn a new agent instance for a task.

        Args:
            agent_type: The agent role (e.g., "Scout", "Forge").
            context: Configuration dict including dispatch message.
            project_key: Project this agent belongs to.
            task_id: Beads issue ID being worked on.

        Returns:
            AgentInstance handle.

        Raises:
            RuntimeError: If engine is shutting down.
        """
        if self._shutdown_event.is_set():
            raise RuntimeError("Engine is shutting down, cannot spawn new agents")

        agent_id = f"{agent_type.lower()}-{uuid.uuid4().hex[:8]}"
        instance = AgentInstance(
            agent_id=agent_id,
            agent_type=agent_type,
            status="starting",
            project_key=project_key,
            current_task=task_id,
        )

        self._agents[agent_id] = instance

        # Create the async task
        task = asyncio.create_task(self._run_agent(instance, context))
        self._tasks[agent_id] = task

        logger.info("Spawned agent %s (type=%s, task=%s)", agent_id, agent_type, task_id)
        return instance

    async def _run_agent(self, instance: AgentInstance, context: dict) -> dict:
        """Internal: execute an agent within the concurrency semaphore."""
        await self._semaphore.acquire()
        try:
            instance.status = "running"
            logger.info("Agent %s now running", instance.agent_id)

            runner = self._runners.get(instance.agent_type)
            if runner is None:
                raise RuntimeError(f"No runner registered for agent type: {instance.agent_type}")

            # Run with timeout
            result = await asyncio.wait_for(
                runner(instance, context),
                timeout=self._config.agent_timeout_seconds,
            )

            instance.status = "stopped"
            logger.info("Agent %s completed", instance.agent_id)
            return result

        except asyncio.TimeoutError:
            instance.status = "error"
            logger.error("Agent %s timed out after %ds", instance.agent_id, self._config.agent_timeout_seconds)
            return {"error": "timeout"}

        except Exception as e:
            instance.status = "error"
            logger.error("Agent %s failed: %s", instance.agent_id, e, exc_info=True)
            return {"error": str(e)}

        finally:
            self._semaphore.release()

    async def stop_agent(self, agent_id: str, reason: str = "") -> None:
        """Gracefully stop an agent instance.

        Args:
            agent_id: The agent to stop.
            reason: Reason for stopping.
        """
        instance = self._agents.get(agent_id)
        if not instance:
            return

        instance.status = "stopping"
        task = self._tasks.get(agent_id)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        instance.status = "stopped"
        logger.info("Stopped agent %s: %s", agent_id, reason)

    def get_agent(self, agent_id: str) -> AgentInstance | None:
        """Get an active agent by ID."""
        return self._agents.get(agent_id)

    def list_active(self) -> list[AgentInstance]:
        """List all currently active agents."""
        return [a for a in self._agents.values() if a.is_active()]

    def list_all(self) -> list[AgentInstance]:
        """List all agents (including stopped)."""
        return list(self._agents.values())

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shut down all agents.

        Args:
            timeout: Maximum seconds to wait for agents to finish.
        """
        self._shutdown_event.set()
        logger.info("Engine shutdown initiated, waiting up to %.0fs for active agents", timeout)

        active_tasks = [t for t in self._tasks.values() if not t.done()]
        if active_tasks:
            done, pending = await asyncio.wait(active_tasks, timeout=timeout)
            for task in pending:
                task.cancel()

        # Mark all remaining as stopped
        for instance in self._agents.values():
            if instance.is_active():
                instance.status = "stopped"

        logger.info("Engine shutdown complete. %d agents processed.", len(self._agents))
