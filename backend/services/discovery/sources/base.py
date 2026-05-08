"""Base classes for API-first company intelligence sources."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

import httpx

from ..source_metrics import SourceHealth

ProgressCallback = Callable[[str, str], Coroutine[Any, Any, None]] | None


class CompanySource(ABC):
    """Uniform async adapter contract for company discovery sources."""

    SOURCE_NAME = "Unknown"
    DEFAULT_TIMEOUT_SECONDS = 20.0
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_CONCURRENCY = 8

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self.max_retries = self.DEFAULT_MAX_RETRIES if max_retries is None else max_retries
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl_seconds = 60 * 60

    @abstractmethod
    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Return normalized company dictionaries."""

    async def health(self) -> SourceHealth:
        return SourceHealth(source=self.SOURCE_NAME)

    async def _notify(self, progress_callback: ProgressCallback, message: str) -> None:
        if progress_callback:
            try:
                await progress_callback(self.SOURCE_NAME, message)
            except Exception:
                pass

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> Any:
        key = cache_key or f"GET:{url}:{params}"
        cached = self._cache.get(key)
        now = time.time()
        if cached and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                self._cache[key] = (now, data)
                return data
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(0.4 * (2 ** attempt))

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed to fetch {url}")
