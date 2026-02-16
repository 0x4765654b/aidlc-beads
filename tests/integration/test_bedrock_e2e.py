"""End-to-end integration test: Agent Engine + Strands + Bedrock.

Requires:
- AWS profile 'ai3_d' configured with Bedrock access
- Network access to Amazon Bedrock

Run with: pytest tests/integration/ -v --timeout=120
"""

from __future__ import annotations

import asyncio
import os

import pytest

from orchestrator.config import BedrockConfig, reset_config
from orchestrator.agents.base import BaseAgent, STRANDS_AVAILABLE
from orchestrator.agents.harmbe import Harmbe
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.wiring import wire_engine, create_agent

# Skip all tests if strands not installed or no AWS profile
pytestmark = [
    pytest.mark.skipif(
        not STRANDS_AVAILABLE,
        reason="strands-agents not installed",
    ),
    pytest.mark.skipif(
        os.environ.get("SKIP_BEDROCK_TESTS", "0") == "1",
        reason="SKIP_BEDROCK_TESTS=1",
    ),
]


@pytest.fixture
def bedrock_config():
    reset_config()
    return BedrockConfig(
        aws_profile="ai3_d",
        aws_region="us-east-1",
        model_id="us.anthropic.claude-opus-4-6-v1",
        max_tokens=200,
    )


class TestBedrockConnectivity:
    """Verify basic Bedrock connectivity via Strands."""

    def test_create_bedrock_model(self, bedrock_config):
        model = bedrock_config.create_bedrock_model()
        assert model is not None

    def test_create_boto_session(self, bedrock_config):
        session = bedrock_config.create_boto_session()
        assert session.profile_name == "ai3_d"
        assert session.region_name == "us-east-1"


class TestAgentWithBedrock:
    """Test that agents can invoke the LLM."""

    @pytest.mark.asyncio
    async def test_harmbe_invoke_llm(self, bedrock_config):
        agent = Harmbe(bedrock_config=bedrock_config)
        response = await agent._invoke_llm(
            "Reply with exactly: Harmbe reporting. Nothing else."
        )
        assert "Harmbe" in response or "reporting" in response.lower()

    @pytest.mark.asyncio
    async def test_base_agent_invoke_llm(self, bedrock_config):
        agent = BaseAgent(
            agent_type="TestAgent",
            bedrock_config=bedrock_config,
        )
        response = await agent._invoke_llm("Reply with exactly: test OK")
        assert len(response) > 0


class TestCreateAgent:
    """Test the create_agent factory."""

    def test_create_harmbe(self, bedrock_config):
        agent = create_agent("Harmbe", bedrock_config=bedrock_config)
        assert isinstance(agent, Harmbe)
        assert agent._strands_agent is not None

    def test_create_unknown_raises(self, bedrock_config):
        with pytest.raises(ValueError, match="Unknown agent type"):
            create_agent("Nonexistent", bedrock_config=bedrock_config)


class TestEngineWiring:
    """Test full engine wiring with Bedrock."""

    @pytest.mark.asyncio
    async def test_wire_and_spawn(self, bedrock_config):
        engine = AgentEngine()
        wire_engine(engine, bedrock_config=bedrock_config)

        instance = await engine.spawn_agent(
            "Harmbe",
            context={"prompt": "Reply with exactly: engine test OK"},
            project_key="test",
        )
        assert instance.agent_type == "Harmbe"

        # Wait for completion (with timeout)
        for _ in range(30):
            await asyncio.sleep(1)
            if not instance.is_active():
                break

        assert instance.status in ("stopped", "error")

        # Shutdown
        await engine.shutdown()
