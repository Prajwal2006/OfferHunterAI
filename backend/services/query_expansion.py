"""
QueryExpansionService — AI-powered search query generation.

Given a parsed user profile and preferences, generates a diverse set of
search queries that increase the discovery surface area across all company
sources by inferring adjacent roles, startup-specific variations, and
domain-relevant keyword combinations.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


class QueryExpansionService:
    """
    Expand base search terms into a rich set of discovery queries.

    The service first extracts base queries from the profile/preferences,
    then (when an API key is available) uses GPT to generate adjacent and
    startup-specific variants.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def expand_queries(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> list[str]:
        """
        Return an ordered list of search queries for company discovery.

        The list is deduplicated, limited to 20 entries, and starts with the
        most directly relevant terms. Longer, more specific queries generated
        by the LLM appear later so callers can truncate without losing core terms.

        Args:
            profile:     Parsed resume profile.
            preferences: User job preferences.

        Returns:
            Ordered list of search query strings.
        """
        base = self._base_queries(profile, preferences)

        if not self._api_key:
            return base

        try:
            ai_queries = await self._ai_expand(profile, preferences, base)
        except Exception:
            ai_queries = []

        # Merge: base queries first (highest signal), then AI expansions
        seen: set[str] = set()
        result: list[str] = []
        for q in base + ai_queries:
            key = q.strip().lower()
            if key and key not in seen:
                seen.add(key)
                result.append(q.strip())

        return result[:20]

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _base_queries(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> list[str]:
        """Extract high-signal queries directly from the profile / preferences."""
        queries: list[str] = []

        roles = preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        for role in roles[:3]:
            if role.strip():
                queries.append(role.strip())

        for skill in list(profile.get("tech_stack", []))[:3]:
            if skill.strip():
                queries.append(skill.strip())

        for industry in list(preferences.get("industries_of_interest", []))[:2]:
            if industry.strip():
                queries.append(industry.strip())

        return queries or ["software engineer"]

    async def _ai_expand(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        base_queries: list[str],
    ) -> list[str]:
        """Use GPT to generate adjacent and startup-specific query variants."""
        skills = ", ".join(list(profile.get("tech_stack", []))[:8])
        base = ", ".join(base_queries[:5])
        industries = ", ".join(list(preferences.get("industries_of_interest", []))[:3])
        experience = profile.get("experience_level", "mid-level")
        work_mode = preferences.get("work_mode", "flexible")

        prompt = f"""Given this job seeker's profile, generate 15 diverse search queries to
discover matching companies across job boards and databases.

Target roles/queries: {base}
Tech skills: {skills}
Industries of interest: {industries or "any"}
Experience level: {experience}
Work mode preference: {work_mode}

Generate queries that span:
1. Adjacent job titles (e.g. "founding engineer", "staff engineer", "platform engineer")
2. Startup-specific variations (e.g. "early-stage", "seed-stage", "pre-IPO")
3. Domain/technology specialisms (e.g. "ML infrastructure", "AI safety", "distributed systems")
4. Role + seniority combos (e.g. "senior backend", "lead ML engineer")
5. Industry-specific role names (e.g. "quant developer" for fintech)

Each query should be 1–5 words. Useful for searching job boards and company directories.
Return a JSON object: {{"queries": ["query1", "query2", ...]}}"""

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = json.loads(response.json()["choices"][0]["message"]["content"])
            return [str(q) for q in data.get("queries", []) if q]
