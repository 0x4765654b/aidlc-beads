"""HTTP client for the MCP Agent Mail server.

Calls MCP tools via the Streamable HTTP endpoint using JSON-RPC format.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

from orchestrator.lib.agent_mail.models import (
    AgentMailConfig,
    MailMessage,
    FileReservation,
    AgentInfo,
)


class AgentMailClient:
    """HTTP client for Agent Mail MCP server.

    Usage::

        client = AgentMailClient()
        client.ensure_project("my-project")
        client.register_agent("my-project", "Harmbe")
        client.send_message("my-project", "Harmbe", ["ProjectMinder"], "Hello", "Body")
    """

    def __init__(self, config: AgentMailConfig | None = None):
        if config is None:
            config = AgentMailConfig(
                base_url=os.environ.get("AGENT_MAIL_URL", "http://localhost:8765"),
                bearer_token=os.environ.get("AGENT_MAIL_TOKEN"),
                timeout=float(os.environ.get("AGENT_MAIL_TIMEOUT", "30")),
            )
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            headers=self._auth_headers(),
        )

    def _auth_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        return headers

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool via JSON-RPC over HTTP.

        Args:
            tool_name: The MCP tool name (e.g., "send_message").
            arguments: Tool arguments as a dictionary.

        Returns:
            The result content from the MCP response.

        Raises:
            ConnectionError: If the server is unreachable.
            PermissionError: If authentication fails.
            RuntimeError: If the tool returns an error.
            TimeoutError: If the request times out.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            response = self._client.post("/mcp", json=payload)
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot connect to Agent Mail at {self._config.base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Agent Mail request timed out after {self._config.timeout}s: {e}"
            ) from e

        if response.status_code in (401, 403):
            raise PermissionError(
                f"Agent Mail authentication failed ({response.status_code}): "
                f"{response.text[:200]}"
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Agent Mail HTTP error {response.status_code}: {response.text[:500]}"
            )

        data = response.json()

        # Check for JSON-RPC error
        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"Agent Mail tool error: [{err.get('code', '?')}] "
                f"{err.get('message', str(err))}"
            )

        result = data.get("result", {})

        # MCP tool results are in result.content[0].text (JSON string)
        content = result.get("content", [])
        if content and isinstance(content, list):
            text = content[0].get("text", "{}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        return result

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> AgentMailClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # -------------------------------------------------------------------
    # Project & Agent Registration
    # -------------------------------------------------------------------

    def ensure_project(self, project_key: str, human_name: str | None = None) -> dict:
        """Ensure a project exists in Agent Mail."""
        args: dict[str, Any] = {"project_key": project_key}
        if human_name:
            args["human_name"] = human_name
        return self._call_tool("ensure_project", args)

    def register_agent(
        self,
        project_key: str,
        agent_name: str,
        model: str | None = None,
        program: str | None = None,
    ) -> AgentInfo:
        """Register an agent identity."""
        args: dict[str, Any] = {
            "project_key": project_key,
            "agent_name": agent_name,
        }
        if model:
            args["model"] = model
        if program:
            args["program"] = program
        result = self._call_tool("register_agent", args)
        return AgentInfo.from_json(result) if isinstance(result, dict) else AgentInfo(name=agent_name)

    # -------------------------------------------------------------------
    # Messaging
    # -------------------------------------------------------------------

    def send_message(
        self,
        project_key: str,
        from_agent: str,
        to_agents: list[str],
        subject: str,
        body: str,
        *,
        thread_id: str | None = None,
        cc_agents: list[str] | None = None,
        importance: str = "normal",
        ack_required: bool = False,
    ) -> MailMessage:
        """Send a message to one or more agents."""
        args: dict[str, Any] = {
            "project_key": project_key,
            "from_agent": from_agent,
            "to_agents": to_agents,
            "subject": subject,
            "body": body,
            "importance": importance,
        }
        if thread_id:
            args["thread_id"] = thread_id
        if cc_agents:
            args["cc_agents"] = cc_agents
        if ack_required:
            args["ack_required"] = True

        result = self._call_tool("send_message", args)
        return MailMessage.from_json(result) if isinstance(result, dict) else MailMessage(id="", subject=subject, body=body, from_agent=from_agent)

    def fetch_inbox(
        self,
        project_key: str,
        agent_name: str,
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[MailMessage]:
        """Fetch inbox messages for an agent."""
        args: dict[str, Any] = {
            "project_key": project_key,
            "agent_name": agent_name,
            "limit": limit,
        }
        if unread_only:
            args["unread_only"] = True

        result = self._call_tool("fetch_inbox", args)
        if isinstance(result, list):
            return [MailMessage.from_json(m) for m in result]
        if isinstance(result, dict):
            messages = result.get("messages", result.get("items", []))
            return [MailMessage.from_json(m) for m in messages]
        return []

    def acknowledge_message(
        self, project_key: str, agent_name: str, message_id: str
    ) -> None:
        """Acknowledge receipt of a message."""
        self._call_tool(
            "acknowledge_message",
            {
                "project_key": project_key,
                "agent_name": agent_name,
                "message_id": message_id,
            },
        )

    def search_messages(
        self,
        project_key: str,
        query: str,
        scope: str = "both",
        limit: int = 20,
    ) -> list[MailMessage]:
        """Search messages by text."""
        result = self._call_tool(
            "search_messages",
            {
                "project_key": project_key,
                "query": query,
                "scope": scope,
                "limit": limit,
            },
        )
        if isinstance(result, list):
            return [MailMessage.from_json(m) for m in result]
        if isinstance(result, dict):
            messages = result.get("messages", result.get("results", []))
            return [MailMessage.from_json(m) for m in messages]
        return []

    # -------------------------------------------------------------------
    # File Reservations
    # -------------------------------------------------------------------

    def reserve_files(
        self,
        project_key: str,
        agent_name: str,
        paths: list[str],
        ttl_seconds: int = 3600,
        exclusive: bool = True,
        reason: str | None = None,
    ) -> FileReservation:
        """Create advisory file reservations."""
        args: dict[str, Any] = {
            "project_key": project_key,
            "agent_name": agent_name,
            "paths": paths,
            "ttl_seconds": ttl_seconds,
            "exclusive": exclusive,
        }
        if reason:
            args["reason"] = reason

        result = self._call_tool("file_reservation_paths", args)
        return FileReservation.from_json(result) if isinstance(result, dict) else FileReservation(id="", agent_name=agent_name, paths=paths)

    def release_files(
        self,
        project_key: str,
        agent_name: str,
        paths: list[str] | None = None,
    ) -> None:
        """Release file reservations."""
        args: dict[str, Any] = {
            "project_key": project_key,
            "agent_name": agent_name,
        }
        if paths:
            args["paths"] = paths
        self._call_tool("release_file_reservations", args)

    # -------------------------------------------------------------------
    # Agent Directory
    # -------------------------------------------------------------------

    def list_agents(self, project_key: str) -> list[AgentInfo]:
        """List registered agents for a project."""
        result = self._call_tool("list_agents", {"project_key": project_key})
        if isinstance(result, list):
            return [AgentInfo.from_json(a) for a in result]
        if isinstance(result, dict):
            agents = result.get("agents", result.get("items", []))
            return [AgentInfo.from_json(a) for a in agents]
        return []
