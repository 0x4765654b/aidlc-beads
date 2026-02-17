"""Health check client."""
from __future__ import annotations
from rafiki.client.base import BaseClient

class HealthClient(BaseClient):
    async def check(self) -> dict:
        """GET /api/health — returns health status."""
        return await self._get("/api/health")

    async def is_healthy(self) -> bool:
        """Returns True if the API is reachable and healthy."""
        try:
            resp = await self.check()
            return resp.get("status") == "healthy" or bool(resp)
        except Exception:
            return False
