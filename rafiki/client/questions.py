"""Q&A question client."""
from __future__ import annotations
from rafiki.client.base import BaseClient


class QuestionClient(BaseClient):
    """Client for the /api/questions/ endpoints.

    Stores a default ``project_key`` so every call targets the correct
    per-project Beads database.
    """

    def __init__(self, base_url: str, project_key: str | None = None, **kwargs):
        super().__init__(base_url, **kwargs)
        self.project_key = project_key

    async def list(self, project_key: str | None = None) -> list[dict]:
        pk = project_key or self.project_key
        params = {"project_key": pk} if pk else {}
        resp = await self._get("/api/questions/", **params)
        return resp if isinstance(resp, list) else resp.get("questions", [])

    async def get_detail(self, issue_id: str) -> dict:
        pk = self.project_key
        params = {"project_key": pk} if pk else {}
        return await self._get(f"/api/questions/{issue_id}", **params)

    async def answer(self, issue_id: str, answer: str) -> dict:
        pk = self.project_key
        url = f"/api/questions/{issue_id}/answer"
        if pk:
            url += f"?project_key={pk}"
        return await self._post(url, body={"answer": answer})
