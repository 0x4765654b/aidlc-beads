"""Chat client for conversing with Harmbe."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class ChatClient(BaseClient):
    async def send(self, project_key: str, message: str) -> dict:
        return await self._post("/api/chat/", body={"project_key": project_key, "message": message})

    async def history(self, project_key: str, limit: int = 50) -> list[dict]:
        resp = await self._get("/api/chat/history", project_key=project_key, limit=limit)
        return resp if isinstance(resp, list) else resp.get("messages", [])
