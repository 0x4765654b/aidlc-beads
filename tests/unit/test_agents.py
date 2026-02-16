"""Unit tests for the Agent Definitions (Unit 5)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from orchestrator.agents.base import BaseAgent
from orchestrator.agents.retry import with_retry, MAX_RETRIES
from orchestrator.agents.tool_registry import ToolGuard, AGENT_TOOL_REGISTRY
from orchestrator.agents.chimps.base_chimp import BaseChimp
from orchestrator.agents.chimps.scout import Scout
from orchestrator.agents.chimps.sage import Sage
from orchestrator.agents.chimps.bard import Bard
from orchestrator.agents.chimps.planner import Planner
from orchestrator.agents.chimps.architect import Architect
from orchestrator.agents.chimps.steward import Steward
from orchestrator.agents.chimps.forge import Forge
from orchestrator.agents.chimps.crucible import Crucible
from orchestrator.agents.cross_cutting.bonobo_agent import BonoboAgent
from orchestrator.agents.cross_cutting.groomer import Groomer
from orchestrator.agents.cross_cutting.snake import Snake
from orchestrator.agents.cross_cutting.curious_george import CuriousGeorge
from orchestrator.agents.cross_cutting.gibbon import Gibbon
from orchestrator.agents.harmbe import Harmbe
from orchestrator.agents.project_minder import ProjectMinder
from orchestrator.agents.troop import Troop
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    build_dispatch,
    build_completion,
)


# ---------------------------------------------------------------------------
# Tool Registry tests
# ---------------------------------------------------------------------------


class TestToolGuard:
    def test_scout_allowed_tools(self):
        guard = ToolGuard()
        assert guard.validate_tool_access("Scout", "read_file") is True
        assert guard.validate_tool_access("Scout", "scribe_create_artifact") is True

    def test_scout_denied_tools(self):
        guard = ToolGuard()
        assert guard.validate_tool_access("Scout", "write_code_file") is False
        assert guard.validate_tool_access("Scout", "git_commit") is False

    def test_forge_has_write_tools(self):
        guard = ToolGuard()
        assert guard.validate_tool_access("Forge", "write_code_file") is True
        assert guard.validate_tool_access("Forge", "git_commit") is True

    def test_harmbe_no_code_tools(self):
        guard = ToolGuard()
        assert guard.validate_tool_access("Harmbe", "write_code_file") is False
        assert guard.validate_tool_access("Harmbe", "project_create") is True

    def test_all_agents_registered(self):
        expected_agents = [
            "Scout", "Sage", "Bard", "Planner", "Architect",
            "Steward", "Forge", "Crucible", "Harmbe", "ProjectMinder",
            "Bonobo", "Groomer", "Snake", "CuriousGeorge", "Gibbon", "Troop",
        ]
        for agent in expected_agents:
            assert agent in AGENT_TOOL_REGISTRY, f"Missing registry for {agent}"

    def test_get_allowed_tools(self):
        guard = ToolGuard()
        tools = guard.get_allowed_tools("Scout")
        assert "read_file" in tools
        assert len(tools) > 0

    def test_unknown_agent_gets_empty(self):
        guard = ToolGuard()
        assert guard.validate_tool_access("NonExistent", "read_file") is False
        assert guard.get_allowed_tools("NonExistent") == []


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestRetry:
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        call_count = 0

        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await with_retry(success)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        result = await with_retry(flaky, base_delay=0.01)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        async def always_fail():
            raise TimeoutError("always fails")

        with pytest.raises(TimeoutError):
            await with_retry(always_fail, max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_non_transient_not_retried(self):
        call_count = 0

        async def value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not transient")

        with pytest.raises(ValueError):
            await with_retry(value_error, base_delay=0.01)
        assert call_count == 1


# ---------------------------------------------------------------------------
# BaseAgent tests
# ---------------------------------------------------------------------------


class TestBaseAgent:
    def test_default_config(self):
        agent = BaseAgent(agent_type="TestAgent")
        assert agent.agent_type == "TestAgent"
        assert agent.model_id == "us.anthropic.claude-opus-4-6-v1"

    def test_can_use_tool(self):
        agent = BaseAgent(agent_type="Scout")
        assert agent.can_use_tool("read_file") is True
        assert agent.can_use_tool("git_commit") is False

    def test_get_tools(self):
        agent = BaseAgent(agent_type="Forge")
        tools = agent._get_tools()
        assert "write_code_file" in tools
        assert "git_commit" in tools

    @pytest.mark.asyncio
    async def test_handle_dispatch_not_implemented(self):
        agent = BaseAgent(agent_type="TestAgent")
        dispatch = build_dispatch(
            "test-stage", "gt-1", "test-project", "/workspace"
        )
        result = await agent.handle_dispatch(dispatch)
        assert result.status == "failed"
        assert "not implemented" in (result.error_detail or "").lower() or "must implement" in (result.error_detail or "").lower()

    @pytest.mark.asyncio
    async def test_error_reporting(self):
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        agent = BaseAgent(agent_type="TestAgent", mail_client=mock_mail)

        dispatch = build_dispatch("test", "gt-1", "project", "/workspace")
        await agent._report_error(ValueError("test error"), dispatch)
        mock_mail.send_message.assert_called_once()
        call_args = mock_mail.send_message.call_args
        assert "CuriousGeorge" in call_args[0][2]  # to_agents


# ---------------------------------------------------------------------------
# Chimp instantiation tests
# ---------------------------------------------------------------------------


class TestChimpAgents:
    def test_scout_stages(self):
        scout = Scout()
        assert scout.agent_type == "Scout"
        assert scout.can_handle_stage("workspace-detection")
        assert scout.can_handle_stage("reverse-engineering")
        assert not scout.can_handle_stage("code-generation")

    def test_sage_stages(self):
        sage = Sage()
        assert sage.can_handle_stage("requirements-analysis")
        assert sage.can_handle_stage("functional-design")

    def test_bard_stages(self):
        bard = Bard()
        assert bard.can_handle_stage("user-stories")

    def test_planner_stages(self):
        planner = Planner()
        assert planner.can_handle_stage("workflow-planning")
        assert planner.can_handle_stage("units-generation")

    def test_architect_stages(self):
        architect = Architect()
        assert architect.can_handle_stage("application-design")
        assert architect.can_handle_stage("infrastructure-design")

    def test_steward_stages(self):
        steward = Steward()
        assert steward.can_handle_stage("nfr-requirements")
        assert steward.can_handle_stage("nfr-design")

    def test_forge_stages(self):
        forge = Forge()
        assert forge.can_handle_stage("code-generation")

    def test_crucible_stages(self):
        crucible = Crucible()
        assert crucible.can_handle_stage("build-and-test")

    @pytest.mark.asyncio
    async def test_chimp_dispatch_returns_completion(self):
        scout = Scout()
        dispatch = build_dispatch(
            "reverse-engineering", "gt-15", "gorilla-troop", "/workspace"
        )
        result = await scout.handle_dispatch(dispatch)
        assert result.status == "completed"
        assert "Scout" in result.summary


# ---------------------------------------------------------------------------
# Cross-cutting agent tests
# ---------------------------------------------------------------------------


class TestCrossCuttingAgents:
    def test_bonobo_type(self):
        bonobo = BonoboAgent()
        assert bonobo.agent_type == "Bonobo"

    def test_groomer_type(self):
        groomer = Groomer()
        assert groomer.agent_type == "Groomer"

    def test_snake_type(self):
        snake = Snake()
        assert snake.agent_type == "Snake"

    def test_curious_george_type(self):
        cg = CuriousGeorge()
        assert cg.agent_type == "CuriousGeorge"

    def test_gibbon_type(self):
        gibbon = Gibbon()
        assert gibbon.agent_type == "Gibbon"


# ---------------------------------------------------------------------------
# Top-level agent tests
# ---------------------------------------------------------------------------


class TestTopLevelAgents:
    def test_harmbe_type(self):
        harmbe = Harmbe()
        assert harmbe.agent_type == "Harmbe"
        assert harmbe.agent_mail_identity == "Harmbe"
        assert harmbe.can_use_tool("project_create")
        assert not harmbe.can_use_tool("write_code_file")

    def test_project_minder_type(self):
        pm = ProjectMinder()
        assert pm.agent_type == "ProjectMinder"
        assert pm.can_use_tool("dispatch_stage")

    def test_troop_unique_identity(self):
        t1 = Troop()
        t2 = Troop()
        assert t1.agent_mail_identity != t2.agent_mail_identity
        assert t1.agent_mail_identity.startswith("Troop-")
        assert t2.agent_mail_identity.startswith("Troop-")


# ---------------------------------------------------------------------------
# Integration: all 16 agents instantiate
# ---------------------------------------------------------------------------


class TestAllAgentsInstantiate:
    def test_all_16_agents(self):
        """Verify all 16 agent types can be instantiated."""
        agents = [
            Scout(), Sage(), Bard(), Planner(),
            Architect(), Steward(), Forge(), Crucible(),
            BonoboAgent(), Groomer(), Snake(),
            CuriousGeorge(), Gibbon(),
            Harmbe(), ProjectMinder(), Troop(),
        ]
        assert len(agents) == 16
        types = {a.agent_type for a in agents}
        expected = {
            "Scout", "Sage", "Bard", "Planner",
            "Architect", "Steward", "Forge", "Crucible",
            "Bonobo", "Groomer", "Snake",
            "CuriousGeorge", "Gibbon",
            "Harmbe", "ProjectMinder", "Troop",
        }
        assert types == expected
