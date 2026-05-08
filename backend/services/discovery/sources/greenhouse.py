"""Greenhouse public job board source."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ...company_sources.utils import DEFAULT_HEADERS
from .base import CompanySource, ProgressCallback
from .job_board_utils import board_slugs_from_context, job_matches, normalize_job_board_company


class GreenhouseSource(CompanySource):
    """Discover companies and roles through the Greenhouse boards API."""

    SOURCE_NAME = "Greenhouse"
    DEFAULT_TIMEOUT_SECONDS = 18.0

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Probing Greenhouse public job boards...")
        boards = board_slugs_from_context(profile, preferences)[:80]
        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            async def fetch_board(board: str) -> dict[str, Any] | None:
                async with semaphore:
                    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
                    try:
                        data = await self._get_json(client, url, params={"content": "true"}, cache_key=f"greenhouse:{board}")
                    except Exception:
                        return None

                    raw_jobs = data.get("jobs") if isinstance(data, dict) else []
                    matched_jobs = []
                    for raw in raw_jobs or []:
                        job = {
                            "title": raw.get("title", ""),
                            "url": raw.get("absolute_url", ""),
                            "location": (raw.get("location") or {}).get("name", ""),
                            "department": (raw.get("departments") or [{}])[0].get("name", ""),
                            "description": raw.get("content", ""),
                            "posted_at": raw.get("updated_at", ""),
                            "work_mode": "remote" if "remote" in str(raw).lower() else "",
                        }
                        if job_matches(job, queries, profile, preferences):
                            matched_jobs.append(job)

                    if not matched_jobs:
                        return None

                    company_name = board.replace("-", " ").title()
                    return normalize_job_board_company(
                        source=self.SOURCE_NAME,
                        company_name=company_name,
                        board_slug=board,
                        jobs=matched_jobs,
                        source_url=f"https://boards.greenhouse.io/{board}",
                    )

            results = await asyncio.gather(*(fetch_board(board) for board in boards), return_exceptions=True)

        companies = [r for r in results if isinstance(r, dict)]
        await self._notify(progress_callback, f"Greenhouse found {len(companies)} companies with matching roles")
        return companies
