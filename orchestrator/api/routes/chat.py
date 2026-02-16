"""Chat message handler -- conversational interface to Harmbe."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from orchestrator.api.deps import get_ws_manager, get_engine
from orchestrator.api.models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
)
from orchestrator.api.websocket import ConnectionManager
from orchestrator.engine.agent_engine import AgentEngine

logger = logging.getLogger("api.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

# In-memory chat history (project_key -> list of messages)
# "global" key stores cross-project messages
_chat_history: dict[str, list[ChatMessage]] = defaultdict(list)
MAX_HISTORY_PER_CHANNEL = 1000

# Lazy-initialized Harmbe agent for direct chat (no engine spawn overhead)
_harmbe_agent = None


def _get_harmbe():
    """Get or create a persistent Harmbe agent for chat."""
    global _harmbe_agent
    if _harmbe_agent is None:
        try:
            from orchestrator.config import get_config
            from orchestrator.agents.harmbe import Harmbe

            config = get_config()
            _harmbe_agent = Harmbe(bedrock_config=config.bedrock)
            logger.info("Harmbe chat agent initialized")
        except Exception as e:
            logger.warning("Could not create Harmbe agent: %s", e)
    return _harmbe_agent


def _build_conversation_context(channel: str, limit: int = 20) -> str:
    """Build conversation history string for LLM context.

    Args:
        channel: Chat channel key (project_key or "global").
        limit: Max recent messages to include.

    Returns:
        Formatted conversation history string.
    """
    history = _chat_history.get(channel, [])
    recent = history[-limit:]
    if not recent:
        return ""

    parts: list[str] = []
    for msg in recent:
        role = "Human" if msg.role == "user" else "Harmbe"
        parts.append(f"{role}: {msg.content}")
    return "\n".join(parts)


def _store_message(msg: ChatMessage) -> None:
    """Append a message to in-memory chat history."""
    channel = msg.project_key or "global"
    history = _chat_history[channel]
    history.append(msg)
    if len(history) > MAX_HISTORY_PER_CHANNEL:
        _chat_history[channel] = history[-MAX_HISTORY_PER_CHANNEL:]


@router.post("/", response_model=ChatResponse)
async def send_chat_message(
    body: ChatRequest,
    ws: ConnectionManager = Depends(get_ws_manager),
) -> ChatResponse:
    """Send a chat message to Harmbe and get a response.

    Routes the message to the Harmbe Strands agent backed by
    Claude Opus 4.6 on Bedrock. Includes conversation history as context.
    Falls back to a placeholder if the agent is unavailable.
    """
    now = datetime.now(timezone.utc).isoformat()
    msg_id = f"msg-{uuid.uuid4().hex[:8]}"

    user_msg = ChatMessage(
        message_id=msg_id,
        role="user",
        content=body.message,
        project_key=body.project_key,
        timestamp=now,
    )
    _store_message(user_msg)

    # Invoke Harmbe agent with conversation context
    harmbe = _get_harmbe()
    actions: list[str] = []

    if harmbe is not None:
        try:
            channel = body.project_key or "global"
            conversation = _build_conversation_context(channel)

            project_ctx = f" (project: {body.project_key})" if body.project_key else ""
            prompt_parts = []

            if conversation:
                prompt_parts.append(
                    "Here is the recent conversation history:\n"
                    f"{conversation}\n\n"
                )

            prompt_parts.append(
                f"The human says{project_ctx}: {body.message}\n\n"
                "Respond helpfully and concisely as Harmbe, the Gorilla Troop supervisor. "
                "You can help with: project status, reviewing artifacts, answering questions "
                "about the AIDLC workflow, explaining what agents are doing, and general guidance."
            )

            prompt = "".join(prompt_parts)
            response_text = await harmbe._invoke_llm(prompt)
            actions.append("harmbe_llm_invoked")
        except Exception as e:
            logger.error("Harmbe invocation failed: %s", e)
            response_text = f"Harmbe encountered an error: {e}"
    else:
        response_text = (
            f"Acknowledged: \"{body.message}\". "
            "Harmbe agent is not available (Strands SDK not configured). "
            "The Gorilla Troop system requires Amazon Bedrock access via the Strands Agents SDK."
        )

    response_id = f"msg-{uuid.uuid4().hex[:8]}"
    response_ts = datetime.now(timezone.utc).isoformat()

    assistant_msg = ChatMessage(
        message_id=response_id,
        role="assistant",
        content=response_text,
        project_key=body.project_key,
        timestamp=response_ts,
    )
    _store_message(assistant_msg)

    await ws.broadcast(
        "chat_message",
        body.project_key or "",
        {"message_id": response_id, "role": "assistant", "content": response_text},
    )

    return ChatResponse(
        message_id=response_id,
        response=response_text,
        project_key=body.project_key,
        actions_taken=actions,
        timestamp=response_ts,
    )


@router.get("/history", response_model=list[ChatMessage])
async def get_chat_history(
    project_key: str | None = None,
    limit: int = 50,
) -> list[ChatMessage]:
    """Get chat history for a project or global channel.

    Args:
        project_key: Filter by project. None returns global channel.
        limit: Maximum messages to return (most recent first).
    """
    channel = project_key or "global"
    history = _chat_history.get(channel, [])
    # Return most recent messages, newest last
    return history[-limit:]
