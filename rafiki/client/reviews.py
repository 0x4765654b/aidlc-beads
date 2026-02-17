"""Review gate client."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class ReviewClient(BaseClient):
    async def list(self, project_key: str | None = None) -> list[dict]:
        params = {}
        if project_key:
            params["project_key"] = project_key
        resp = await self._get("/api/review/", **params)
        return resp if isinstance(resp, list) else resp.get("reviews", [])

    async def get_detail(self, issue_id: str) -> dict:
        return await self._get(f"/api/review/{issue_id}")

    async def approve(self, issue_id: str, feedback: str = "") -> dict:
        body: dict = {"feedback": feedback}
        return await self._post(f"/api/review/{issue_id}/approve", body=body)

    async def reject(self, issue_id: str, feedback: str = "") -> dict:
        body: dict = {"feedback": feedback}
        return await self._post(f"/api/review/{issue_id}/reject", body=body)
