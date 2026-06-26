"""Workable public job feed source."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ...company_sources.utils import DEFAULT_HEADERS
from .base import CompanySource, ProgressCallback
from .job_board_utils import board_slugs_from_context, gather_within_budget, job_matches, normalize_job_board_company


class WorkableSource(CompanySource):
    """Discover companies from Workable public accounts."""

    SOURCE_NAME = "Workable"
    DEFAULT_TIMEOUT_SECONDS = 24.0
    MAX_BOARDS = 160
    DEFAULT_CONCURRENCY = 24

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Searching Workable public feeds...")
        boards = board_slugs_from_context(profile, preferences)[:self.MAX_BOARDS]
        semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            async def fetch_board(board: str) -> dict[str, Any] | None:
                async with semaphore:
                    url = f"https://apply.workable.com/api/v3/accounts/{board}/jobs"
                    try:
                        data = await self._get_json(client, url, cache_key=f"workable:{board}")
                    except Exception:
                        return None

                    raw_jobs = data.get("results") or data.get("jobs") if isinstance(data, dict) else []
                    matched_jobs = []
                    for raw in raw_jobs or []:
                        job = {
                            "title": raw.get("title", ""),
                            "url": raw.get("url", "") or f"https://apply.workable.com/{board}/j/{raw.get('shortcode', '')}",
                            "location": raw.get("location", {}).get("city", "") if isinstance(raw.get("location"), dict) else raw.get("location", ""),
                            "department": raw.get("department", ""),
                            "description": raw.get("description", ""),
                            "posted_at": raw.get("published", ""),
                            "work_mode": raw.get("workplace", ""),
                            "source_work_mode_hint": raw.get("location", ""),
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
                        source_url=f"https://apply.workable.com/{board}",
                    )

            results = await gather_within_budget(
                [lambda b=board: fetch_board(b) for board in boards],
                budget_seconds=self.timeout_seconds - 3,
            )

        companies = [r for r in results if isinstance(r, dict)]
        await self._notify(progress_callback, f"Workable found {len(companies)} companies with matching roles")
        return companies
