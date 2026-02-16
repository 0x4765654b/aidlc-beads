"""Unit tests for the Context Dispatch and Agent Engine (Unit 4)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_dispatch,
    build_completion,
    serialize_dispatch,
    deserialize_dispatch,
    serialize_completion,
    deserialize_completion,
    STAGE_AGENT_MAP,
)
from orchestrator.engine.agent_engine import AgentEngine, AgentInstance, EngineConfig
from orchestrator.engine.project_registry import ProjectRegistry, ProjectState
from orchestrator.engine.notification_manager import NotificationManager, Notification


# ---------------------------------------------------------------------------
# Context Dispatch Protocol tests
# ---------------------------------------------------------------------------


class TestDispatchMessage:
    def test_build_dispatch_defaults(self):
        msg = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="gorilla-troop",
            workspace_root="/workspace",
        )
        assert msg.stage_name == "requirements-analysis"
        assert msg.assigned_agent == "Sage"  # From STAGE_AGENT_MAP
        assert msg.project_key == "gorilla-troop"

    def test_build_dispatch_override_agent(self):
        msg = build_dispatch(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            project_key="test",
            workspace_root="/workspace",
            assigned_agent="Troop",
        )
        assert msg.assigned_agent == "Troop"

    def test_build_dispatch_unknown_stage(self):
        msg = build_dispatch(
            stage_name="unknown-stage",
            beads_issue_id="gt-99",
            project_key="test",
            workspace_root="/workspace",
        )
        assert msg.assigned_agent == "Troop"  # Fallback

    def test_serialization_roundtrip(self):
        msg = build_dispatch(
            stage_name="code-generation",
            beads_issue_id="gt-19",
            project_key="gorilla-troop",
            workspace_root="/workspace",
            unit_name="unit-1-scribe",
            phase="construction",
            input_artifacts=["aidlc-docs/construction/unit-1-scribe/functional-design.md"],
        )
        json_str = serialize_dispatch(msg)
        restored = deserialize_dispatch(json_str)
        assert restored.stage_name == msg.stage_name
        assert restored.beads_issue_id == msg.beads_issue_id
        assert restored.input_artifacts == msg.input_artifacts
        assert restored.assigned_agent == "Forge"


class TestCompletionMessage:
    def test_build_completion(self):
        msg = build_completion(
            stage_name="requirements-analysis",
            beads_issue_id="gt-5",
            output_artifacts=["aidlc-docs/inception/requirements/requirements.md"],
            summary="Requirements document created with 15 FRs and 8 NFRs.",
        )
        assert msg.status == "completed"
        assert len(msg.output_artifacts) == 1

    def test_build_failure(self):
        msg = build_completion(
            stage_name="code-generation",
            beads_issue_id="gt-19",
            output_artifacts=[],
            summary="",
            status="failed",
            error_detail="Import error in generated module",
        )
        assert msg.status == "failed"
        assert msg.error_detail is not None

    def test_serialization_roundtrip(self):
        msg = build_completion("test", "gt-1", ["out.md"], "Done", discovered_issues=[{"title": "Found bug"}])
        json_str = serialize_completion(msg)
        restored = deserialize_completion(json_str)
        assert restored.stage_name == "test"
        assert len(restored.discovered_issues) == 1


class TestStageAgentMap:
    def test_all_inception_stages_mapped(self):
        inception_stages = [
            "workspace-detection", "reverse-engineering",
            "requirements-analysis", "user-stories",
            "workflow-planning", "application-design", "units-generation",
        ]
        for stage in inception_stages:
            assert stage in STAGE_AGENT_MAP, f"Missing mapping for {stage}"

    def test_all_construction_stages_mapped(self):
        construction_stages = [
            "functional-design", "nfr-requirements", "nfr-design",
            "infrastructure-design", "code-generation", "build-and-test",
        ]
        for stage in construction_stages:
            assert stage in STAGE_AGENT_MAP, f"Missing mapping for {stage}"


# ---------------------------------------------------------------------------
# Agent Engine tests
# ---------------------------------------------------------------------------


class TestAgentEngine:
    @pytest.mark.asyncio
    async def test_spawn_and_complete(self):
        engine = AgentEngine(EngineConfig(max_concurrent_agents=2))

        async def mock_runner(instance: AgentInstance, context: dict) -> dict:
            return {"result": "success"}

        engine.register_runner("Scout", mock_runner)
        instance = await engine.spawn_agent("Scout", {"test": True}, task_id="gt-5")

        assert instance.agent_type == "Scout"
        assert instance.current_task == "gt-5"

        # Wait for completion
        await asyncio.sleep(0.1)
        assert instance.status == "stopped"

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        engine = AgentEngine(EngineConfig(max_concurrent_agents=1))
        running_count = 0
        max_running = 0

        async def slow_runner(instance: AgentInstance, context: dict) -> dict:
            nonlocal running_count, max_running
            running_count += 1
            max_running = max(max_running, running_count)
            await asyncio.sleep(0.05)
            running_count -= 1
            return {}

        engine.register_runner("Scout", slow_runner)

        # Spawn 3 agents with concurrency limit of 1
        await engine.spawn_agent("Scout", {})
        await engine.spawn_agent("Scout", {})
        await engine.spawn_agent("Scout", {})

        await asyncio.sleep(0.5)
        assert max_running <= 1

    @pytest.mark.asyncio
    async def test_shutdown(self):
        engine = AgentEngine(EngineConfig(max_concurrent_agents=2))

        async def long_runner(instance: AgentInstance, context: dict) -> dict:
            await asyncio.sleep(10)
            return {}

        engine.register_runner("Scout", long_runner)
        await engine.spawn_agent("Scout", {})

        await engine.shutdown(timeout=1.0)
        active = engine.list_active()
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_spawn_during_shutdown_raises(self):
        engine = AgentEngine()

        async def noop(instance, context):
            return {}

        engine.register_runner("Scout", noop)
        engine._shutdown_event.set()

        with pytest.raises(RuntimeError, match="shutting down"):
            await engine.spawn_agent("Scout", {})

    @pytest.mark.asyncio
    async def test_timeout(self):
        engine = AgentEngine(EngineConfig(agent_timeout_seconds=1))

        async def slow_runner(instance: AgentInstance, context: dict) -> dict:
            await asyncio.sleep(10)
            return {}

        engine.register_runner("Scout", slow_runner)
        instance = await engine.spawn_agent("Scout", {})

        await asyncio.sleep(1.5)
        assert instance.status == "error"

    def test_list_active(self):
        engine = AgentEngine()
        instance = AgentInstance(agent_id="test-1", agent_type="Scout", status="running")
        engine._agents["test-1"] = instance
        assert len(engine.list_active()) == 1

        instance.status = "stopped"
        assert len(engine.list_active()) == 0


# ---------------------------------------------------------------------------
# Project Registry tests
# ---------------------------------------------------------------------------


class TestProjectRegistry:
    def test_create_and_get(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        project = registry.create_project("test", "Test Project", str(tmp_path))
        assert project.project_key == "test"
        assert project.status == "active"

        fetched = registry.get_project("test")
        assert fetched is not None
        assert fetched.name == "Test Project"

    def test_duplicate_key_raises(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        registry.create_project("test", "Test", str(tmp_path))
        with pytest.raises(ValueError, match="already exists"):
            registry.create_project("test", "Duplicate", str(tmp_path))

    def test_list_projects(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        registry.create_project("proj-a", "A", str(tmp_path))
        registry.create_project("proj-b", "B", str(tmp_path))

        all_projects = registry.list_projects()
        assert len(all_projects) == 2

    def test_pause_resume(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        registry.create_project("test", "Test", str(tmp_path))

        registry.pause_project("test")
        assert registry.get_project("test").status == "paused"
        assert registry.get_project("test").paused_at is not None

        registry.resume_project("test")
        assert registry.get_project("test").status == "active"
        assert registry.get_project("test").paused_at is None

    def test_persistence(self, tmp_path: Path):
        registry1 = ProjectRegistry(workspace_root=tmp_path)
        registry1.create_project("test", "Test", str(tmp_path))

        # Create new instance -- should load from disk
        registry2 = ProjectRegistry(workspace_root=tmp_path)
        assert registry2.get_project("test") is not None
        assert registry2.get_project("test").name == "Test"

    def test_not_found_raises(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        with pytest.raises(KeyError, match="not found"):
            registry.pause_project("nonexistent")

    def test_filter_by_status(self, tmp_path: Path):
        registry = ProjectRegistry(workspace_root=tmp_path)
        registry.create_project("active-1", "A", str(tmp_path))
        registry.create_project("paused-1", "P", str(tmp_path))
        registry.pause_project("paused-1")

        active = registry.list_projects(status="active")
        assert len(active) == 1
        assert active[0].project_key == "active-1"


# ---------------------------------------------------------------------------
# Notification Manager tests
# ---------------------------------------------------------------------------


class TestNotificationManager:
    def test_add_and_get_unread(self):
        mgr = NotificationManager()
        mgr.create("review_gate", "Review needed", "Please review.", "proj-a", priority=0)
        mgr.create("info", "Stage complete", "FD done.", "proj-a", priority=4)

        unread = mgr.get_unread()
        assert len(unread) == 2
        assert unread[0].priority == 0  # Higher priority first
        assert unread[1].priority == 4

    def test_mark_read(self):
        mgr = NotificationManager()
        notif = mgr.create("info", "Test", "Body", "proj-a")
        assert mgr.count_unread() == 1

        mgr.mark_read(notif.id)
        assert mgr.count_unread() == 0

    def test_project_filter(self):
        mgr = NotificationManager()
        mgr.create("info", "A", "Body", "proj-a")
        mgr.create("info", "B", "Body", "proj-b")

        a_unread = mgr.get_unread(project_key="proj-a")
        assert len(a_unread) == 1
        assert a_unread[0].title == "A"

    def test_clear_project(self):
        mgr = NotificationManager()
        mgr.create("info", "A", "Body", "proj-a")
        mgr.create("info", "B", "Body", "proj-b")

        mgr.clear_project("proj-a")
        assert mgr.count_unread("proj-a") == 0
        assert mgr.count_unread("proj-b") == 1

    def test_priority_ordering(self):
        mgr = NotificationManager()
        mgr.create("info", "Low", "Body", "proj-a", priority=4)
        mgr.create("escalation", "High", "Body", "proj-a", priority=1)
        mgr.create("review_gate", "Critical", "Body", "proj-a", priority=0)

        unread = mgr.get_unread()
        assert unread[0].type == "review_gate"
        assert unread[1].type == "escalation"
        assert unread[2].type == "info"

    def test_mark_all_read(self):
        mgr = NotificationManager()
        mgr.create("info", "A", "Body", "proj-a")
        mgr.create("info", "B", "Body", "proj-a")
        mgr.create("info", "C", "Body", "proj-b")

        count = mgr.mark_all_read("proj-a")
        assert count == 2
        assert mgr.count_unread("proj-a") == 0
        assert mgr.count_unread("proj-b") == 1

    def test_limit(self):
        mgr = NotificationManager()
        for i in range(10):
            mgr.create("info", f"N{i}", "Body", "proj-a")

        limited = mgr.get_unread(limit=3)
        assert len(limited) == 3
