"""
Wellfound (AngelList) company discovery source.

Best-effort scrape of Wellfound startup job listings.
Returns empty list if Wellfound blocks the request.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, normalize_company, slugify_domain

WELLFOUND_JOBS_URL = "https://wellfound.com/jobs"


class WellfoundSource(CompanySource):
    """Discover startups via Wellfound job listings."""

    SOURCE_NAME = "Wellfound"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Scrape Wellfound job search results."""
        await self._notify(progress_callback, "Searching Wellfound for startup opportunities...")

        role_terms = (
            preferences.get("preferred_roles")
            or profile.get("preferred_domains")
            or queries[:1]
            or ["software engineer"]
        )
        query = quote(role_terms[0])
        target_url = f"{WELLFOUND_JOBS_URL}?query={query}"

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers={
                    **DEFAULT_HEADERS,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://wellfound.com/",
                },
            ) as client:
                response = await client.get(target_url)
                if response.status_code != 200:
                    return []
                soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            return []

        companies: dict[str, dict[str, Any]] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/company/" not in href and "/jobs/" not in href:
                continue

            text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            if not text or len(text) < 2:
                continue

            company_name = self._extract_company_name(text)
            if not company_name:
                continue

            company_url = urljoin(WELLFOUND_JOBS_URL, href)
            companies.setdefault(company_name, {
                "name": company_name,
                "domain": slugify_domain(company_name),
                "description": text[:180],
                "size": "Startup (< 50)",
                "funding_stage": "Startup",
                "hiring_status": "actively_hiring",
                "remote_friendly": "remote" in text.lower(),
                "source_url": company_url,
                "culture_tags": ["startup"],
            })

        results = [normalize_company(c, self.SOURCE_NAME) for c in companies.values()][:30]
        await self._notify(progress_callback, f"Found {len(results)} companies on Wellfound")
        return results

    @staticmethod
    def _extract_company_name(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.split(r"\s+[•·|\-]\s+", cleaned, maxsplit=1)[0]
        if len(cleaned) < 2 or len(cleaned) > 60:
            return ""
        return cleaned
