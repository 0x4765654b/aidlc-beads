"""Orchestrator logs client."""
from __future__ import annotations
from rafiki.client.base import BaseClient


class LogsClient(BaseClient):
    async def list(
        self,
        project_key: str | None = None,
        level: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[dict]:
        params: dict = {"limit": str(limit)}
        if project_key:
            params["project_key"] = project_key
        if level:
            params["level"] = level
        if since:
            params["since"] = since
        resp = await self._get("/api/logs/", **params)
        return resp if isinstance(resp, list) else []
