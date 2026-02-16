"""Tests for Unit 8: GT CLI (Click command-line interface)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from cli.gt import cli, ApiClient


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_api():
    """Patch httpx.request to simulate API responses."""
    with patch("cli.gt.httpx.request") as mock_req:
        yield mock_req


def _ok_response(data, status_code=200):
    """Create a mock httpx.Response with JSON data."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = str(data)
    return resp


def _no_content():
    """Create a 204 No Content mock response."""
    resp = MagicMock()
    resp.status_code = 204
    return resp


def _error_response(status_code, detail):
    """Create an error mock response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"detail": detail}
    resp.text = detail
    return resp


# ── info command ──────────────────────────────────────────────────────────


class TestInfoCommand:
    def test_info(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "version": "0.1.0",
            "active_projects": 2,
            "active_agents": 3,
            "pending_notifications": 5,
            "engine_status": "running",
        })
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "Gorilla Troop v0.1.0" in result.output
        assert "Active Projects: 2" in result.output
        assert "Active Agents: 3" in result.output
        assert "Engine: running" in result.output


# ── status command ────────────────────────────────────────────────────────


class TestStatusCommand:
    def test_status_all_projects(self, runner, mock_api):
        mock_api.return_value = _ok_response([
            {"project_key": "proj-a", "name": "Project A", "status": "active"},
            {"project_key": "proj-b", "name": "Project B", "status": "paused"},
        ])
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "proj-a" in result.output
        assert "●" in result.output
        assert "proj-b" in result.output

    def test_status_specific_project(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "project_key": "test",
            "name": "Test",
            "status": "active",
            "current_phase": "construction",
            "active_agents": 2,
            "pending_reviews": 1,
            "open_questions": 0,
        })
        result = runner.invoke(cli, ["status", "test"])
        assert result.exit_code == 0
        assert "Project: test (Test)" in result.output
        assert "Phase: construction" in result.output

    def test_status_empty(self, runner, mock_api):
        mock_api.return_value = _ok_response([])
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "No projects found" in result.output


# ── projects commands ─────────────────────────────────────────────────────


class TestProjectsCommands:
    def test_projects_list(self, runner, mock_api):
        mock_api.return_value = _ok_response([
            {
                "project_key": "test",
                "name": "Test Project",
                "status": "active",
                "created_at": "2026-02-15T00:00:00Z",
            }
        ])
        result = runner.invoke(cli, ["projects", "list"])
        assert result.exit_code == 0
        assert "test" in result.output
        assert "Test Project" in result.output

    def test_projects_create(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "project_key": "new-proj",
            "name": "New Project",
            "status": "active",
        })
        result = runner.invoke(
            cli, ["projects", "create", "new-proj", "New Project", "/dev/proj"]
        )
        assert result.exit_code == 0
        assert "Created project: new-proj" in result.output

    def test_projects_pause(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "project_key": "test",
            "status": "paused",
        })
        result = runner.invoke(cli, ["projects", "pause", "test"])
        assert result.exit_code == 0
        assert "Paused project: test" in result.output

    def test_projects_resume(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "project_key": "test",
            "status": "active",
        })
        result = runner.invoke(cli, ["projects", "resume", "test"])
        assert result.exit_code == 0
        assert "Resumed project: test" in result.output

    def test_projects_delete_with_confirm(self, runner, mock_api):
        mock_api.return_value = _no_content()
        result = runner.invoke(cli, ["projects", "delete", "test", "--confirm"])
        assert result.exit_code == 0
        assert "Deleted project: test" in result.output

    def test_projects_delete_abort(self, runner, mock_api):
        result = runner.invoke(cli, ["projects", "delete", "test"], input="n\n")
        assert result.exit_code == 1


# ── approve / reject ─────────────────────────────────────────────────────


class TestReviewCommands:
    def test_approve(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "issue_id": "gt-12",
            "decision": "approved",
            "message": "Next stage dispatched.",
        })
        result = runner.invoke(cli, ["approve", "gt-12"])
        assert result.exit_code == 0
        assert "Review gt-12 approved" in result.output

    def test_approve_with_feedback(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "issue_id": "gt-12",
            "decision": "approved",
            "message": "Done.",
        })
        result = runner.invoke(
            cli, ["approve", "gt-12", "--feedback", "Looks good!"]
        )
        assert result.exit_code == 0

    def test_reject(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "issue_id": "gt-12",
            "decision": "rejected",
            "message": "Rework dispatched.",
        })
        result = runner.invoke(
            cli, ["reject", "gt-12", "--feedback", "Needs more detail"]
        )
        assert result.exit_code == 0
        assert "Review gt-12 rejected" in result.output
        assert "Needs more detail" in result.output

    def test_reject_requires_feedback(self, runner, mock_api):
        result = runner.invoke(cli, ["reject", "gt-12"])
        assert result.exit_code != 0


# ── reviews ───────────────────────────────────────────────────────────────


class TestReviewsList:
    def test_reviews_empty(self, runner, mock_api):
        mock_api.return_value = _ok_response([])
        result = runner.invoke(cli, ["reviews"])
        assert result.exit_code == 0
        assert "No pending reviews" in result.output

    def test_reviews_list(self, runner, mock_api):
        mock_api.return_value = _ok_response([
            {"issue_id": "gt-12", "title": "Req Analysis", "project_key": "test"},
        ])
        result = runner.invoke(cli, ["reviews"])
        assert result.exit_code == 0
        assert "gt-12" in result.output
        assert "Req Analysis" in result.output


# ── questions ─────────────────────────────────────────────────────────────


class TestQuestionsCommands:
    def test_questions_list_empty(self, runner, mock_api):
        mock_api.return_value = _ok_response([])
        result = runner.invoke(cli, ["questions"])
        assert result.exit_code == 0
        assert "No pending questions" in result.output

    def test_questions_answer(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "issue_id": "gt-25",
            "answer": "B) OAuth",
            "message": "Question answered.",
        })
        result = runner.invoke(
            cli, ["questions", "answer", "gt-25", "B) OAuth"]
        )
        assert result.exit_code == 0
        assert "Question gt-25 answered" in result.output


# ── notifications ─────────────────────────────────────────────────────────


class TestNotificationsCommands:
    def test_notifications_empty(self, runner, mock_api):
        mock_api.return_value = _ok_response([])
        result = runner.invoke(cli, ["notifications"])
        assert result.exit_code == 0
        assert "No unread notifications" in result.output

    def test_notifications_list(self, runner, mock_api):
        mock_api.return_value = _ok_response([
            {
                "id": "notif-1",
                "type": "review_gate",
                "title": "Review Ready",
                "priority": 0,
                "read": False,
                "project_key": "test",
                "created_at": "2026-02-15T12:00:00Z",
            }
        ])
        result = runner.invoke(cli, ["notifications"])
        assert result.exit_code == 0
        assert "Review Ready" in result.output
        assert "P0" in result.output

    def test_notifications_read(self, runner, mock_api):
        mock_api.return_value = _no_content()
        result = runner.invoke(cli, ["notifications", "read", "notif-1"])
        assert result.exit_code == 0
        assert "Marked notif-1 as read" in result.output

    def test_notifications_read_all(self, runner, mock_api):
        mock_api.return_value = _ok_response({"marked": 5})
        result = runner.invoke(cli, ["notifications", "read-all"])
        assert result.exit_code == 0
        assert "Marked 5 notifications as read" in result.output


# ── chat ──────────────────────────────────────────────────────────────────


class TestChatCommand:
    def test_chat(self, runner, mock_api):
        mock_api.return_value = _ok_response({
            "message_id": "msg-abc",
            "response": "Hello! How can I help?",
        })
        result = runner.invoke(cli, ["chat", "Hello Harmbe!"])
        assert result.exit_code == 0
        assert "Harmbe: Hello! How can I help?" in result.output


# ── error handling ────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_connection_error(self, runner, mock_api):
        import httpx
        mock_api.side_effect = httpx.ConnectError("refused")
        result = runner.invoke(cli, ["info"])
        assert result.exit_code != 0
        assert "Cannot connect" in result.output

    def test_api_error(self, runner, mock_api):
        mock_api.return_value = _error_response(404, "Not found")
        result = runner.invoke(cli, ["status", "nonexistent"])
        assert result.exit_code != 0
        assert "Not found" in result.output

    def test_timeout(self, runner, mock_api):
        import httpx
        mock_api.side_effect = httpx.TimeoutException("timed out")
        result = runner.invoke(cli, ["info"])
        assert result.exit_code != 0
        assert "timed out" in result.output


# ── ApiClient unit tests ─────────────────────────────────────────────────


class TestApiClient:
    def test_base_url_trimming(self):
        client = ApiClient("http://localhost:9741/")
        assert client.base_url == "http://localhost:9741"

    def test_default_url(self):
        client = ApiClient("http://localhost:9741")
        assert client.base_url == "http://localhost:9741"
