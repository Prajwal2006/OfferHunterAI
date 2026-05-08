"""Social and community discovery sources."""

from __future__ import annotations

from typing import Any

from ...company_sources.hackernews import HackerNewsSource
from .base import ProgressCallback


class HackerNewsHiringMiningSource(HackerNewsSource):
    """HN hiring mining wrapped as a community intelligence adapter."""

    SOURCE_NAME = "HackerNewsHiring"


class RedditStartupHiringSource:
    """Placeholder adapter for Reddit startup hiring feeds."""

    SOURCE_NAME = "RedditHiring"
    timeout_seconds = 12.0

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        if progress_callback:
            await progress_callback(self.SOURCE_NAME, "Reddit hiring discovery requires a configured Reddit API client")
        return []
