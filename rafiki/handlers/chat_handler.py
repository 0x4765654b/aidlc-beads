"""Chat handler — strategic conversations with Harmbe."""
from __future__ import annotations

import logging
from rafiki.models import ChatRecord

logger = logging.getLogger("rafiki.handlers.chat")


class ChatHandler:
    """Drives strategic chat interactions with Harmbe."""

    def __init__(self, chat_client, project_key: str):
        self.chat_client = chat_client
        self.project_key = project_key
        self.history: list[ChatRecord] = []

    async def chat(self, prompt: str) -> ChatRecord:
        """Send a message to Harmbe and record the response."""
        logger.info("Chat: %s", prompt)
        try:
            resp = await self.chat_client.send(self.project_key, prompt)
            response_text = resp.get("response", "") or resp.get("message", "") or str(resp)
        except Exception as exc:
            logger.warning("Chat failed: %s", exc)
            response_text = f"[Chat error: {exc}]"

        record = ChatRecord(prompt=prompt, response=response_text)
        self.history.append(record)
        return record

    async def on_project_created(self) -> ChatRecord:
        return await self.chat(
            f"What is the current status of the {self.project_key} project?"
        )

    async def on_phase_complete(self, phase_name: str) -> ChatRecord:
        return await self.chat(
            f"The {phase_name} phase just completed. What phase are we in now? What's next?"
        )

    async def on_stall(self, stage_name: str, stall_minutes: float) -> ChatRecord:
        return await self.chat(
            f"I haven't seen progress in {stall_minutes:.0f} minutes. "
            f"What's happening with {stage_name}?"
        )

    async def on_completion(self) -> ChatRecord:
        return await self.chat(
            f"Is the {self.project_key} project fully complete? What's the final status?"
        )
