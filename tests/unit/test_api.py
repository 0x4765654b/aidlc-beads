"""Tests for Unit 6: Orchestrator API (FastAPI REST + WebSocket)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from orchestrator.api.app import create_app
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.notification_manager import NotificationManager


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_registry(tmp_path: Path) -> ProjectRegistry:
    """Create a ProjectRegistry backed by a temp directory."""
    return ProjectRegistry(workspace_root=tmp_path)


@pytest.fixture
def engine() -> AgentEngine:
    """Create a fresh AgentEngine."""
    return AgentEngine()


@pytest.fixture
def notif_mgr() -> NotificationManager:
    """Create a fresh NotificationManager."""
    return NotificationManager()


@pytest.fixture
def app(tmp_registry, engine, notif_mgr):
    """Create the FastAPI app with injected test dependencies."""
    return create_app(
        project_registry=tmp_registry,
        agent_engine=engine,
        notification_manager=notif_mgr,
    )


@pytest_asyncio.fixture
async def client(app):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health & Info ─────────────────────────────────────────────────────────


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_system_info(self, client: AsyncClient):
        resp = await client.get("/api/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert data["active_projects"] == 0
        assert data["active_agents"] == 0
        assert data["pending_notifications"] == 0
        assert data["engine_status"] == "running"


# ── Projects ──────────────────────────────────────────────────────────────


class TestProjects:
    @pytest.mark.asyncio
    async def test_create_project(self, client: AsyncClient, tmp_path: Path):
        """Create a project pointing to an existing directory."""
        workspace = tmp_path / "my-project"
        workspace.mkdir()

        resp = await client.post(
            "/api/projects/",
            json={
                "key": "test-proj",
                "name": "Test Project",
                "workspace_path": str(workspace),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_key"] == "test-proj"
        assert data["name"] == "Test Project"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_project_invalid_path(self, client: AsyncClient):
        """Reject creation with non-existent workspace."""
        resp = await client.post(
            "/api/projects/",
            json={
                "key": "bad-proj",
                "name": "Bad",
                "workspace_path": "/nonexistent/path/xyz",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_duplicate_project(self, client: AsyncClient, tmp_path: Path):
        """Reject duplicate project keys."""
        workspace = tmp_path / "dup-proj"
        workspace.mkdir()
        body = {
            "key": "dup",
            "name": "Dup",
            "workspace_path": str(workspace),
        }

        resp1 = await client.post("/api/projects/", json=body)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/projects/", json=body)
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client: AsyncClient):
        resp = await client.get("/api/projects/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_projects_with_filter(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "filter-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "p1", "name": "P1", "workspace_path": str(workspace)},
        )

        resp_all = await client.get("/api/projects/")
        assert len(resp_all.json()) == 1

        resp_paused = await client.get("/api/projects/?status=paused")
        assert len(resp_paused.json()) == 0

    @pytest.mark.asyncio
    async def test_get_project(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "get-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "gp", "name": "GP", "workspace_path": str(workspace)},
        )

        resp = await client.get("/api/projects/gp")
        assert resp.status_code == 200
        assert resp.json()["project_key"] == "gp"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient):
        resp = await client.get("/api/projects/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pause_resume_project(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "pause-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "pr", "name": "PR", "workspace_path": str(workspace)},
        )

        # Pause
        resp = await client.post("/api/projects/pr/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

        # Resume
        resp = await client.post("/api/projects/pr/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_pause_nonexistent(self, client: AsyncClient):
        resp = await client.post("/api/projects/nope/pause")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "del-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "dp", "name": "DP", "workspace_path": str(workspace)},
        )

        resp = await client.delete("/api/projects/dp")
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get("/api/projects/dp")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient):
        resp = await client.delete("/api/projects/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_project_status(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "status-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "sp", "name": "SP", "workspace_path": str(workspace)},
        )

        resp = await client.get("/api/projects/sp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_key"] == "sp"
        assert data["active_agents"] == 0

    @pytest.mark.asyncio
    async def test_project_agents(self, client: AsyncClient, tmp_path: Path):
        workspace = tmp_path / "agents-test"
        workspace.mkdir()
        await client.post(
            "/api/projects/",
            json={"key": "ag", "name": "AG", "workspace_path": str(workspace)},
        )

        resp = await client.get("/api/projects/ag/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_project_invalid_key(self, client: AsyncClient, tmp_path: Path):
        """Reject keys with invalid characters."""
        workspace = tmp_path / "inv"
        workspace.mkdir()
        resp = await client.post(
            "/api/projects/",
            json={"key": "bad key!", "name": "Bad", "workspace_path": str(workspace)},
        )
        assert resp.status_code == 422


# ── Chat ──────────────────────────────────────────────────────────────────


class TestChat:
    @pytest.mark.asyncio
    async def test_send_message(self, client: AsyncClient):
        resp = await client.post(
            "/api/chat/",
            json={"message": "Hello Harmbe!", "project_key": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["response"]) > 0
        assert data["message_id"].startswith("msg-")

    @pytest.mark.asyncio
    async def test_chat_history_empty(self, client: AsyncClient):
        resp = await client.get("/api/chat/history?project_key=nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_chat_history_after_message(self, client: AsyncClient):
        await client.post(
            "/api/chat/",
            json={"message": "First message", "project_key": "hist"},
        )

        resp = await client.get("/api/chat/history?project_key=hist")
        assert resp.status_code == 200
        history = resp.json()
        # Should have user msg + assistant response
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_empty_message_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/chat/",
            json={"message": "", "project_key": "test"},
        )
        assert resp.status_code == 422


# ── Review ────────────────────────────────────────────────────────────────


class TestReview:
    @pytest.mark.asyncio
    async def test_list_review_gates_empty(self, client: AsyncClient):
        from unittest.mock import MagicMock, patch

        mock_beads = MagicMock()
        mock_beads.list_issues = MagicMock(return_value=[])
        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads):
            resp = await client.get("/api/review/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_review_detail_not_found(self, client: AsyncClient):
        from unittest.mock import MagicMock, patch

        mock_beads = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=None)
        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads):
            resp = await client.get("/api/review/gt-99")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_review(self, client: AsyncClient):
        from unittest.mock import MagicMock, patch

        mock_beads = MagicMock()
        mock_beads.update_issue = MagicMock()
        mock_mail = MagicMock()
        mock_mail.send_message = MagicMock()
        with patch("orchestrator.api.routes.review.get_beads_client", return_value=mock_beads), \
             patch("orchestrator.api.routes.review.get_mail_client", return_value=mock_mail):
            resp = await client.post(
                "/api/review/gt-99/approve",
                json={"feedback": "Looks good!"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"
        assert data["issue_id"] == "gt-99"

    @pytest.mark.asyncio
    async def test_reject_review(self, client: AsyncClient):
        resp = await client.post(
            "/api/review/gt-99/reject",
            json={"feedback": "Needs more detail in section 3"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "rejected"
        assert data["next_action"] == "dispatched_rework"


# ── Notifications ─────────────────────────────────────────────────────────


class TestNotifications:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/notifications/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_count_empty(self, client: AsyncClient):
        resp = await client.get("/api/notifications/count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["by_type"] == {}

    @pytest.mark.asyncio
    async def test_notification_lifecycle(self, client: AsyncClient, notif_mgr: NotificationManager):
        """Create a notification, list it, mark it read."""
        # Create via the manager directly (API consumers use the engine)
        n = notif_mgr.create(
            type="review_gate",
            title="Review ready",
            body="Requirements doc ready for review",
            project_key="test-proj",
            priority=0,
        )

        # List
        resp = await client.get("/api/notifications/")
        assert resp.status_code == 200
        notifs = resp.json()
        assert len(notifs) == 1
        assert notifs[0]["title"] == "Review ready"
        assert notifs[0]["read"] is False

        # Count
        resp = await client.get("/api/notifications/count")
        assert resp.json()["count"] == 1
        assert resp.json()["by_type"]["review_gate"] == 1

        # Mark read
        resp = await client.post(f"/api/notifications/{n.id}/read")
        assert resp.status_code == 204

        # Verify count is now 0
        resp = await client.get("/api/notifications/count")
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_mark_nonexistent_read(self, client: AsyncClient):
        resp = await client.post("/api/notifications/nonexistent/read")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_all_read(self, client: AsyncClient, notif_mgr: NotificationManager):
        notif_mgr.create("info", "A", "body", "proj1")
        notif_mgr.create("info", "B", "body", "proj1")
        notif_mgr.create("info", "C", "body", "proj2")

        resp = await client.post("/api/notifications/read-all?project_key=proj1")
        assert resp.status_code == 200
        assert resp.json()["marked"] == 2

        # proj2 notification still unread
        resp = await client.get("/api/notifications/count?project_key=proj2")
        assert resp.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_project(self, client: AsyncClient, notif_mgr: NotificationManager):
        notif_mgr.create("info", "A", "body", "alpha")
        notif_mgr.create("info", "B", "body", "beta")

        resp = await client.get("/api/notifications/?project_key=alpha")
        assert len(resp.json()) == 1
        assert resp.json()[0]["project_key"] == "alpha"


# ── Questions ─────────────────────────────────────────────────────────────


class TestQuestions:
    @pytest.mark.asyncio
    async def test_list_questions_empty(self, client: AsyncClient):
        resp = await client.get("/api/questions/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_question_not_found(self, client: AsyncClient):
        from unittest.mock import MagicMock, patch

        mock_beads = MagicMock()
        mock_beads.show_issue = MagicMock(return_value=None)
        with patch("orchestrator.api.routes.questions.get_beads_client", return_value=mock_beads):
            resp = await client.get("/api/questions/gt-42")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_answer_question(self, client: AsyncClient):
        resp = await client.post(
            "/api/questions/gt-42/answer",
            json={"answer": "B) OAuth/SSO"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["issue_id"] == "gt-42"
        assert data["answer"] == "B) OAuth/SSO"

    @pytest.mark.asyncio
    async def test_answer_empty_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/questions/gt-42/answer",
            json={"answer": ""},
        )
        assert resp.status_code == 422


# ── WebSocket ─────────────────────────────────────────────────────────────


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self, app):
        """Test the ConnectionManager broadcast logic directly."""
        from orchestrator.api.websocket import ConnectionManager

        manager = ConnectionManager()
        assert manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_ws_manager_in_app(self, app):
        """Verify ws_manager is accessible from app state."""
        assert hasattr(app.state, "ws_manager")
        assert app.state.ws_manager.active_connections == 0


# ── Option Parsing ────────────────────────────────────────────────────────


class TestOptionParsing:
    def test_parse_options(self):
        """Test that _parse_options extracts options from question text."""
        from orchestrator.api.routes.questions import _parse_options

        text = """Which authentication method?

A) OAuth/SSO
B) Username/Password
C) API Keys
X) Other"""
        options = _parse_options(text)
        assert len(options) == 4
        assert options[0] == "A) OAuth/SSO"
        assert options[3] == "X) Other"

    def test_parse_options_no_options(self):
        from orchestrator.api.routes.questions import _parse_options

        assert _parse_options("No options here") == []

    def test_parse_options_partial(self):
        from orchestrator.api.routes.questions import _parse_options

        text = "A) Only one option"
        options = _parse_options(text)
        assert len(options) == 1


# ── Artifact Path Extraction ─────────────────────────────────────────────


class TestArtifactExtraction:
    def test_extract_artifact_path(self):
        from orchestrator.api.routes.review import _extract_artifact_path

        notes = "artifact: aidlc-docs/inception/requirements/requirements.md\nCompleted: done"
        path = _extract_artifact_path(notes)
        assert path == "aidlc-docs/inception/requirements/requirements.md"

    def test_extract_artifact_path_none(self):
        from orchestrator.api.routes.review import _extract_artifact_path

        assert _extract_artifact_path(None) is None
        assert _extract_artifact_path("no artifact here") is None

    def test_extract_stage_name(self):
        from orchestrator.api.routes.review import _extract_stage_name

        assert _extract_stage_name("REVIEW: Requirements Analysis - Awaiting Approval") == "Requirements Analysis"
        assert _extract_stage_name("Something else") == ""
