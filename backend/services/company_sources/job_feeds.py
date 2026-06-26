"""
Public job-board feed sources.

Each adapter pulls real, open job *listings* from a free public API, filters them
to the candidate's roles/skills, groups them by employer, and returns company
dicts with populated ``open_positions``. These feeds surface a long tail of
roles — remote-first startups, EU/global employers, niche boards — that rarely
get promoted on the big aggregators, directly serving "jobs that are not that
publicized."

All adapters degrade gracefully: any network/parse error yields an empty list so
one slow or unavailable feed never breaks discovery.
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from .base import CompanySource, ProgressCallback
from .utils import (
    DEFAULT_HEADERS,
    extract_domain_from_url,
    infer_industry,
    infer_tech_stack,
    normalize_company,
    slugify_domain,
)


def _terms(profile: dict[str, Any], preferences: dict[str, Any], queries: list[str]) -> tuple[list[str], list[str], list[str]]:
    roles = [
        str(r).lower()
        for r in (preferences.get("preferred_roles") or profile.get("preferred_domains") or [])
        if r
    ]
    skills = [
        str(s).lower()
        for s in (profile.get("skills", []) + profile.get("tech_stack", []))
        if s
    ]
    query_terms = [str(q).lower() for q in (queries or []) if q]
    return roles, skills, query_terms


def _job_is_relevant(
    title: str,
    description: str,
    tags: Iterable[str],
    roles: list[str],
    skills: list[str],
    query_terms: list[str],
) -> bool:
    """Relevant if any role/skill/query term appears, or if no signals were given."""
    haystack = " ".join(
        [title or "", description or "", " ".join(str(t) for t in (tags or []))]
    ).lower()
    if not (roles or skills or query_terms):
        return True
    if any(r in haystack for r in roles):
        return True
    if any(s in title.lower() or s in haystack for s in skills):
        return True
    return any(q in haystack for q in query_terms)


def build_company_results(
    *,
    jobs: list[dict[str, Any]],
    source: str,
    source_url: str,
    profile: dict[str, Any],
    preferences: dict[str, Any],
    queries: list[str],
    max_companies: int = 40,
    max_jobs_per_company: int = 20,
) -> list[dict[str, Any]]:
    """Group normalized job dicts by employer and keep only relevant companies.

    Each ``job`` should carry: company, title, url, location, work_mode, tags,
    salary_range, posted_at, description, logo_url, company_url.
    """
    roles, skills, query_terms = _terms(profile, preferences, queries)
    excluded_domains = {str(d).lower().strip() for d in (preferences.get("_excluded_domains") or [])}
    excluded_names = {str(n).lower().strip() for n in (preferences.get("_excluded_names") or [])}

    grouped: dict[str, dict[str, Any]] = {}
    relevant_count: dict[str, int] = {}

    for job in jobs:
        company_name = (job.get("company") or "").strip()
        if not company_name or company_name.lower() in excluded_names:
            continue

        is_relevant = _job_is_relevant(
            job.get("title", ""),
            job.get("description", ""),
            job.get("tags", []),
            roles,
            skills,
            query_terms,
        )

        entry = grouped.get(company_name)
        if entry is None:
            company_url = job.get("company_url") or ""
            domain = (
                extract_domain_from_url(company_url)
                or extract_domain_from_url(job.get("url", ""))
                or slugify_domain(company_name)
            )
            if domain.lower() in excluded_domains:
                continue
            entry = {
                "name": company_name,
                "domain": domain,
                "logo_url": job.get("logo_url", ""),
                "website_url": company_url,
                "hiring_status": "actively_hiring",
                "remote_friendly": False,
                "open_positions": [],
                "source_url": source_url,
                "_text": [],
            }
            grouped[company_name] = entry
            relevant_count[company_name] = 0

        if len(entry["open_positions"]) < max_jobs_per_company:
            entry["open_positions"].append(
                {
                    "title": job.get("title", ""),
                    "url": job.get("url", ""),
                    "location": job.get("location", ""),
                    "work_mode": job.get("work_mode", ""),
                    "salary_range": job.get("salary_range", ""),
                    "posted_at": job.get("posted_at", ""),
                    "employment_type": job.get("employment_type", ""),
                }
            )
        entry["_text"].append(f"{job.get('title', '')} {job.get('description', '')}")
        if (job.get("work_mode") or "").lower() == "remote" or job.get("is_remote"):
            entry["remote_friendly"] = True
        if is_relevant:
            relevant_count[company_name] += 1

    results: list[dict[str, Any]] = []
    for name, entry in grouped.items():
        if relevant_count.get(name, 0) < 1:
            continue
        text = " ".join(entry.pop("_text", []))[:4000]
        entry["industry"] = infer_industry(text)
        entry["tech_stack"] = infer_tech_stack(text)
        entry["description"] = (
            f"Actively hiring via {source}; {len(entry['open_positions'])} open role(s) matched."
        )
        entry["relevance_score"] = min(0.92, 0.5 + min(relevant_count[name], 8) * 0.05)
        results.append(normalize_company(entry, source))

    results.sort(key=lambda c: len(c.get("open_positions") or []), reverse=True)
    return results[:max_companies]


class _JobFeedSource(CompanySource):
    """Base for single-GET public job feeds."""

    SOURCE_NAME = "JobFeed"
    FEED_URL = ""
    SOURCE_URL = ""
    TIMEOUT = 15.0

    async def _fetch(self, params: dict[str, Any] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True
            ) as client:
                response = await client.get(self.FEED_URL, params=params)
                if response.status_code != 200:
                    return None
                return response.json()
        except Exception:
            return None

    def _parse(self, data: Any) -> list[dict[str, Any]]:  # pragma: no cover - overridden
        raise NotImplementedError

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, f"Searching {self.SOURCE_NAME} for open roles...")
        data = await self._fetch(self._params(profile, preferences, queries))
        if data is None:
            return []
        jobs = self._parse(data)
        results = build_company_results(
            jobs=jobs,
            source=self.SOURCE_NAME,
            source_url=self.SOURCE_URL,
            profile=profile,
            preferences=preferences,
            queries=queries,
        )
        await self._notify(
            progress_callback, f"{self.SOURCE_NAME} found {len(results)} companies with matching roles"
        )
        return results

    def _params(
        self, profile: dict[str, Any], preferences: dict[str, Any], queries: list[str]
    ) -> dict[str, Any] | None:
        return None


class RemotiveSource(_JobFeedSource):
    """Remote jobs from Remotive's free public API (remotive.com)."""

    SOURCE_NAME = "Remotive"
    FEED_URL = "https://remotive.com/api/remote-jobs"
    SOURCE_URL = "https://remotive.com/remote-jobs"

    def _parse(self, data: Any) -> list[dict[str, Any]]:
        jobs = []
        for raw in (data or {}).get("jobs", []) if isinstance(data, dict) else []:
            jobs.append(
                {
                    "company": raw.get("company_name", ""),
                    "title": raw.get("title", ""),
                    "url": raw.get("url", ""),
                    "location": raw.get("candidate_required_location", ""),
                    "work_mode": "remote",
                    "is_remote": True,
                    "tags": raw.get("tags", []) or [],
                    "salary_range": raw.get("salary", "") or "",
                    "posted_at": raw.get("publication_date", ""),
                    "employment_type": raw.get("job_type", ""),
                    "description": raw.get("description", ""),
                    "logo_url": raw.get("company_logo", "") or "",
                }
            )
        return jobs


class ArbeitnowSource(_JobFeedSource):
    """EU/global + remote jobs from the free Arbeitnow job-board API."""

    SOURCE_NAME = "Arbeitnow"
    FEED_URL = "https://www.arbeitnow.com/api/job-board-api"
    SOURCE_URL = "https://www.arbeitnow.com/"

    def _parse(self, data: Any) -> list[dict[str, Any]]:
        jobs = []
        for raw in (data or {}).get("data", []) if isinstance(data, dict) else []:
            jobs.append(
                {
                    "company": raw.get("company_name", ""),
                    "title": raw.get("title", ""),
                    "url": raw.get("url", ""),
                    "location": raw.get("location", ""),
                    "work_mode": "remote" if raw.get("remote") else "",
                    "is_remote": bool(raw.get("remote")),
                    "tags": (raw.get("tags") or []) + (raw.get("job_types") or []),
                    "posted_at": raw.get("created_at", ""),
                    "description": raw.get("description", ""),
                }
            )
        return jobs


class JobicySource(_JobFeedSource):
    """Curated remote jobs from the free Jobicy API."""

    SOURCE_NAME = "Jobicy"
    FEED_URL = "https://jobicy.com/api/v2/remote-jobs"
    SOURCE_URL = "https://jobicy.com/"

    def _params(self, profile, preferences, queries):
        return {"count": 50}

    def _parse(self, data: Any) -> list[dict[str, Any]]:
        jobs = []
        for raw in (data or {}).get("jobs", []) if isinstance(data, dict) else []:
            industries = raw.get("jobIndustry") or []
            jobs.append(
                {
                    "company": raw.get("companyName", ""),
                    "title": raw.get("jobTitle", ""),
                    "url": raw.get("url", ""),
                    "location": raw.get("jobGeo", ""),
                    "work_mode": "remote",
                    "is_remote": True,
                    "tags": industries if isinstance(industries, list) else [industries],
                    "salary_range": (
                        f"{raw.get('annualSalaryMin')} - {raw.get('annualSalaryMax')} {raw.get('salaryCurrency', '')}".strip()
                        if raw.get("annualSalaryMin")
                        else ""
                    ),
                    "posted_at": raw.get("pubDate", ""),
                    "employment_type": ", ".join(raw.get("jobType", []) or []),
                    "description": raw.get("jobExcerpt", "") or raw.get("jobDescription", ""),
                    "logo_url": raw.get("companyLogo", "") or "",
                }
            )
        return jobs


class TheMuseSource(_JobFeedSource):
    """Vetted company jobs from The Muse's free public API."""

    SOURCE_NAME = "TheMuse"
    FEED_URL = "https://www.themuse.com/api/public/jobs"
    SOURCE_URL = "https://www.themuse.com/jobs"

    def _params(self, profile, preferences, queries):
        return {"page": 0}

    def _parse(self, data: Any) -> list[dict[str, Any]]:
        jobs = []
        for raw in (data or {}).get("results", []) if isinstance(data, dict) else []:
            company = (raw.get("company") or {}).get("name", "")
            locations = [
                loc.get("name", "")
                for loc in (raw.get("locations") or [])
                if isinstance(loc, dict)
            ]
            location = ", ".join(locations)
            jobs.append(
                {
                    "company": company,
                    "title": raw.get("name", ""),
                    "url": (raw.get("refs") or {}).get("landing_page", ""),
                    "location": location,
                    "work_mode": "remote" if "remote" in location.lower() else "",
                    "is_remote": "remote" in location.lower(),
                    "tags": [lvl.get("name", "") for lvl in (raw.get("levels") or []) if isinstance(lvl, dict)],
                    "posted_at": raw.get("publication_date", ""),
                    "description": raw.get("contents", "") or "",
                }
            )
        return jobs
