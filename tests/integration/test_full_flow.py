"""Integration tests for the full Gorilla Troop multi-agent orchestration flow.

Tests the end-to-end interactions between API, Engine, Agents, Dispatch, and
Completion without requiring Bedrock access.  All LLM calls and Beads CLI
calls are mocked.

Run with: pytest tests/integration/test_full_flow.py -v
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from orchestrator.api.app import create_app
from orchestrator.engine.agent_engine import AgentEngine, AgentInstance, EngineConfig
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.notification_manager import NotificationManager
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_dispatch,
    build_completion,
)
from orchestrator.agents.base import BaseAgent
from orchestrator.agents.chimps.base_chimp import BaseChimp
from orchestrator.agents.chimps.scout import Scout
from orchestrator.agents.chimps.sage import Sage
from orchestrator.agents.chimps.forge import Forge
from orchestrator.agents.harmbe import Harmbe
from orchestrator.agents.project_minder import ProjectMinder
from orchestrator.agents.cross_cutting.curious_george import CuriousGeorge
from orchestrator.agents.cross_cutting.gibbon import Gibbon, MAX_REWORK_ITERATIONS
from orchestrator.wiring import wire_engine, create_agent, AGENT_CLASSES
from orchestrator.lib.beads.models import BeadsIssue


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_beads_issue(
    issue_id: str = "gt-5",
    title: str = "Requirements Analysis",
    status: str = "open",
    labels: list[str] | None = None,
    notes: str | None = None,
    description: str | None = None,
) -> BeadsIssue:
    """Build a synthetic BeadsIssue for testing."""
    return BeadsIssue(
        id=issue_id,
        title=title,
        status=status,
        labels=labels or [],
        notes=notes,
        description=description,
    )


# ---------------------------------------------------------------------------
# 1. TestFullDispatchFlow
# ---------------------------------------------------------------------------


class TestFullDispatchFlow:
    """Complete dispatch -> agent -> completion cycle."""

    @pytest.mark.asyncio
    async def test_dispatch_through_engine_to_scout(self):
        """Spawn Scout via engine, verify dispatch produces completion."""
        engine = AgentEngine(EngineConfig(max_concurrent_agents=2))

        async def mock_scout_runner(instance: AgentInstance, context: dict) -> dict:
            dispatch = context.get("dispatch")
            if dispatch and isinstance(dispatch, DispatchMessage):
                scout = Scout()
                with patch.object(
                    scout, "_invoke_llm", new_callable=AsyncMock,
                    return_value="artifact: aidlc-docs/inception/workspace/workspace.md\nWorkspace scanned.",
                ):
                    completion = await scout.handle_dispatch(dispatch)
                return {
                    "status": completion.status,
                    "summary": completion.summary,
                    "output_artifacts": completion.output_artifacts,
                }
            return {"error": "no dispatch"}

        engine.register_runner("Scout", mock_scout_runner)

        dispatch = build_dispatch(
            stage_name="workspace-detection",
            beads_issue_id="gt-3",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
        )

        instance = await engine.spawn_agent(
            "Scout",
            context={"dispatch": dispatch},
            project_key="test-proj",
            task_id="gt-3",
        )

        assert instance.agent_type == "Scout"
        assert instance.current_task == "gt-3"

        # Wait for completion
        for _ in range(20):
            await asyncio.sleep(0.05)
            if not instance.is_active():
                break

        assert instance.status == "stopped"

    @pytest.mark.asyncio
    async def test_wired_engine_dispatch_flow(self):
        """Wire all agents into the engine and dispatch to Sage."""
        engine = AgentEngine(EngineConfig(max_concurrent_agents=4))

        # Wire engine -- Strands is not available so agents use placeholders
        with patch("orchestrator.wiring.get_config") as mock_config:
            mock_bedrock = MagicMock()
            mock_bedrock.model_id = "test-model"
            mock_bedrock.aws_profile = "test"
            mock_config.return_value.bedrock = mock_bedrock
            wire_engine(engine, bedrock_config=mock_bedrock)

        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
        )

        instance = await engine.spawn_agent(
            "Sage",
            context={"dispatch": dispatch},
            project_key="test-proj",
            task_id="gt-5",
        )

        for _ in range(30):
            await asyncio.sleep(0.05)
            if not instance.is_active():
                break

        assert instance.status == "stopped"
        await engine.shutdown(timeout=2.0)

    @pytest.mark.asyncio
    async def test_chimp_handle_dispatch_produces_completion(self):
        """Directly invoke a chimp's handle_dispatch and verify CompletionMessage."""
        sage = Sage()
        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
        )

        with patch.object(
            sage, "_invoke_llm", new_callable=AsyncMock,
            return_value=(
                "Requirements document generated.\n"
                "artifact: aidlc-docs/inception/requirements/requirements.md\n"
                "15 functional requirements and 8 non-functional requirements."
            ),
        ):
            completion = await sage.handle_dispatch(dispatch)

        assert isinstance(completion, CompletionMessage)
        assert completion.status == "completed"
        assert completion.beads_issue_id == "gt-5"
        assert completion.stage_name == "requirements-analysis"
        assert "aidlc-docs/inception/requirements/requirements.md" in completion.output_artifacts

    @pytest.mark.asyncio
    async def test_dispatch_to_forge_code_generation(self):
        """Forge processes a code-generation dispatch and returns artifacts."""
        forge = Forge()
        dispatch = build_dispatch(
            stage_name="code-generation",
            beads_issue_id="gt-19",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
            phase="construction",
            unit_name="unit-1-scribe",
            input_artifacts=["aidlc-docs/construction/unit-1-scribe/functional-design.md"],
        )

        with patch.object(
            forge, "_invoke_llm", new_callable=AsyncMock,
            return_value=(
                "Code generation complete.\n"
                "Created artifact at: orchestrator/lib/scribe/workspace.py\n"
                "Created artifact at: orchestrator/lib/scribe/models.py\n"
                "All modules compile and pass linting."
            ),
        ):
            completion = await forge.handle_dispatch(dispatch)

        assert completion.status == "completed"
        assert len(completion.output_artifacts) >= 1


# ---------------------------------------------------------------------------
# 2. TestReviewGateLifecycle
# ---------------------------------------------------------------------------


class TestReviewGateLifecycle:
    """Review gate creation, approval, rejection via the API."""

    @pytest.fixture
    def engine(self) -> AgentEngine:
        eng = AgentEngine()
        # Register a no-op Gibbon runner so reject can spawn it
        async def noop_runner(instance: AgentInstance, context: dict) -> dict:
            return {"status": "completed"}
        eng.register_runner("Gibbon", noop_runner)
        return eng

    @pytest.fixture
    def app(self, tmp_path: Path, engine):
        registry = ProjectRegistry(workspace_root=tmp_path)
        notif_mgr = NotificationManager()
        return create_app(
            project_registry=registry,
            agent_engine=engine,
            notification_manager=notif_mgr,
        )

    @pytest_asyncio.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_list_review_gates_with_mocked_beads(self, client: AsyncClient):
        """List review gates when Beads returns open review-gate issues."""
        mock_issue = _make_beads_issue(
            issue_id="gt-42",
            title="REVIEW: Requirements Analysis - Awaiting Approval",
            status="open",
            labels=["type:review-gate", "phase:inception"],
            notes="artifact: aidlc-docs/inception/requirements/requirements.md",
        )
        mock_beads = MagicMock()
        mock_beads.list_issues = MagicMock(return_value=[mock_issue])

        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads):
            resp = await client.get("/api/review/")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["issue_id"] == "gt-42"
        assert data[0]["stage_name"] == "Requirements Analysis"

    @pytest.mark.asyncio
    async def test_approve_review_updates_beads(self, client: AsyncClient):
        """Approve a review gate, verify Beads is updated and mail sent."""
        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=_make_beads_issue("gt-42"))
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads), \
             patch("orchestrator.api.routes.review.get_mail_client", return_value=mock_mail):
            resp = await client.post(
                "/api/review/gt-42/approve",
                json={"feedback": "Looks great, approved!"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"
        assert data["issue_id"] == "gt-42"

        mock_beads.update_issue.assert_called_once()
        call_kwargs = mock_beads.update_issue.call_args
        assert call_kwargs[0][0] == "gt-42"

    @pytest.mark.asyncio
    async def test_reject_review_spawns_gibbon(self, client: AsyncClient, engine: AgentEngine):
        """Reject a review gate, verify Gibbon rework agent is spawned."""
        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=_make_beads_issue(
            "gt-42",
            notes="artifact: aidlc-docs/inception/requirements/requirements.md",
        ))

        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads):
            resp = await client.post(
                "/api/review/gt-42/reject",
                json={"feedback": "Section 3 needs more detail on auth requirements."},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "rejected"
        assert data["next_action"] == "dispatched_rework"

        # Verify Gibbon was spawned
        await asyncio.sleep(0.2)
        all_agents = engine.list_all()
        gibbon_agents = [a for a in all_agents if a.agent_type == "Gibbon"]
        assert len(gibbon_agents) >= 1

    @pytest.mark.asyncio
    async def test_approve_then_unblock_advances_workflow(self, client: AsyncClient):
        """Approve triggers beads update that would unblock downstream stages."""
        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=_make_beads_issue("gt-42"))
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads), \
             patch("orchestrator.api.routes.review.get_mail_client", return_value=mock_mail):
            resp = await client.post(
                "/api/review/gt-42/approve",
                json={"feedback": ""},
            )

        assert resp.status_code == 200
        # Mail should notify ProjectMinder
        mock_mail.send_message.assert_called_once()
        call_args = mock_mail.send_message.call_args
        assert "ProjectMinder" in call_args[0][2]  # recipients


# ---------------------------------------------------------------------------
# 3. TestQALifecycle
# ---------------------------------------------------------------------------


class TestQALifecycle:
    """Q&A question routing and answering flow."""

    @pytest.fixture
    def app(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        engine = AgentEngine()
        notif_mgr = NotificationManager()
        return create_app(
            project_registry=registry,
            agent_engine=engine,
            notification_manager=notif_mgr,
        )

    @pytest_asyncio.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_list_questions_from_beads(self, client: AsyncClient):
        """List Q&A questions from mocked Beads state."""
        qa_issue = _make_beads_issue(
            issue_id="gt-10",
            title="QUESTION: requirements-analysis - Auth Method",
            status="open",
            labels=["type:qa"],
            description="Which authentication method?\n\nA) OAuth/SSO\nB) API Keys\nC) Both",
        )
        mock_beads = MagicMock()
        mock_beads.list_issues = MagicMock(return_value=[qa_issue])

        with patch("orchestrator.api.routes.questions.get_beads_client", return_value=mock_beads):
            resp = await client.get("/api/questions/")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["issue_id"] == "gt-10"

    @pytest.mark.asyncio
    async def test_answer_question_closes_issue(self, client: AsyncClient):
        """Answer a question, verify Beads issue is updated and closed."""
        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.close_issue = MagicMock()
        mock_beads.ready = MagicMock(return_value=[
            _make_beads_issue("gt-11", title="User Stories", status="open"),
        ])
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        with patch("orchestrator.api.routes.questions.get_beads_client", return_value=mock_beads), \
             patch("orchestrator.api.routes.questions.get_mail_client", return_value=mock_mail):
            resp = await client.post(
                "/api/questions/gt-10/answer",
                json={"answer": "A) OAuth/SSO"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["issue_id"] == "gt-10"
        assert data["answer"] == "A) OAuth/SSO"
        assert "gt-11" in data["unblocked_stages"]

        mock_beads.update_issue.assert_called_once_with(
            "gt-10", append_notes="ANSWER: A) OAuth/SSO"
        )
        mock_beads.close_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_answer_notifies_project_minder(self, client: AsyncClient):
        """After answering, Agent Mail notifies ProjectMinder of unblocked work."""
        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.close_issue = MagicMock()
        mock_beads.ready = MagicMock(return_value=[])
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        with patch("orchestrator.api.routes.questions.get_beads_client", return_value=mock_beads), \
             patch("orchestrator.api.routes.questions.get_mail_client", return_value=mock_mail):
            resp = await client.post(
                "/api/questions/gt-10/answer",
                json={"answer": "B) API Keys"},
            )

        assert resp.status_code == 200
        mock_mail.send_message.assert_called_once()
        call_args = mock_mail.send_message.call_args
        assert "ProjectMinder" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_answer_empty_rejected(self, client: AsyncClient):
        """Empty answer should be rejected with 422."""
        resp = await client.post(
            "/api/questions/gt-10/answer",
            json={"answer": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. TestChatFlow
# ---------------------------------------------------------------------------


class TestChatFlow:
    """Chat messages through Harmbe via the API."""

    @pytest.fixture
    def app(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        engine = AgentEngine()
        notif_mgr = NotificationManager()
        return create_app(
            project_registry=registry,
            agent_engine=engine,
            notification_manager=notif_mgr,
        )

    @pytest_asyncio.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_chat_invokes_harmbe(self, client: AsyncClient):
        """Chat message triggers Harmbe LLM invocation and returns response."""
        mock_response = "Hello! I am Harmbe, your project supervisor. How can I help?"

        with patch("orchestrator.api.routes.chat._get_harmbe") as mock_get:
            mock_harmbe = MagicMock()
            mock_harmbe._invoke_llm = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_harmbe

            resp = await client.post(
                "/api/chat/",
                json={"message": "What is the project status?", "project_key": "test-proj"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == mock_response
        assert data["message_id"].startswith("msg-")

    @pytest.mark.asyncio
    async def test_chat_history_tracks_messages(self, client: AsyncClient):
        """Chat history stores both user and assistant messages."""
        with patch("orchestrator.api.routes.chat._get_harmbe") as mock_get:
            mock_harmbe = MagicMock()
            mock_harmbe._invoke_llm = AsyncMock(return_value="Status looks good.")
            mock_get.return_value = mock_harmbe

            await client.post(
                "/api/chat/",
                json={"message": "Status please", "project_key": "hist-test"},
            )

        resp = await client.get("/api/chat/history?project_key=hist-test")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_without_strands_returns_placeholder(self, client: AsyncClient):
        """When Harmbe agent is unavailable, chat returns a placeholder."""
        with patch("orchestrator.api.routes.chat._get_harmbe", return_value=None):
            resp = await client.post(
                "/api/chat/",
                json={"message": "Hello", "project_key": "test"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "Acknowledged" in data["response"] or "not available" in data["response"]

    @pytest.mark.asyncio
    async def test_harmbe_execute_chat_action(self):
        """Directly invoke Harmbe._execute with chat action."""
        harmbe = Harmbe()
        with patch.object(
            harmbe, "_invoke_llm", new_callable=AsyncMock,
            return_value="Project is in inception phase with 3 stages complete.",
        ), patch.object(
            harmbe, "_get_project_state", new_callable=AsyncMock,
            return_value="**Total Issues**: 10\n**Done**: 3",
        ):
            result = await harmbe._execute({
                "action": "chat",
                "message": "What is the status?",
            })

        assert isinstance(result, str)
        assert "inception" in result.lower() or "phase" in result.lower()

    @pytest.mark.asyncio
    async def test_harmbe_execute_delegate_action(self):
        """Harmbe delegate action routes work to ProjectMinder."""
        harmbe = Harmbe()
        with patch.object(harmbe, "_send_notification", new_callable=AsyncMock):
            result = await harmbe._execute({
                "action": "delegate",
                "project_key": "test-proj",
                "stage_name": "requirements-analysis",
            })

        assert "Delegated" in result
        assert "requirements-analysis" in result


# ---------------------------------------------------------------------------
# 5. TestErrorEscalation
# ---------------------------------------------------------------------------


class TestErrorEscalation:
    """Error -> CuriousGeorge -> Harmbe escalation chain."""

    @pytest.mark.asyncio
    async def test_base_agent_reports_error_to_curious_george(self):
        """When an agent fails, _report_error sends mail to CuriousGeorge."""
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        agent = BaseAgent(agent_type="Sage", mail_client=mock_mail)

        dispatch = build_dispatch("requirements-analysis", "gt-5", "test-proj", "/workspace")
        await agent._report_error(ValueError("import error"), dispatch)

        mock_mail.send_message.assert_called_once()
        call_args = mock_mail.send_message.call_args
        assert "CuriousGeorge" in call_args[0][2]
        assert "ValueError" in call_args[0][3]

    @pytest.mark.asyncio
    async def test_handle_dispatch_failure_triggers_error_report(self):
        """handle_dispatch catches _execute failures and sends error report."""
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        agent = BaseAgent(agent_type="TestAgent", mail_client=mock_mail)

        dispatch = build_dispatch("test-stage", "gt-1", "test", "/workspace")
        completion = await agent.handle_dispatch(dispatch)

        assert completion.status == "failed"
        assert "must implement" in (completion.error_detail or "").lower() or \
               "not implemented" in (completion.error_detail or "").lower()
        mock_mail.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_curious_george_investigates_and_escalates(self):
        """CuriousGeorge receives error, investigates, escalates to Harmbe."""
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        cg = CuriousGeorge(mail_client=mock_mail)

        error_context = json.dumps({
            "error_message": "Bedrock throttling error",
            "source_agent": "Forge",
            "affected_issue_id": "gt-19",
        })

        dispatch = build_dispatch(
            stage_name="error-investigation",
            beads_issue_id="gt-19",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
            instructions=error_context,
        )

        # Mock LLM to return analysis that cannot fix the issue -> escalate
        escalation_response = json.dumps({
            "root_cause": "AWS Bedrock service throttling",
            "fix_suggested": False,
            "escalation_reason": "Throttling requires AWS account adjustment",
        })

        with patch.object(
            cg, "_invoke_llm", new_callable=AsyncMock,
            return_value=escalation_response,
        ), patch(
            "orchestrator.agents.cross_cutting.curious_george.show_issue",
            side_effect=Exception("beads unavailable"),
        ):
            completion = await cg._execute(dispatch)

        assert completion.status == "completed"
        assert "Escalated to Harmbe" in completion.summary

        # Verify mail was sent to Harmbe
        escalation_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "Harmbe" in c[0][2]
        ]
        assert len(escalation_calls) >= 1

    @pytest.mark.asyncio
    async def test_curious_george_suggests_fix_to_source_agent(self):
        """CuriousGeorge investigates and suggests a fix back to the source agent."""
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        cg = CuriousGeorge(mail_client=mock_mail)

        error_context = json.dumps({
            "error_message": "Missing beads header in artifact",
            "source_agent": "Sage",
            "affected_issue_id": "gt-5",
        })

        dispatch = build_dispatch(
            stage_name="error-investigation",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
            instructions=error_context,
        )

        fix_response = json.dumps({
            "root_cause": "Artifact missing required beads-issue header comment",
            "fix_suggested": True,
            "fix_description": "Add <!-- beads-issue: gt-5 --> header to requirements.md",
            "target_agent": "Sage",
        })

        with patch.object(
            cg, "_invoke_llm", new_callable=AsyncMock,
            return_value=fix_response,
        ), patch(
            "orchestrator.agents.cross_cutting.curious_george.show_issue",
            return_value=_make_beads_issue("gt-5", status="in_progress"),
        ):
            completion = await cg._execute(dispatch)

        assert completion.status == "completed"
        assert "Fix suggested" in completion.summary

        # Verify fix was sent to Sage, not escalated to Harmbe
        fix_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "Sage" in c[0][2]
        ]
        assert len(fix_calls) == 1

    @pytest.mark.asyncio
    async def test_full_escalation_chain_agent_to_george_to_harmbe(self):
        """End-to-end: Sage fails -> reports to CG -> CG escalates to Harmbe."""
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        # Step 1: Sage fails during dispatch
        sage = Sage(mail_client=mock_mail)

        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
        )

        with patch.object(
            sage, "_invoke_llm", new_callable=AsyncMock,
            side_effect=ConnectionError("Bedrock connection refused"),
        ):
            completion = await sage.handle_dispatch(dispatch)

        assert completion.status == "failed"
        # Sage reported error to CuriousGeorge
        sage_error_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "CuriousGeorge" in c[0][2]
        ]
        assert len(sage_error_calls) >= 1

        # Step 2: CuriousGeorge investigates
        cg = CuriousGeorge(mail_client=mock_mail)
        mock_mail.send_message.reset_mock()

        cg_dispatch = build_dispatch(
            stage_name="error-investigation",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
            instructions=json.dumps({
                "error_message": "Bedrock connection refused",
                "source_agent": "Sage",
                "affected_issue_id": "gt-5",
            }),
        )

        escalation_analysis = json.dumps({
            "root_cause": "Bedrock endpoint unreachable",
            "fix_suggested": False,
            "escalation_reason": "Infrastructure issue requires human intervention",
        })

        with patch.object(
            cg, "_invoke_llm", new_callable=AsyncMock,
            return_value=escalation_analysis,
        ), patch(
            "orchestrator.agents.cross_cutting.curious_george.show_issue",
            side_effect=Exception("beads unavailable"),
        ):
            cg_completion = await cg._execute(cg_dispatch)

        assert cg_completion.status == "completed"
        harmbe_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "Harmbe" in c[0][2]
        ]
        assert len(harmbe_calls) >= 1


# ---------------------------------------------------------------------------
# 6. TestReworkFlow
# ---------------------------------------------------------------------------


class TestReworkFlow:
    """Rejection -> Gibbon rework -> resubmission cycle."""

    @pytest.mark.asyncio
    async def test_gibbon_rework_succeeds(self, tmp_path: Path):
        """Gibbon reads artifact, applies corrections, writes corrected version."""
        # Create an artifact file
        artifact_dir = tmp_path / "aidlc-docs" / "inception" / "requirements"
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "requirements.md"
        artifact_file.write_text(
            "# Requirements\n\n## FR-001\nBasic login.\n",
            encoding="utf-8",
        )

        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        gibbon = Gibbon(mail_client=mock_mail)

        rework_instructions = json.dumps({
            "review_gate_id": "gt-42",
            "feedback": "FR-001 needs more detail on auth method and error handling.",
            "artifact_path": "aidlc-docs/inception/requirements/requirements.md",
            "retry_count": 0,
        })

        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root=str(tmp_path),
            instructions=rework_instructions,
        )

        corrected_content = (
            "# Requirements\n\n"
            "## FR-001\n"
            "Login with OAuth/SSO. On auth failure, display error code and retry prompt.\n"
        )

        with patch.object(
            gibbon, "_invoke_llm", new_callable=AsyncMock,
            return_value=corrected_content,
        ):
            completion = await gibbon._execute(dispatch)

        assert completion.status == "completed"
        assert "aidlc-docs/inception/requirements/requirements.md" in completion.output_artifacts
        assert "Rework iteration 1" in completion.summary

        # Verify the file was updated
        updated = artifact_file.read_text(encoding="utf-8")
        assert "OAuth/SSO" in updated

    @pytest.mark.asyncio
    async def test_gibbon_max_iterations_escalates_to_harmbe(self, tmp_path: Path):
        """After MAX_REWORK_ITERATIONS, Gibbon escalates to Harmbe."""
        artifact_dir = tmp_path / "aidlc-docs"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "test.md").write_text("# Test\n", encoding="utf-8")

        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        gibbon = Gibbon(mail_client=mock_mail)

        rework_instructions = json.dumps({
            "review_gate_id": "gt-42",
            "feedback": "Still not adequate.",
            "artifact_path": "aidlc-docs/test.md",
            "retry_count": MAX_REWORK_ITERATIONS,  # Already at the limit
        })

        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root=str(tmp_path),
            instructions=rework_instructions,
        )

        completion = await gibbon._execute(dispatch)

        assert completion.status == "needs_rework"
        assert "Escalated to Harmbe" in completion.summary

        # Verify escalation mail was sent to Harmbe
        harmbe_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "Harmbe" in c[0][2]
        ]
        assert len(harmbe_calls) >= 1

    @pytest.mark.asyncio
    async def test_gibbon_missing_artifact_fails(self):
        """Gibbon fails gracefully when the artifact file does not exist."""
        gibbon = Gibbon()

        rework_instructions = json.dumps({
            "review_gate_id": "gt-42",
            "feedback": "Needs work.",
            "artifact_path": "nonexistent/artifact.md",
            "retry_count": 0,
        })

        dispatch = build_dispatch(
            stage_name="test-stage",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/nonexistent-workspace",
            instructions=rework_instructions,
        )

        completion = await gibbon._execute(dispatch)

        assert completion.status == "failed"
        assert "not found" in (completion.error_detail or "").lower()

    @pytest.mark.asyncio
    async def test_gibbon_missing_feedback_fails(self):
        """Gibbon fails when no feedback is provided in the rework request."""
        gibbon = Gibbon()

        rework_instructions = json.dumps({
            "review_gate_id": "gt-42",
            "feedback": "",
            "artifact_path": "some/path.md",
            "retry_count": 0,
        })

        dispatch = build_dispatch(
            stage_name="test-stage",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root="/tmp/workspace",
            instructions=rework_instructions,
        )

        completion = await gibbon._execute(dispatch)

        assert completion.status == "failed"
        assert "feedback" in (completion.error_detail or "").lower()

    @pytest.mark.asyncio
    async def test_rework_retry_increments_correctly(self, tmp_path: Path):
        """Sequential rework iterations increment retry_count properly."""
        artifact_dir = tmp_path / "docs"
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "artifact.md"
        artifact_file.write_text("# Original\n", encoding="utf-8")

        gibbon = Gibbon()

        for iteration in range(MAX_REWORK_ITERATIONS):
            rework_instructions = json.dumps({
                "review_gate_id": "gt-42",
                "feedback": f"Iteration {iteration} feedback",
                "artifact_path": "docs/artifact.md",
                "retry_count": iteration,
            })

            dispatch = build_dispatch(
                stage_name="test-stage",
                beads_issue_id="gt-5",
                project_key="test-proj",
                workspace_root=str(tmp_path),
                instructions=rework_instructions,
            )

            with patch.object(
                gibbon, "_invoke_llm", new_callable=AsyncMock,
                return_value=f"# Corrected iteration {iteration + 1}\nImproved content.\n",
            ):
                completion = await gibbon._execute(dispatch)

            assert completion.status == "completed"
            assert f"iteration {iteration + 1}" in completion.summary.lower()

    @pytest.mark.asyncio
    async def test_full_reject_rework_approve_cycle(self, tmp_path: Path):
        """End-to-end: API reject -> Gibbon rework -> API approve."""
        # Setup artifact
        artifact_dir = tmp_path / "aidlc-docs"
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "requirements.md"
        artifact_file.write_text("# Needs work\n", encoding="utf-8")

        # Step 1: Gibbon rework
        gibbon = Gibbon()
        rework_instructions = json.dumps({
            "review_gate_id": "gt-42",
            "feedback": "Add more detail to section 2.",
            "artifact_path": "aidlc-docs/requirements.md",
            "retry_count": 0,
        })

        dispatch = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test-proj",
            workspace_root=str(tmp_path),
            instructions=rework_instructions,
        )

        with patch.object(
            gibbon, "_invoke_llm", new_callable=AsyncMock,
            return_value="# Improved\n\n## Section 2\nDetailed auth requirements.\n",
        ):
            rework_completion = await gibbon._execute(dispatch)

        assert rework_completion.status == "completed"

        # Step 2: Approve via API
        engine = AgentEngine()
        registry = ProjectRegistry(workspace_root=tmp_path)
        notif_mgr = NotificationManager()
        app = create_app(
            project_registry=registry,
            agent_engine=engine,
            notification_manager=notif_mgr,
        )

        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=_make_beads_issue("gt-42"))
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads), \
                 patch("orchestrator.api.routes.review.get_mail_client", return_value=mock_mail):
                resp = await client.post(
                    "/api/review/gt-42/approve",
                    json={"feedback": "Looks good after rework."},
                )

        assert resp.status_code == 200
        assert resp.json()["decision"] == "approved"
