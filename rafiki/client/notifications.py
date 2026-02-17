"""Notification client."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class NotificationClient(BaseClient):
    async def list(self, project_key: str | None = None, unread_only: bool = False) -> list[dict]:
        params: dict = {}
        if project_key:
            params["project_key"] = project_key
        if unread_only:
            params["unread_only"] = "true"
        resp = await self._get("/api/notifications/", **params)
        return resp if isinstance(resp, list) else resp.get("notifications", [])

    async def count(self, project_key: str | None = None) -> int:
        params: dict = {}
        if project_key:
            params["project_key"] = project_key
        resp = await self._get("/api/notifications/count", **params)
        return resp.get("count", 0)

    async def mark_read(self, notification_id: str) -> dict:
        return await self._post(f"/api/notifications/{notification_id}/read")

    async def mark_all_read(self, project_key: str | None = None) -> dict:
        body = {}
        if project_key:
            body["project_key"] = project_key
        return await self._post("/api/notifications/read-all", body=body)
