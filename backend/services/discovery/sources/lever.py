"""Lever public postings source."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ...company_sources.utils import DEFAULT_HEADERS
from .base import CompanySource, ProgressCallback
from .job_board_utils import board_slugs_from_context, job_matches, normalize_job_board_company


class LeverSource(CompanySource):
    """Discover companies and roles through Lever's public postings API."""

    SOURCE_NAME = "Lever"
    DEFAULT_TIMEOUT_SECONDS = 18.0

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Searching Lever public postings...")
        boards = board_slugs_from_context(profile, preferences)[:80]
        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            async def fetch_company(board: str) -> dict[str, Any] | None:
                async with semaphore:
                    url = f"https://api.lever.co/v0/postings/{board}"
                    try:
                        raw_jobs = await self._get_json(client, url, params={"mode": "json"}, cache_key=f"lever:{board}")
                    except Exception:
                        return None

                    matched_jobs = []
                    for raw in raw_jobs or []:
                        categories = raw.get("categories") or {}
                        job = {
                            "title": raw.get("text", ""),
                            "url": raw.get("hostedUrl", ""),
                            "location": categories.get("location", ""),
                            "department": categories.get("team", ""),
                            "description": raw.get("descriptionPlain", "") or raw.get("description", ""),
                            "posted_at": raw.get("createdAt", ""),
                            "employment_type": categories.get("commitment", ""),
                            "work_mode": raw.get("workplaceType", ""),
                            "source_work_mode_hint": categories.get("location", ""),
                        }
                        if job_matches(job, queries, profile, preferences):
                            matched_jobs.append(job)

                    if not matched_jobs:
                        return None

                    return normalize_job_board_company(
                        source=self.SOURCE_NAME,
                        company_name=board.replace("-", " ").title(),
                        board_slug=board,
                        jobs=matched_jobs,
                        source_url=f"https://jobs.lever.co/{board}",
                    )

            results = await asyncio.gather(*(fetch_company(board) for board in boards), return_exceptions=True)

        companies = [r for r in results if isinstance(r, dict)]
        await self._notify(progress_callback, f"Lever found {len(companies)} companies with matching roles")
        return companies
