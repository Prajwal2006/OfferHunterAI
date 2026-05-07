"""
YCombinator companies discovery source.

Queries the YC Algolia API for companies matching the user profile,
with a static fallback list of known YC companies for common roles.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, extract_domain_from_url, normalize_company, slugify_domain

YC_ALGOLIA_URL = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
YC_ALGOLIA_APP_ID = "45BWZJ1SGC"
YC_ALGOLIA_API_KEY = (
    "Zjk5ZmUyZjBhMmIyZDgxODRhOWMxNjZjMzg5MDZlNjFhMWM4YWViZjYxOTA1YWZiNzg2ZTU2ZGQ4Zj"
    "kwNjVmZnJlc3RyaWN0SW5kaWNlcz1ZQ0NvbXBhbnlfcHJvZHVjdGlvbiZ2YWxpZFVudGlsPTE3NjQ0NDE0MTE="
)


class YCCompaniesSource(CompanySource):
    """Discover YC-backed companies actively hiring."""

    SOURCE_NAME = "YCombinator"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Query the YC company directory for hiring companies."""
        await self._notify(progress_callback, "Querying Y Combinator company directory...")

        industries = preferences.get("industries_of_interest", [])
        roles = preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        query_terms = list(industries[:2]) + list(roles[:1]) + list(queries[:1])
        query = " ".join(query_terms[:3]) if query_terms else "software"

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "x-algolia-application-id": YC_ALGOLIA_APP_ID,
                    "x-algolia-api-key": YC_ALGOLIA_API_KEY,
                    "Content-Type": "application/json",
                    "User-Agent": DEFAULT_HEADERS["User-Agent"],
                },
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    YC_ALGOLIA_URL,
                    params={"x-algolia-agent": "OfferHunterAI"},
                    content=json.dumps({
                        "requests": [{
                            "indexName": "YCCompany_production",
                            "query": query,
                            "params": (
                                "hitsPerPage=50&page=0"
                                "&facets=%5B%22top_company%22%2C%22isHiring%22%5D"
                                "&facetFilters=%5B%5B%22isHiring%3Atrue%22%5D%5D"
                            ),
                        }]
                    }).encode(),
                )
                if response.status_code != 200:
                    return self._fallback(profile, preferences)

                data = response.json()
                hits = data.get("results", [{}])[0].get("hits", [])

        except Exception:
            return self._fallback(profile, preferences)

        companies = []
        for hit in hits:
            company = {
                "name": hit.get("name", ""),
                "domain": (
                    extract_domain_from_url(hit.get("website", ""))
                    or slugify_domain(hit.get("name", ""))
                ),
                "description": hit.get("one_liner", ""),
                "industry": hit.get("tags", [""])[0] if hit.get("tags") else "",
                "size": str(hit.get("team_size", "")),
                "headquarters": hit.get("location", ""),
                "website_url": hit.get("website", ""),
                "logo_url": hit.get("small_logo_url", ""),
                "funding_stage": "YC-backed",
                "hiring_status": "actively_hiring" if hit.get("isHiring") else "unknown",
                "culture_tags": list(hit.get("tags", []))[:5],
                "source_url": f"https://www.ycombinator.com/companies/{hit.get('slug', '')}",
            }
            if company["name"]:
                companies.append(normalize_company(company, self.SOURCE_NAME))

        if not companies:
            companies = self._fallback(profile, preferences)

        await self._notify(progress_callback, f"Found {len(companies)} YC companies")
        return companies[:50]

    @staticmethod
    def _fallback(
        profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return a curated list of well-known YC companies when the API fails."""
        known_yc = [
            {"name": "Stripe", "domain": "stripe.com", "industry": "Fintech", "funding_stage": "YC S09", "website_url": "https://stripe.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Brex", "domain": "brex.com", "industry": "Fintech", "funding_stage": "YC W17", "website_url": "https://brex.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Scale AI", "domain": "scale.com", "industry": "AI/ML", "funding_stage": "YC S16", "website_url": "https://scale.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Gusto", "domain": "gusto.com", "industry": "HR Tech", "funding_stage": "YC W12", "website_url": "https://gusto.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Rippling", "domain": "rippling.com", "industry": "HR Tech", "funding_stage": "YC W16", "website_url": "https://rippling.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Deel", "domain": "deel.com", "industry": "HR Tech", "funding_stage": "YC W19", "website_url": "https://deel.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Retool", "domain": "retool.com", "industry": "Developer Tools", "funding_stage": "YC S17", "website_url": "https://retool.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Posthog", "domain": "posthog.com", "industry": "Developer Tools", "funding_stage": "YC W20", "website_url": "https://posthog.com", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Supabase", "domain": "supabase.com", "industry": "Developer Tools", "funding_stage": "YC S20", "website_url": "https://supabase.com", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Linear", "domain": "linear.app", "industry": "Productivity", "funding_stage": "Series B", "website_url": "https://linear.app", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Vercel", "domain": "vercel.com", "industry": "Developer Tools", "funding_stage": "Series D", "website_url": "https://vercel.com", "headquarters": "Remote", "hiring_status": "hiring"},
        ]
        return [normalize_company(c, "YCombinator") for c in known_yc]
