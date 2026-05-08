"""
Work at a Startup company discovery source.

Scrapes the Y Combinator Work at a Startup job board for early-stage companies
that are actively hiring.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, normalize_company, slugify_domain, infer_industry

WORK_AT_A_STARTUP_URL = "https://www.workatastartup.com/jobs"


class WorkAtAStartupSource(CompanySource):
    """Discover YC-backed startups via the Work at a Startup job board."""

    SOURCE_NAME = "WorkAtAStartup"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Scrape Work at a Startup for matching companies."""
        await self._notify(progress_callback, "Searching Work at a Startup (YC-backed companies)...")

        roles = (
            preferences.get("preferred_roles")
            or profile.get("preferred_domains")
            or queries[:1]
            or ["software-engineer"]
        )
        role_slug = quote(roles[0].lower().replace(" ", "-"))
        remote_only = (preferences.get("work_mode") or "").lower() == "remote"

        target_url = (
            f"{WORK_AT_A_STARTUP_URL}/r/{role_slug}"
            if remote_only
            else f"{WORK_AT_A_STARTUP_URL}/l/{role_slug}"
        )

        soup: BeautifulSoup | None = None
        try:
            async with httpx.AsyncClient(
                timeout=20.0, headers=DEFAULT_HEADERS, follow_redirects=True
            ) as client:
                response = await client.get(target_url)
                if response.status_code != 200:
                    response = await client.get(WORK_AT_A_STARTUP_URL)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            return []

        if not soup:
            return []

        companies: dict[str, dict[str, Any]] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/companies/" not in href:
                continue

            line = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            if not line:
                continue

            company_name, descriptor = self._parse_company_line(line)
            if not company_name:
                continue

            company_url = urljoin(WORK_AT_A_STARTUP_URL, href)
            job_anchor = anchor.find_next("a", href=re.compile(r"/jobs/\d+"))
            job_title = job_anchor.get_text(" ", strip=True) if job_anchor else ""
            job_url = (
                urljoin(WORK_AT_A_STARTUP_URL, job_anchor["href"])
                if job_anchor
                else company_url
            )

            company = companies.setdefault(company_name, {
                "name": company_name,
                "domain": slugify_domain(company_name),
                "description": descriptor,
                "industry": infer_industry(descriptor),
                "size": "Startup (< 50)",
                "funding_stage": "YC-backed",
                "hiring_status": "actively_hiring",
                "remote_friendly": "remote" in line.lower(),
                "source_url": company_url,
                "open_positions": [],
                "culture_tags": ["startup", "yc"],
            })
            if job_title:
                company["open_positions"].append({
                    "title": job_title,
                    "url": job_url,
                    "work_mode": "remote" if "remote" in line.lower() else "hybrid_or_onsite",
                })

        results = [normalize_company(c, self.SOURCE_NAME) for c in companies.values()][:40]
        await self._notify(progress_callback, f"Found {len(results)} companies on Work at a Startup")
        return results

    @staticmethod
    def _parse_company_line(line: str) -> tuple[str, str]:
        m = re.match(r"^(?P<name>.+?)\s*\((?P<batch>[^)]+)\)\s*[•\-]\s*(?P<desc>.+)$", line)
        if m:
            return m.group("name").strip(), m.group("desc").strip()
        parts = line.split("•", 1)
        return parts[0].strip(), line
