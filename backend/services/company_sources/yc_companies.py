"""
YCombinator companies discovery source.

Queries the YC Algolia API for companies matching the user profile,
with a static fallback list of known YC companies for common roles.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, extract_domain_from_url, normalize_company, slugify_domain

# YC's public site uses a time-limited Algolia "secured" API key. The bundled
# default below expires (the validUntil timestamp is encoded in the key), after
# which the live query returns no hits and discovery falls back to the static
# list. Refresh without a code change by setting YC_ALGOLIA_API_KEY (and, if it
# ever changes, YC_ALGOLIA_APP_ID) — grab the current key from the network tab
# on ycombinator.com/companies.
YC_ALGOLIA_APP_ID = os.getenv("YC_ALGOLIA_APP_ID", "45BWZJ1SGC")
YC_ALGOLIA_URL = f"https://{YC_ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
YC_ALGOLIA_API_KEY = os.getenv(
    "YC_ALGOLIA_API_KEY",
    (
        "Zjk5ZmUyZjBhMmIyZDgxODRhOWMxNjZjMzg5MDZlNjFhMWM4YWViZjYxOTA1YWZiNzg2ZTU2ZGQ4Zj"
        "kwNjVmZnJlc3RyaWN0SW5kaWNlcz1ZQ0NvbXBhbnlfcHJvZHVjdGlvbiZ2YWxpZFVudGlsPTE3NjQ0NDE0MTE="
    ),
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
        """Return less-obvious YC companies when the API fails.

        This is a resilience fallback, not production mock data. Keep it broad
        and honor already-seen filters so API failures do not collapse discovery
        back to the same famous companies.
        """
        excluded_domains = {str(d).lower().strip() for d in preferences.get("_excluded_domains", [])}
        excluded_names = {str(n).lower().strip() for n in preferences.get("_excluded_names", [])}
        known_yc = [
            {"name": "AtoB", "domain": "atob.com", "industry": "Fintech", "funding_stage": "YC S20", "website_url": "https://atob.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Instawork", "domain": "instawork.com", "industry": "Labor Marketplace", "funding_stage": "YC S15", "website_url": "https://instawork.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Fintoc", "domain": "fintoc.com", "industry": "Fintech", "funding_stage": "YC W21", "website_url": "https://fintoc.com", "headquarters": "Santiago, Chile", "hiring_status": "hiring"},
            {"name": "Turso", "domain": "turso.tech", "industry": "Developer Tools", "funding_stage": "Series A", "website_url": "https://turso.tech", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Mintlify", "domain": "mintlify.com", "industry": "Developer Tools", "funding_stage": "YC W22", "website_url": "https://mintlify.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Corgi", "domain": "corgi.insure", "industry": "Insurtech", "funding_stage": "YC S23", "website_url": "https://corgi.insure", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Infisical", "domain": "infisical.com", "industry": "Security", "funding_stage": "YC W23", "website_url": "https://infisical.com", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Helicone", "domain": "helicone.ai", "industry": "AI / Developer Tools", "funding_stage": "YC W23", "website_url": "https://helicone.ai", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Langfuse", "domain": "langfuse.com", "industry": "AI / Observability", "funding_stage": "Seed", "website_url": "https://langfuse.com", "headquarters": "Berlin, Germany", "hiring_status": "hiring"},
            {"name": "Pave Robotics", "domain": "paverobotics.com", "industry": "Robotics", "funding_stage": "YC S24", "website_url": "https://paverobotics.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Salvy", "domain": "salvy.com.br", "industry": "Telecom", "funding_stage": "YC W22", "website_url": "https://salvy.com.br", "headquarters": "Sao Paulo, Brazil", "hiring_status": "hiring"},
            {"name": "Trigo", "domain": "trigo.com", "industry": "Retail Tech", "funding_stage": "YC", "website_url": "https://trigo.com", "headquarters": "Tel Aviv, Israel", "hiring_status": "hiring"},
            {"name": "Speak", "domain": "speak.com", "industry": "AI / EdTech", "funding_stage": "YC W17", "website_url": "https://speak.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Lago", "domain": "getlago.com", "industry": "Billing / Dev Tools", "funding_stage": "YC S21", "website_url": "https://getlago.com", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Trace", "domain": "trace.space", "industry": "Hardware / PLM", "funding_stage": "YC W23", "website_url": "https://trace.space", "headquarters": "New York, NY", "hiring_status": "hiring"},
            {"name": "Cedana", "domain": "cedana.ai", "industry": "AI Infrastructure", "funding_stage": "YC S24", "website_url": "https://cedana.ai", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Lightski", "domain": "lightski.com", "industry": "AI / Analytics", "funding_stage": "YC W24", "website_url": "https://lightski.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Mirou", "domain": "mirou.io", "industry": "AI / Healthcare", "funding_stage": "YC", "website_url": "https://mirou.io", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Onyx", "domain": "onyx.app", "industry": "AI / Enterprise Search", "funding_stage": "YC W24", "website_url": "https://onyx.app", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Trainy", "domain": "trainy.ai", "industry": "AI Infrastructure", "funding_stage": "YC W24", "website_url": "https://trainy.ai", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Definite", "domain": "definite.app", "industry": "Data / Analytics", "funding_stage": "YC W24", "website_url": "https://definite.app", "headquarters": "Remote", "hiring_status": "hiring"},
            {"name": "Sweetspot", "domain": "sweetspot.so", "industry": "GovTech / AI", "funding_stage": "YC S24", "website_url": "https://sweetspot.so", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Greptile", "domain": "greptile.com", "industry": "AI / Developer Tools", "funding_stage": "YC W24", "website_url": "https://greptile.com", "headquarters": "San Francisco, CA", "hiring_status": "hiring"},
            {"name": "Haystack", "domain": "haystackeditor.com", "industry": "Developer Tools", "funding_stage": "YC W23", "website_url": "https://haystackeditor.com", "headquarters": "Remote", "hiring_status": "hiring"},
        ]
        filtered = [
            c for c in known_yc
            if c["domain"].lower() not in excluded_domains
            and c["name"].lower() not in excluded_names
        ]
        return [normalize_company(c, "YCombinator") for c in filtered]
