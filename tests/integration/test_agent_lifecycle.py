"""Integration tests for agent lifecycle management in the Gorilla Troop system.

Tests the AgentEngine lifecycle (spawn, run, timeout, shutdown), runner
registration and dispatch routing via wiring, cross-cutting agent interaction
patterns (CuriousGeorge, Gibbon, Groomer), and ProjectMinder workflow
advancement -- all with mocked LLM and Beads dependencies.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.engine.agent_engine import AgentEngine, AgentInstance, EngineConfig
from orchestrator.lib.context.dispatch import (
    STAGE_AGENT_MAP,
    CompletionMessage,
    DispatchMessage,
    build_completion,
    build_dispatch,
)
from orchestrator.wiring import AGENT_CLASSES, wire_engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dispatch(
    stage: str = "requirements-analysis",
    issue_id: str = "gt-10",
    project_key: str = "test-project",
    workspace: str = "/tmp/workspace",
    **kwargs,
) -> DispatchMessage:
    """Shortcut to create a DispatchMessage for tests."""
    return build_dispatch(stage, issue_id, project_key, workspace, **kwargs)


def _make_engine(
    max_concurrent: int = 4,
    timeout: int = 3600,
) -> AgentEngine:
    """Create an AgentEngine with test-friendly defaults."""
    return AgentEngine(
        EngineConfig(
            max_concurrent_agents=max_concurrent,
            agent_timeout_seconds=timeout,
        )
    )


def _mock_bedrock_config():
    """Return a MagicMock standing in for BedrockConfig."""
    cfg = MagicMock()
    cfg.model_id = "test-model"
    cfg.aws_profile = "test-profile"
    cfg.create_bedrock_model = MagicMock(side_effect=RuntimeError("no Bedrock in CI"))
    return cfg


# ---------------------------------------------------------------------------
# 1. TestAgentSpawnLifecycle
# ---------------------------------------------------------------------------


class TestAgentSpawnLifecycle:
    """Spawn, run, complete, and status-transition tests."""

    @pytest.mark.asyncio
    async def test_spawn_returns_starting_instance(self):
        engine = _make_engine()

        async def runner(inst: AgentInstance, ctx: dict) -> dict:
            await asyncio.sleep(0.5)
            return {"ok": True}

        engine.register_runner("Scout", runner)
        instance = await engine.spawn_agent("Scout", {}, project_key="p1", task_id="gt-1")

        assert instance.agent_type == "Scout"
        assert instance.project_key == "p1"
        assert instance.current_task == "gt-1"
        # Immediately after spawn, status should be starting or running
        assert instance.status in ("starting", "running")

        await engine.shutdown(timeout=2.0)

    @pytest.mark.asyncio
    async def test_agent_transitions_to_running_then_stopped(self):
        engine = _make_engine()
        status_log: list[str] = []

        async def runner(inst: AgentInstance, ctx: dict) -> dict:
            status_log.append(inst.status)
            await asyncio.sleep(0.05)
            return {"done": True}

        engine.register_runner("Sage", runner)
        instance = await engine.spawn_agent("Sage", {})

        # Let the agent complete
        await asyncio.sleep(0.3)

        assert "running" in status_log
        assert instance.status == "stopped"

    @pytest.mark.asyncio
    async def test_agent_error_sets_error_status(self):
        engine = _make_engine()

        async def failing_runner(inst: AgentInstance, ctx: dict) -> dict:
            raise ValueError("simulated failure")

        engine.register_runner("Bard", failing_runner)
        instance = await engine.spawn_agent("Bard", {})

        await asyncio.sleep(0.2)
        assert instance.status == "error"

    @pytest.mark.asyncio
    async def test_no_runner_registered_sets_error(self):
        engine = _make_engine()
        instance = await engine.spawn_agent("UnknownType", {})

        await asyncio.sleep(0.2)
        assert instance.status == "error"

    @pytest.mark.asyncio
    async def test_get_agent_returns_spawned(self):
        engine = _make_engine()

        async def noop(inst, ctx):
            return {}

        engine.register_runner("Scout", noop)
        instance = await engine.spawn_agent("Scout", {})
        fetched = engine.get_agent(instance.agent_id)
        assert fetched is instance

        await engine.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_list_all_includes_completed(self):
        engine = _make_engine()

        async def fast(inst, ctx):
            return {}

        engine.register_runner("Scout", fast)
        await engine.spawn_agent("Scout", {})
        await asyncio.sleep(0.2)

        all_agents = engine.list_all()
        assert len(all_agents) == 1
        assert all_agents[0].status == "stopped"

    @pytest.mark.asyncio
    async def test_stop_agent_cancels_running(self):
        engine = _make_engine()

        async def long_runner(inst, ctx):
            await asyncio.sleep(60)
            return {}

        engine.register_runner("Forge", long_runner)
        instance = await engine.spawn_agent("Forge", {})
        await asyncio.sleep(0.1)

        await engine.stop_agent(instance.agent_id, reason="manual stop")
        assert instance.status == "stopped"

        await engine.shutdown(timeout=1.0)


# ---------------------------------------------------------------------------
# 2. TestConcurrentAgents
# ---------------------------------------------------------------------------


class TestConcurrentAgents:
    """Multiple agents with semaphore-based concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        engine = _make_engine(max_concurrent=2)
        concurrent_count = 0
        peak_concurrent = 0

        async def tracked_runner(inst: AgentInstance, ctx: dict) -> dict:
            nonlocal concurrent_count, peak_concurrent
            concurrent_count += 1
            peak_concurrent = max(peak_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return {}

        engine.register_runner("Scout", tracked_runner)

        # Spawn 5 agents against a limit of 2
        for _ in range(5):
            await engine.spawn_agent("Scout", {})

        # Wait long enough for all to complete sequentially
        await asyncio.sleep(1.5)

        assert peak_concurrent <= 2
        assert all(a.status == "stopped" for a in engine.list_all())

    @pytest.mark.asyncio
    async def test_multiple_agent_types_concurrent(self):
        engine = _make_engine(max_concurrent=3)
        completed_types: list[str] = []

        async def type_tracker(inst: AgentInstance, ctx: dict) -> dict:
            await asyncio.sleep(0.05)
            completed_types.append(inst.agent_type)
            return {}

        for agent_type in ("Scout", "Sage", "Forge"):
            engine.register_runner(agent_type, type_tracker)

        await engine.spawn_agent("Scout", {})
        await engine.spawn_agent("Sage", {})
        await engine.spawn_agent("Forge", {})

        await asyncio.sleep(0.5)

        assert set(completed_types) == {"Scout", "Sage", "Forge"}
        assert len(engine.list_active()) == 0

    @pytest.mark.asyncio
    async def test_list_active_reflects_running(self):
        engine = _make_engine(max_concurrent=4)
        gate = asyncio.Event()

        async def gated_runner(inst, ctx):
            await gate.wait()
            return {}

        engine.register_runner("Scout", gated_runner)
        await engine.spawn_agent("Scout", {})
        await engine.spawn_agent("Scout", {})

        await asyncio.sleep(0.1)
        assert len(engine.list_active()) == 2

        gate.set()
        await asyncio.sleep(0.2)
        assert len(engine.list_active()) == 0

        await engine.shutdown(timeout=1.0)


# ---------------------------------------------------------------------------
# 3. TestAgentTimeout
# ---------------------------------------------------------------------------


class TestAgentTimeout:
    """Agent timeout handling with short timeout config."""

    @pytest.mark.asyncio
    async def test_timeout_sets_error_status(self):
        engine = _make_engine(timeout=1)

        async def slow(inst, ctx):
            await asyncio.sleep(30)
            return {}

        engine.register_runner("Scout", slow)
        instance = await engine.spawn_agent("Scout", {})

        await asyncio.sleep(1.5)
        assert instance.status == "error"

    @pytest.mark.asyncio
    async def test_timeout_releases_semaphore(self):
        engine = _make_engine(max_concurrent=1, timeout=1)

        async def slow(inst, ctx):
            await asyncio.sleep(30)
            return {}

        async def fast(inst, ctx):
            return {"fast": True}

        engine.register_runner("Scout", slow)
        engine.register_runner("Sage", fast)

        slow_inst = await engine.spawn_agent("Scout", {})

        # After the timeout fires, the semaphore should be released
        await asyncio.sleep(1.5)
        assert slow_inst.status == "error"

        fast_inst = await engine.spawn_agent("Sage", {})
        await asyncio.sleep(0.3)
        assert fast_inst.status == "stopped"

        await engine.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_fast_agent_completes_before_timeout(self):
        engine = _make_engine(timeout=5)

        async def quick(inst, ctx):
            await asyncio.sleep(0.05)
            return {"quick": True}

        engine.register_runner("Scout", quick)
        instance = await engine.spawn_agent("Scout", {})

        await asyncio.sleep(0.3)
        assert instance.status == "stopped"


# ---------------------------------------------------------------------------
# 4. TestEngineShutdown
# ---------------------------------------------------------------------------


class TestEngineShutdown:
    """Graceful shutdown with active agents."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_active_agents(self):
        engine = _make_engine()

        async def forever(inst, ctx):
            await asyncio.sleep(3600)
            return {}

        engine.register_runner("Scout", forever)
        a1 = await engine.spawn_agent("Scout", {})
        a2 = await engine.spawn_agent("Scout", {})

        await asyncio.sleep(0.1)
        await engine.shutdown(timeout=1.0)

        assert a1.status == "stopped"
        assert a2.status == "stopped"
        assert len(engine.list_active()) == 0

    @pytest.mark.asyncio
    async def test_shutdown_prevents_new_spawns(self):
        engine = _make_engine()

        async def noop(inst, ctx):
            return {}

        engine.register_runner("Scout", noop)
        await engine.shutdown(timeout=1.0)

        with pytest.raises(RuntimeError, match="shutting down"):
            await engine.spawn_agent("Scout", {})

    @pytest.mark.asyncio
    async def test_shutdown_marks_all_stopped(self):
        engine = _make_engine(max_concurrent=1)
        gate = asyncio.Event()

        async def gated(inst, ctx):
            await gate.wait()
            return {}

        engine.register_runner("Scout", gated)
        # Spawn more than concurrency allows so some stay in "starting"
        inst1 = await engine.spawn_agent("Scout", {})
        inst2 = await engine.spawn_agent("Scout", {})

        await asyncio.sleep(0.1)
        await engine.shutdown(timeout=1.0)

        for inst in engine.list_all():
            assert inst.status == "stopped"

    @pytest.mark.asyncio
    async def test_shutdown_with_no_agents(self):
        engine = _make_engine()
        # Should not raise
        await engine.shutdown(timeout=1.0)
        assert len(engine.list_all()) == 0


# ---------------------------------------------------------------------------
# 5. TestRunnerRegistration
# ---------------------------------------------------------------------------


class TestRunnerRegistration:
    """wire_engine registers all agent types from AGENT_CLASSES."""

    def test_wire_engine_registers_all_agent_types(self):
        engine = _make_engine()
        bedrock_config = _mock_bedrock_config()

        wire_engine(engine, bedrock_config=bedrock_config)

        for agent_type in AGENT_CLASSES:
            assert agent_type in engine._runners, (
                f"Runner not registered for {agent_type}"
            )

    def test_wire_engine_runner_count(self):
        engine = _make_engine()
        bedrock_config = _mock_bedrock_config()

        wire_engine(engine, bedrock_config=bedrock_config)

        assert len(engine._runners) == len(AGENT_CLASSES)

    def test_registered_runners_are_callable(self):
        engine = _make_engine()
        bedrock_config = _mock_bedrock_config()

        wire_engine(engine, bedrock_config=bedrock_config)

        for agent_type, runner in engine._runners.items():
            assert callable(runner), f"Runner for {agent_type} is not callable"

    def test_manual_registration(self):
        engine = _make_engine()

        async def custom_runner(inst, ctx):
            return {"custom": True}

        engine.register_runner("CustomAgent", custom_runner)
        assert "CustomAgent" in engine._runners

    def test_agent_classes_complete(self):
        expected = {
            "Harmbe", "ProjectMinder", "Scout", "Sage", "Bard",
            "Planner", "Architect", "Steward", "Forge", "Crucible", "Troop",
        }
        assert expected.issubset(set(AGENT_CLASSES.keys()))


# ---------------------------------------------------------------------------
# 6. TestDispatchRouting
# ---------------------------------------------------------------------------


class TestDispatchRouting:
    """Correct agent type receives dispatch for each stage."""

    def test_stage_agent_map_covers_all_stages(self):
        expected_stages = {
            "workspace-detection", "reverse-engineering",
            "requirements-analysis", "user-stories",
            "workflow-planning", "application-design", "units-generation",
            "functional-design", "nfr-requirements", "nfr-design",
            "infrastructure-design", "code-generation", "build-and-test",
        }
        assert expected_stages == set(STAGE_AGENT_MAP.keys())

    @pytest.mark.parametrize(
        "stage, expected_agent",
        [
            ("workspace-detection", "Scout"),
            ("reverse-engineering", "Scout"),
            ("requirements-analysis", "Sage"),
            ("user-stories", "Bard"),
            ("workflow-planning", "Planner"),
            ("application-design", "Architect"),
            ("units-generation", "Planner"),
            ("functional-design", "Sage"),
            ("nfr-requirements", "Steward"),
            ("nfr-design", "Steward"),
            ("infrastructure-design", "Architect"),
            ("code-generation", "Forge"),
            ("build-and-test", "Crucible"),
        ],
    )
    def test_dispatch_assigns_correct_agent(self, stage, expected_agent):
        dispatch = build_dispatch(stage, "gt-1", "proj", "/ws")
        assert dispatch.assigned_agent == expected_agent

    def test_unknown_stage_falls_back_to_troop(self):
        dispatch = build_dispatch("nonexistent-stage", "gt-99", "proj", "/ws")
        assert dispatch.assigned_agent == "Troop"

    @pytest.mark.asyncio
    async def test_engine_routes_dispatch_to_runner(self):
        engine = _make_engine()
        received_contexts: dict[str, dict] = {}

        def make_capturing_runner(agent_type: str):
            async def runner(inst: AgentInstance, ctx: dict) -> dict:
                received_contexts[agent_type] = ctx
                return {"agent": agent_type}
            return runner

        for agent_type in ("Scout", "Sage", "Forge"):
            engine.register_runner(agent_type, make_capturing_runner(agent_type))

        dispatch = _make_dispatch(stage="requirements-analysis")
        ctx = {"dispatch": dispatch}
        await engine.spawn_agent("Sage", ctx, task_id="gt-10")

        await asyncio.sleep(0.2)
        assert "Sage" in received_contexts
        assert received_contexts["Sage"]["dispatch"].stage_name == "requirements-analysis"

        await engine.shutdown(timeout=1.0)

    def test_dispatch_override_agent(self):
        dispatch = build_dispatch(
            "code-generation", "gt-1", "proj", "/ws", assigned_agent="Troop"
        )
        assert dispatch.assigned_agent == "Troop"


# ---------------------------------------------------------------------------
# 7. TestCrossCuttingIntegration
# ---------------------------------------------------------------------------


class TestCrossCuttingIntegration:
    """CuriousGeorge error handling, Gibbon rework, Groomer monitoring."""

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.curious_george.show_issue")
    async def test_curious_george_investigates_and_suggests_fix(self, mock_show):
        mock_issue = MagicMock()
        mock_issue.id = "gt-10"
        mock_issue.title = "Requirements Analysis"
        mock_issue.status = "in_progress"
        mock_issue.assignee = "Sage"
        mock_issue.labels = ["stage:requirements-analysis"]
        mock_issue.notes = ""
        mock_show.return_value = mock_issue

        from orchestrator.agents.cross_cutting.curious_george import CuriousGeorge

        mock_mail = MagicMock()
        cg = CuriousGeorge(mail_client=mock_mail)

        error_instructions = json.dumps({
            "error_message": "Timeout calling Bedrock",
            "source_agent": "Sage",
            "affected_issue_id": "gt-10",
        })

        dispatch = _make_dispatch(
            stage="error-investigation",
            issue_id="gt-10",
            instructions=error_instructions,
        )

        # Mock _invoke_llm to return a fix suggestion
        cg._invoke_llm = AsyncMock(return_value=json.dumps({
            "root_cause": "Bedrock API timeout due to large prompt",
            "fix_suggested": True,
            "fix_description": "Split prompt into smaller chunks",
            "target_agent": "Sage",
        }))

        result = await cg._execute(dispatch)

        assert result.status == "completed"
        assert "root cause" in result.summary.lower() or "Root cause" in result.summary
        # CuriousGeorge should have sent a fix message to the source agent
        mock_mail.send_message.assert_called()
        call_args = mock_mail.send_message.call_args
        assert "Sage" in call_args[0][2]  # to_agents list

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.curious_george.show_issue")
    async def test_curious_george_escalates_unfixable_error(self, mock_show):
        mock_show.return_value = None  # Issue not found

        from orchestrator.agents.cross_cutting.curious_george import CuriousGeorge

        mock_mail = MagicMock()
        cg = CuriousGeorge(mail_client=mock_mail)

        dispatch = _make_dispatch(
            stage="error-investigation",
            issue_id="gt-99",
            instructions=json.dumps({
                "error_message": "Catastrophic data corruption",
                "source_agent": "Forge",
                "affected_issue_id": "gt-99",
            }),
        )

        cg._invoke_llm = AsyncMock(return_value=json.dumps({
            "root_cause": "Data corruption in workspace",
            "fix_suggested": False,
            "escalation_reason": "Data loss requires human intervention",
        }))

        result = await cg._execute(dispatch)

        assert result.status == "completed"
        assert "escalat" in result.summary.lower()
        # Escalation message should go to Harmbe
        harmbe_call = None
        for call in mock_mail.send_message.call_args_list:
            if "Harmbe" in call[0][2]:
                harmbe_call = call
                break
        assert harmbe_call is not None, "Expected escalation to Harmbe"

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.gibbon.AuditLog")
    @patch("orchestrator.agents.cross_cutting.gibbon.FileGuard")
    async def test_gibbon_rework_within_budget(self, mock_fg_cls, mock_al_cls, tmp_path):
        from orchestrator.agents.cross_cutting.gibbon import Gibbon

        # Create a test artifact file
        artifact = tmp_path / "design.md"
        artifact.write_text("# Original Design\nNeeds improvement.", encoding="utf-8")

        mock_file_guard = MagicMock()
        mock_file_guard.write_file.return_value = str(artifact)
        mock_fg_cls.return_value = mock_file_guard
        mock_al_cls.return_value = MagicMock()

        gibbon = Gibbon()
        gibbon._invoke_llm = AsyncMock(return_value="# Corrected Design\nImproved content.")

        dispatch = _make_dispatch(
            stage="rework",
            issue_id="gt-10",
            workspace=str(tmp_path),
            instructions=json.dumps({
                "review_gate_id": "rg-5",
                "feedback": "Missing NFR coverage",
                "artifact_path": "design.md",
                "retry_count": 0,
            }),
        )

        result = await gibbon._execute(dispatch)

        assert result.status == "completed"
        assert "design.md" in result.output_artifacts
        assert "iteration 1" in result.summary.lower() or "1/" in result.summary

    @pytest.mark.asyncio
    async def test_gibbon_escalates_after_max_iterations(self):
        from orchestrator.agents.cross_cutting.gibbon import Gibbon, MAX_REWORK_ITERATIONS

        mock_mail = MagicMock()
        gibbon = Gibbon(mail_client=mock_mail)

        dispatch = _make_dispatch(
            stage="rework",
            issue_id="gt-10",
            instructions=json.dumps({
                "review_gate_id": "rg-5",
                "feedback": "Still wrong",
                "artifact_path": "design.md",
                "retry_count": MAX_REWORK_ITERATIONS,  # Exceeded budget
            }),
        )

        result = await gibbon._execute(dispatch)

        assert result.status == "needs_rework"
        assert "escalat" in result.summary.lower()
        # Escalation to Harmbe
        mock_mail.send_message.assert_called_once()
        call_args = mock_mail.send_message.call_args
        assert "Harmbe" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_gibbon_fails_without_artifact_path(self):
        from orchestrator.agents.cross_cutting.gibbon import Gibbon

        gibbon = Gibbon()
        dispatch = _make_dispatch(
            stage="rework",
            issue_id="gt-10",
            instructions=json.dumps({
                "feedback": "Fix this",
                # Missing artifact_path
            }),
        )

        result = await gibbon._execute(dispatch)
        assert result.status == "failed"
        assert "artifact_path" in (result.error_detail or "").lower()

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.groomer.list_issues")
    async def test_groomer_detects_stale_issues(self, mock_list):
        from orchestrator.agents.cross_cutting.groomer import Groomer, STALE_THRESHOLD_HOURS

        # Create an issue that is stale (older than threshold)
        stale_issue = MagicMock()
        stale_issue.id = "gt-5"
        stale_issue.title = "Requirements Analysis"
        stale_issue.status = "in_progress"
        stale_issue.updated_at = "2025-01-01T00:00:00Z"
        stale_issue.created_at = "2025-01-01T00:00:00Z"

        mock_list.return_value = [stale_issue]

        mock_mail = MagicMock()
        groomer = Groomer(mail_client=mock_mail)

        dispatch = _make_dispatch(stage="monitoring", issue_id="gt-0")
        result = await groomer._execute(dispatch)

        assert result.status == "completed"
        assert len(result.discovered_issues) > 0
        stale_found = any(
            d["type"] == "stale_issue" for d in result.discovered_issues
        )
        assert stale_found, "Groomer should detect stale issues"

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.groomer.list_issues")
    async def test_groomer_sends_report_to_harmbe(self, mock_list):
        from orchestrator.agents.cross_cutting.groomer import Groomer

        mock_list.return_value = []  # No stale issues

        mock_mail = MagicMock()
        mock_mail.fetch_inbox = MagicMock(return_value=[])
        groomer = Groomer(mail_client=mock_mail)

        dispatch = _make_dispatch(stage="monitoring", issue_id="gt-0")
        await groomer._execute(dispatch)

        # The Groomer should send a report to Harmbe
        send_calls = [
            c for c in mock_mail.send_message.call_args_list
            if "Harmbe" in c[0][2]
        ]
        assert len(send_calls) >= 1

    @pytest.mark.asyncio
    @patch("orchestrator.agents.cross_cutting.groomer.list_issues")
    async def test_groomer_no_issues_clean_report(self, mock_list):
        from orchestrator.agents.cross_cutting.groomer import Groomer

        mock_list.return_value = []

        groomer = Groomer()  # No mail client
        dispatch = _make_dispatch(stage="monitoring", issue_id="gt-0")
        result = await groomer._execute(dispatch)

        assert result.status == "completed"
        assert len(result.discovered_issues) == 0


# ---------------------------------------------------------------------------
# 8. TestProjectMinderWorkflow
# ---------------------------------------------------------------------------


class TestProjectMinderWorkflow:
    """Workflow advancement with mocked Beads state."""

    @pytest.mark.asyncio
    @patch("orchestrator.agents.project_minder.ProjectMinder._dispatch_to_chimp", new_callable=AsyncMock)
    @patch("orchestrator.agents.project_minder.ProjectMinder._claim_issue", new_callable=AsyncMock)
    @patch("orchestrator.agents.project_minder.ProjectMinder._gather_input_artifacts", new_callable=AsyncMock)
    @patch("orchestrator.agents.project_minder.ProjectMinder._get_ready_issues", new_callable=AsyncMock)
    async def test_advance_dispatches_next_stage(
        self, mock_ready, mock_gather, mock_claim, mock_dispatch
    ):
        from orchestrator.agents.project_minder import ProjectMinder

        # Simulate a ready issue for requirements-analysis
        ready_issue = MagicMock()
        ready_issue.id = "gt-5"
        ready_issue.title = "Requirements Analysis"
        ready_issue.labels = ["stage:requirements-analysis", "phase:inception"]
        ready_issue.status = "open"
        mock_ready.return_value = [ready_issue]
        mock_gather.return_value = ["aidlc-docs/inception/workspace-detection.md"]

        pm = ProjectMinder()
        pm._project_key = "gorilla-troop"
        pm._workspace_root = "/workspace"

        result = await pm._execute({"action": "advance"})

        assert "requirements-analysis" in result
        assert "Sage" in result
        mock_claim.assert_awaited_once_with("gt-5")
        mock_dispatch.assert_awaited_once()
        # Verify the dispatch was to Sage
        dispatch_call = mock_dispatch.call_args
        assert dispatch_call[0][0] == "Sage"

    @pytest.mark.asyncio
    @patch("orchestrator.agents.project_minder.ProjectMinder._get_ready_issues", new_callable=AsyncMock)
    @patch("orchestrator.agents.project_minder.ProjectMinder._check_all_done", new_callable=AsyncMock)
    async def test_advance_no_ready_waiting(self, mock_done, mock_ready):
        from orchestrator.agents.project_minder import ProjectMinder

        mock_ready.return_value = []
        mock_done.return_value = False

        pm = ProjectMinder()
        result = await pm._execute({"action": "advance"})

        assert "waiting" in result.lower() or "no stages ready" in result.lower()

    @pytest.mark.asyncio
    @patch("orchestrator.agents.project_minder.ProjectMinder._get_ready_issues", new_callable=AsyncMock)
    @patch("orchestrator.agents.project_minder.ProjectMinder._check_all_done", new_callable=AsyncMock)
    async def test_advance_all_done(self, mock_done, mock_ready):
        from orchestrator.agents.project_minder import ProjectMinder

        mock_ready.return_value = []
        mock_done.return_value = True

        pm = ProjectMinder()
        result = await pm._execute({"action": "advance"})

        assert "complete" in result.lower() or "finished" in result.lower()

    @pytest.mark.asyncio
    @patch("orchestrator.agents.project_minder.ProjectMinder._advance_workflow", new_callable=AsyncMock)
    async def test_handle_completion_updates_issue(self, mock_advance):
        from orchestrator.agents.project_minder import ProjectMinder

        mock_advance.return_value = "Advanced to next stage"

        pm = ProjectMinder()

        with patch("orchestrator.lib.beads.client.update_issue") as mock_update:
            result = await pm._execute({
                "action": "handle_completion",
                "beads_issue_id": "gt-5",
                "status": "completed",
                "summary": "Requirements done",
                "output_artifacts": ["requirements.md"],
            })

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == "gt-5"
            assert call_args[1]["status"] == "done"

    @pytest.mark.asyncio
    async def test_recommend_skip_sends_to_harmbe(self):
        from orchestrator.agents.project_minder import ProjectMinder

        pm = ProjectMinder()
        pm._project_key = "test-proj"

        with patch("orchestrator.lib.agent_mail.client.AgentMailClient") as mock_mail_cls:
            mock_mail_inst = MagicMock()
            mock_mail_cls.return_value = mock_mail_inst

            result = await pm._execute({
                "action": "recommend_skip",
                "stage_name": "reverse-engineering",
                "issue_id": "gt-3",
                "rationale": "Greenfield project, nothing to reverse-engineer",
            })

            assert "skip" in result.lower()
            mock_mail_inst.send_message.assert_called_once()
            call_args = mock_mail_inst.send_message.call_args
            assert "Harmbe" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_check_review_gates_lists_open(self):
        from orchestrator.agents.project_minder import ProjectMinder

        gate1 = MagicMock()
        gate1.id = "rg-1"
        gate1.title = "Review: Requirements"
        gate2 = MagicMock()
        gate2.id = "rg-2"
        gate2.title = "Review: Design"

        with patch("orchestrator.lib.beads.client.list_issues", return_value=[gate1, gate2]):
            pm = ProjectMinder()
            result = await pm._execute({"action": "check_review_gates"})

            assert "rg-1" in result
            assert "rg-2" in result

    @pytest.mark.asyncio
    async def test_check_review_gates_none_pending(self):
        from orchestrator.agents.project_minder import ProjectMinder

        with patch("orchestrator.lib.beads.client.list_issues", return_value=[]):
            pm = ProjectMinder()
            result = await pm._execute({"action": "check_review_gates"})

            assert "no pending" in result.lower()

    @pytest.mark.asyncio
    async def test_default_action_is_advance(self):
        from orchestrator.agents.project_minder import ProjectMinder

        pm = ProjectMinder()

        with patch.object(pm, "_advance_workflow", new_callable=AsyncMock) as mock_advance:
            mock_advance.return_value = "advanced"
            result = await pm._execute({})

            mock_advance.assert_awaited_once()
            assert result == "advanced"

    @pytest.mark.asyncio
    async def test_unknown_action_defaults_to_advance(self):
        from orchestrator.agents.project_minder import ProjectMinder

        pm = ProjectMinder()

        with patch.object(pm, "_advance_workflow", new_callable=AsyncMock) as mock_advance:
            mock_advance.return_value = "advanced-fallback"
            result = await pm._execute({"action": "some_unknown_action"})

            mock_advance.assert_awaited_once()
            assert result == "advanced-fallback"
