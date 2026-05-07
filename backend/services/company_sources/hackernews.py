"""
HackerNews "Who's Hiring" company discovery source.

Queries the Algolia HN API for the latest hiring thread and extracts companies
that match the user's skills and role targets.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import DEFAULT_HEADERS, normalize_company, slugify_domain

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsSource(CompanySource):
    """Discover companies from Hacker News 'Who Is Hiring' monthly threads."""

    SOURCE_NAME = "HackerNews"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """Search HN hiring threads for matching companies."""
        await self._notify(progress_callback, "Searching Hacker News 'Who Is Hiring'...")

        # Build query from provided expanded queries + fallback
        skills = profile.get("tech_stack", [])[:4]
        roles = preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        query_terms = list(queries[:2]) + list(roles[:1]) + list(skills[:2])
        if not query_terms:
            query_terms = ["software engineer"]
        query = " ".join(query_terms[:5])

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=DEFAULT_HEADERS) as client:
                # Step 1: Find the latest "Ask HN: Who is hiring?" story
                hiring_resp = await client.get(
                    HN_ALGOLIA_URL,
                    params={
                        "query": "Ask HN: Who is hiring?",
                        "tags": "ask_hn",
                        "numericFilters": "created_at_i>1700000000",
                        "hitsPerPage": 3,
                    },
                )
                story_id: str | None = None
                if hiring_resp.status_code == 200:
                    stories = hiring_resp.json().get("hits", [])
                    if stories:
                        story_id = stories[0].get("objectID")

                # Step 2: Search comments on that thread
                params: dict[str, Any] = {
                    "query": query,
                    "numericFilters": "created_at_i>1700000000",
                        "hitsPerPage": 100,
                }
                if story_id:
                    params["tags"] = f"comment,story_{story_id}"
                else:
                    params["tags"] = "comment"
                    params["query"] = f"hiring {query}"

                response = await client.get(HN_ALGOLIA_URL, params=params)
                if response.status_code != 200:
                    return []
                hits = response.json().get("hits", [])
        except Exception:
            return []

        companies: list[dict[str, Any]] = []
        for hit in hits:
            title = hit.get("story_title", "") or ""
            text = hit.get("comment_text", "") or hit.get("story_text", "") or ""
            if not text:
                continue
            extracted = self._extract_companies_from_post(title, text)
            companies.extend(extracted)

        results = [normalize_company(c, self.SOURCE_NAME) for c in companies[:30]]
        await self._notify(progress_callback, f"Found {len(results)} companies on Hacker News")
        return results

    @staticmethod
    def _extract_companies_from_post(title: str, text: str) -> list[dict[str, Any]]:
        """Extract structured company info from an HN hiring post."""
        companies: list[dict[str, Any]] = []

        # Standard HN hiring format: "CompanyName | Role | Location | Remote"
        pipe_pattern = re.compile(r"^([A-Z][A-Za-z0-9 .,&!'-]{2,40})\s*\|", re.MULTILINE)
        matches = pipe_pattern.findall(text[:3000])

        for name in matches[:5]:
            name = name.strip()
            if len(name) > 3 and not name.lower().startswith(("we ", "our ", "the ")):
                url_match = re.search(
                    r"(?:https?://)?(?:www\.)?[\w-]+\.(?:com|io|ai|co|org)",
                    text,
                    re.IGNORECASE,
                )
                companies.append({
                    "name": name,
                    "domain": slugify_domain(name),
                    "source_url": url_match.group(0) if url_match else "",
                    "hiring_status": "actively_hiring",
                    "description": f"Hiring via Hacker News: {title[:100]}",
                    "discovery_queries": [],
                })

        return companies
