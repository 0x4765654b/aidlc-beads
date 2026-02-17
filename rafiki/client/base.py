"""Base async HTTP client with retry logic."""
from __future__ import annotations
import httpx
import asyncio
import logging

logger = logging.getLogger("rafiki.client")

class BaseClient:
    """Thin async HTTP wrapper around httpx."""
    
    def __init__(self, base_url: str, timeout: float = 30.0, max_retries: int = 3, retry_delay: float = 2.0):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def _request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None) -> dict:
        """Make an HTTP request with retry logic for 5xx and connection errors."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._ensure_client()
                resp = await client.request(method, path, json=body, params=params)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    logger.warning("Server error %d on %s %s (attempt %d)", resp.status_code, method, path, attempt + 1)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()
            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = min(self.retry_delay * (2 ** attempt), 30.0)
                    logger.warning("Connection error on %s %s (attempt %d), retrying in %.1fs", method, path, attempt + 1, delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.HTTPStatusError:
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Retry loop exited unexpectedly")

    async def _get(self, path: str, **params) -> dict:
        return await self._request("GET", path, params=params if params else None)

    async def _post(self, path: str, body: dict | None = None) -> dict:
        return await self._request("POST", path, body=body)

    async def _put(self, path: str, body: dict | None = None) -> dict:
        return await self._request("PUT", path, body=body)

    async def _delete(self, path: str) -> dict:
        return await self._request("DELETE", path)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
