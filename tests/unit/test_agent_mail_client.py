"""Unit tests for the Agent Mail HTTP client library."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.lib.agent_mail.models import (
    AgentMailConfig,
    MailMessage,
    FileReservation,
    AgentInfo,
)
from orchestrator.lib.agent_mail.client import AgentMailClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_mcp_response(result_data: dict | list | str) -> MagicMock:
    """Create a mock httpx Response for MCP JSON-RPC."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(result_data)}
            ]
        },
    }
    return response


def _mock_error_response(code: int, message: str) -> MagicMock:
    """Create a mock httpx Response for MCP error."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "error": {"code": code, "message": message},
    }
    return response


def _mock_http_error(status_code: int, text: str = "Error") -> MagicMock:
    """Create a mock httpx Response for HTTP-level error."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestMailMessage:
    def test_from_json(self):
        data = {
            "id": "msg-1",
            "subject": "Hello",
            "body": "World",
            "from_agent": "Harmbe",
            "to_agents": ["ProjectMinder"],
            "thread_id": "gt-5",
            "importance": "high",
            "created_at": "2026-02-15",
            "acknowledged": False,
        }
        msg = MailMessage.from_json(data)
        assert msg.id == "msg-1"
        assert msg.from_agent == "Harmbe"
        assert msg.to_agents == ["ProjectMinder"]

    def test_from_json_alt_keys(self):
        data = {
            "message_id": "msg-2",
            "subject": "Alt",
            "body": "Keys",
            "sender": "Snake",
            "recipients": ["Forge"],
        }
        msg = MailMessage.from_json(data)
        assert msg.id == "msg-2"
        assert msg.from_agent == "Snake"


class TestFileReservation:
    def test_from_json(self):
        data = {
            "id": "res-1",
            "agent_name": "Forge",
            "paths": ["orchestrator/**"],
            "exclusive": True,
            "reason": "gt-19",
            "ttl_seconds": 3600,
        }
        res = FileReservation.from_json(data)
        assert res.id == "res-1"
        assert res.exclusive is True


class TestAgentInfo:
    def test_from_json(self):
        data = {
            "name": "Harmbe",
            "project_key": "gorilla-troop",
            "model": "claude-opus-4.6",
        }
        info = AgentInfo.from_json(data)
        assert info.name == "Harmbe"
        assert info.model == "claude-opus-4.6"


# ---------------------------------------------------------------------------
# Client tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestAgentMailClient:
    def _make_client(self):
        config = AgentMailConfig(
            base_url="http://test:8765",
            bearer_token="test-token",
            timeout=5.0,
        )
        client = AgentMailClient(config)
        return client

    @patch("httpx.Client.post")
    def test_ensure_project(self, mock_post):
        mock_post.return_value = _mock_mcp_response({"project_key": "my-proj"})
        client = self._make_client()
        result = client.ensure_project("my-proj", "My Project")
        assert result["project_key"] == "my-proj"
        mock_post.assert_called_once()

    @patch("httpx.Client.post")
    def test_register_agent(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "name": "Harmbe",
            "project_key": "gorilla-troop",
        })
        client = self._make_client()
        info = client.register_agent("gorilla-troop", "Harmbe", model="claude-opus-4.6")
        assert info.name == "Harmbe"

    @patch("httpx.Client.post")
    def test_send_message(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "id": "msg-42",
            "subject": "Stage Complete",
            "body": "Requirements done",
            "from_agent": "Scout",
            "to_agents": ["ProjectMinder"],
        })
        client = self._make_client()
        msg = client.send_message(
            "gorilla-troop", "Scout", ["ProjectMinder"],
            "Stage Complete", "Requirements done",
            thread_id="gt-5",
        )
        assert msg.id == "msg-42"
        assert msg.subject == "Stage Complete"

    @patch("httpx.Client.post")
    def test_fetch_inbox(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "messages": [
                {"id": "msg-1", "subject": "Hello", "body": "Hi", "from_agent": "Harmbe", "to_agents": ["Scout"]},
                {"id": "msg-2", "subject": "Update", "body": "Done", "from_agent": "Harmbe", "to_agents": ["Scout"]},
            ]
        })
        client = self._make_client()
        messages = client.fetch_inbox("gorilla-troop", "Scout")
        assert len(messages) == 2
        assert messages[0].id == "msg-1"

    @patch("httpx.Client.post")
    def test_acknowledge_message(self, mock_post):
        mock_post.return_value = _mock_mcp_response({"ok": True})
        client = self._make_client()
        client.acknowledge_message("gorilla-troop", "Scout", "msg-1")
        mock_post.assert_called_once()

    @patch("httpx.Client.post")
    def test_search_messages(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "results": [
                {"id": "msg-1", "subject": "Requirements", "body": "Done", "from_agent": "Scout", "to_agents": ["PM"]},
            ]
        })
        client = self._make_client()
        results = client.search_messages("gorilla-troop", "requirements")
        assert len(results) == 1

    @patch("httpx.Client.post")
    def test_reserve_files(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "id": "res-1",
            "agent_name": "Forge",
            "paths": ["orchestrator/**"],
            "exclusive": True,
        })
        client = self._make_client()
        res = client.reserve_files("gorilla-troop", "Forge", ["orchestrator/**"], reason="gt-19")
        assert res.id == "res-1"
        assert res.exclusive is True

    @patch("httpx.Client.post")
    def test_release_files(self, mock_post):
        mock_post.return_value = _mock_mcp_response({"ok": True})
        client = self._make_client()
        client.release_files("gorilla-troop", "Forge", ["orchestrator/**"])
        mock_post.assert_called_once()

    @patch("httpx.Client.post")
    def test_list_agents(self, mock_post):
        mock_post.return_value = _mock_mcp_response({
            "agents": [
                {"name": "Harmbe", "project_key": "gorilla-troop"},
                {"name": "Scout", "project_key": "gorilla-troop"},
            ]
        })
        client = self._make_client()
        agents = client.list_agents("gorilla-troop")
        assert len(agents) == 2

    # -------------------------------------------------------------------
    # Error handling tests
    # -------------------------------------------------------------------

    @patch("httpx.Client.post")
    def test_auth_failure(self, mock_post):
        mock_post.return_value = _mock_http_error(401, "Unauthorized")
        client = self._make_client()
        with pytest.raises(PermissionError, match="authentication failed"):
            client.ensure_project("test")

    @patch("httpx.Client.post")
    def test_tool_error(self, mock_post):
        mock_post.return_value = _mock_error_response(-32000, "Agent not registered")
        client = self._make_client()
        with pytest.raises(RuntimeError, match="Agent not registered"):
            client.send_message("test", "Nobody", ["PM"], "Hi", "Body")

    @patch("httpx.Client.post")
    def test_http_error(self, mock_post):
        mock_post.return_value = _mock_http_error(500, "Internal Server Error")
        client = self._make_client()
        with pytest.raises(RuntimeError, match="HTTP error 500"):
            client.ensure_project("test")

    @patch("httpx.Client.post", side_effect=Exception("Connection refused"))
    def test_connection_error_fallback(self, mock_post):
        """Non-httpx exceptions should propagate."""
        client = self._make_client()
        with pytest.raises(Exception):
            client.ensure_project("test")
