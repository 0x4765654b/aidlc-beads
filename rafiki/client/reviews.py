"""Review gate client."""
from __future__ import annotations
from rafiki.client.base import BaseClient


class ReviewClient(BaseClient):
    """Client for the /api/review/ endpoints.

    Stores a default ``project_key`` so every call targets the correct
    per-project Beads database.
    """

    def __init__(self, base_url: str, project_key: str | None = None, **kwargs):
        super().__init__(base_url, **kwargs)
        self.project_key = project_key

    def _pk_params(self, extra: dict | None = None) -> dict:
        params: dict = {}
        if self.project_key:
            params["project_key"] = self.project_key
        if extra:
            params.update(extra)
        return params

    async def list(self, project_key: str | None = None) -> list[dict]:
        pk = project_key or self.project_key
        params = {"project_key": pk} if pk else {}
        resp = await self._get("/api/review/", **params)
        return resp if isinstance(resp, list) else resp.get("reviews", [])

    async def get_detail(self, issue_id: str, project_key: str | None = None) -> dict:
        pk = project_key or self.project_key
        params = {"project_key": pk} if pk else {}
        return await self._get(f"/api/review/{issue_id}", **params)

    async def approve(self, issue_id: str, feedback: str = "") -> dict:
        body: dict = {"feedback": feedback}
        pk = self.project_key
        url = f"/api/review/{issue_id}/approve"
        if pk:
            url += f"?project_key={pk}"
        return await self._post(url, body=body)

    async def reject(self, issue_id: str, feedback: str = "") -> dict:
        body: dict = {"feedback": feedback}
        pk = self.project_key
        url = f"/api/review/{issue_id}/reject"
        if pk:
            url += f"?project_key={pk}"
        return await self._post(url, body=body)
