"""File upload/download client."""
from __future__ import annotations
from rafiki.client.base import BaseClient


class FileClient(BaseClient):
    async def write(self, project_key: str, path: str, content: str) -> dict:
        return await self._post(
            f"/api/projects/{project_key}/files",
            body={"path": path, "content": content},
        )

    async def read(self, project_key: str, path: str) -> dict:
        return await self._get(
            f"/api/projects/{project_key}/files",
            path=path,
        )
