"""Q&A question client."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class QuestionClient(BaseClient):
    async def list(self, project_key: str | None = None) -> list[dict]:
        params = {}
        if project_key:
            params["project_key"] = project_key
        resp = await self._get("/api/questions/", **params)
        return resp if isinstance(resp, list) else resp.get("questions", [])

    async def get_detail(self, issue_id: str) -> dict:
        return await self._get(f"/api/questions/{issue_id}")

    async def answer(self, issue_id: str, answer: str) -> dict:
        return await self._post(f"/api/questions/{issue_id}/answer", body={"answer": answer})
