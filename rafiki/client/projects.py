"""Project management client."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class ProjectClient(BaseClient):
    async def create(self, project_key: str, name: str, workspace_path: str) -> dict:
        body = {"key": project_key, "name": name, "workspace_path": workspace_path}
        return await self._post("/api/projects/", body=body)

    async def list(self) -> list[dict]:
        resp = await self._get("/api/projects/")
        return resp if isinstance(resp, list) else resp.get("projects", [])

    async def get(self, project_key: str) -> dict:
        return await self._get(f"/api/projects/{project_key}")

    async def status(self, project_key: str) -> dict:
        return await self._get(f"/api/projects/{project_key}/status")

    async def pause(self, project_key: str) -> dict:
        return await self._post(f"/api/projects/{project_key}/pause")

    async def resume(self, project_key: str) -> dict:
        return await self._post(f"/api/projects/{project_key}/resume")

    async def delete(self, project_key: str) -> dict:
        return await self._delete(f"/api/projects/{project_key}")
