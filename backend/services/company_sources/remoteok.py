"""
RemoteOK company discovery source.

Fetches the RemoteOK public API and extracts companies that match the
candidate's skills and target roles.
"""

from __future__ import annotations

from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, extract_domain_from_url, normalize_company, slugify_domain

REMOTEOK_URL = "https://remoteok.com/api"


class RemoteOKSource(CompanySource):
    """Discover remote-friendly companies via the RemoteOK public API."""

    SOURCE_NAME = "RemoteOK"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Fetch job listings from RemoteOK and group by company."""
        await self._notify(progress_callback, "Searching RemoteOK for remote-friendly companies...")

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={**DEFAULT_HEADERS, "Accept": "application/json"},
                follow_redirects=True,
            ) as client:
                response = await client.get(REMOTEOK_URL)
                if response.status_code != 200:
                    return []
                jobs = response.json()
        except Exception:
            return []

        skills = {s.lower() for s in profile.get("skills", []) + profile.get("tech_stack", [])}
        roles = [r.lower() for r in (preferences.get("preferred_roles") or profile.get("preferred_domains", []))]
        query_terms = {q.lower() for q in queries}

        seen_companies: dict[str, dict[str, Any]] = {}
        company_match_counts: dict[str, int] = {}  # jobs that actually matched

        for job in jobs:
            if not isinstance(job, dict):
                continue
            company_name = job.get("company", "")
            if not company_name:
                continue

            title = (job.get("position", "") or "").lower()
            job_tags = {t.lower() for t in (job.get("tags", []) or [])}

            role_match = any(r in title for r in roles) if roles else False
            skill_match = bool(skills & job_tags)
            query_match = any(q in title for q in query_terms)  # only match in title, not company name

            is_relevant = role_match or skill_match or query_match

            # Only add a company if at least one job is directly relevant
            if not is_relevant and (roles or skills or query_terms):
                # Still track the company entry if already added, but don't count this job
                if company_name in seen_companies:
                    seen_companies[company_name]["open_positions"].append({
                        "title": job.get("position", ""),
                        "url": job.get("url", ""),
                        "work_mode": "remote",
                        "salary_range": (
                            f"${job.get('salary_min', 0):,} – ${job.get('salary_max', 0):,}"
                            if job.get("salary_min") else ""
                        ),
                        "posted_at": job.get("date", ""),
                    })
                continue

            if company_name not in seen_companies:
                job_url = job.get("url", "")
                domain = extract_domain_from_url(job_url) or slugify_domain(company_name)
                seen_companies[company_name] = {
                    "name": company_name,
                    "domain": domain,
                    "logo_url": job.get("company_logo", ""),
                    "hiring_status": "actively_hiring",
                    "remote_friendly": True,
                    "open_positions": [],
                    "source_url": "https://remoteok.com",
                }
                company_match_counts[company_name] = 0

            seen_companies[company_name]["open_positions"].append({
                "title": job.get("position", ""),
                "url": job.get("url", ""),
                "work_mode": "remote",
                "salary_range": (
                    f"${job.get('salary_min', 0):,} – ${job.get('salary_max', 0):,}"
                    if job.get("salary_min") else ""
                ),
                "posted_at": job.get("date", ""),
            })
            if is_relevant:
                company_match_counts[company_name] = company_match_counts.get(company_name, 0) + 1

        # Only keep companies where at least 1 of their relevant-job matches drove the inclusion
        # This filters out companies added solely because one unrelated tech job appeared
        qualified = {
            name: c for name, c in seen_companies.items()
            if company_match_counts.get(name, 0) >= 1
        }

        results = [normalize_company(c, self.SOURCE_NAME) for c in qualified.values()][:40]
        await self._notify(progress_callback, f"Found {len(results)} companies on RemoteOK")
        return results
