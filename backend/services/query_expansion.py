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

from .logger_service import get_logger


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
        self._logger = get_logger()

    async def expand_queries(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> list[str]:
        """
        Return an ordered list of search queries for company discovery.

        The list is deduplicated, limited to 30 entries, and starts with the
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

        return result[:30]

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

        for skill in list(profile.get("tech_stack", []))[:4]:
            if skill.strip():
                queries.append(skill.strip())

        for industry in list(preferences.get("industries_of_interest", []))[:2]:
            if industry.strip():
                queries.append(industry.strip())

        seed_text = " ".join(
            queries + profile.get("skills", []) + profile.get("tech_stack", [])
        ).lower()
        semantic_defaults: list[str] = []
        if any(term in seed_text for term in ["ai", "ml", "machine learning", "python", "llm", "genai"]):
            semantic_defaults.extend([
                "MLOps engineer",
                "AI infra engineer",
                "backend systems engineer",
                "GenAI platform engineer",
                "distributed systems engineer",
                "vector database engineer",
                "founding engineer",
                "machine learning platform",
                "LLM infrastructure",
            ])
        if any(term in seed_text for term in ["backend", "python", "go", "java", "distributed"]):
            semantic_defaults.extend([
                "platform engineer",
                "backend infrastructure",
                "cloud systems engineer",
                "API platform engineer",
            ])
        if any(term in seed_text for term in ["react", "typescript", "frontend", "next"]):
            semantic_defaults.extend([
                "product engineer",
                "frontend platform engineer",
                "full-stack engineer",
            ])

        seen: set[str] = set()
        expanded: list[str] = []
        for query in queries + semantic_defaults + ["software engineer"]:
            key = query.strip().lower()
            if key and key not in seen:
                seen.add(key)
                expanded.append(query.strip())
        return expanded[:18]

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
        discovery_round: int = int(preferences.get("_discovery_round") or 1)

        round_angle = {
            1: "Focus on well-known and mainstream companies that are commonly listed on job boards.",
            2: "Focus on niche, lesser-known, or emerging companies — avoid mainstream giants.",
            3: "Focus on international, remote-first, or non-SF/NYC companies.",
            4: "Focus on deep-tech, B2B SaaS, infrastructure, and developer-tools companies.",
            5: "Focus on mission-driven, climate-tech, health-tech, and social-impact companies.",
        }.get(discovery_round, f"Focus on an entirely different set of companies than previous rounds (diversity angle {discovery_round}).")

        temperature = min(0.7 + (discovery_round - 1) * 0.05, 0.95)

        prompt = f"""Given this job seeker's profile, generate 20 diverse search queries to
discover matching companies across job boards and databases.

Target roles/queries: {base}
Tech skills: {skills}
Industries of interest: {industries or "any"}
Experience level: {experience}
Work mode preference: {work_mode}

Discovery angle for this round: {round_angle}

Generate queries that span:
1. Adjacent job titles (e.g. "founding engineer", "staff engineer", "platform engineer")
2. Startup-specific variations (e.g. "early-stage", "seed-stage", "pre-IPO")
3. Domain/technology specialisms (e.g. "ML infrastructure", "AI safety", "distributed systems")
4. Role + seniority combos (e.g. "senior backend", "lead ML engineer")
5. Industry-specific role names (e.g. "quant developer" for fintech)

Each query should be 1-5 words. Useful for searching job boards, public ATS APIs, OSS organizations, funding databases, and company directories.
Return a JSON object: {{"queries": ["query1", "query2", ...]}}"""

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }
        call_id = self._logger.log_llm_call(
            provider="openai",
            model=self._model,
            user_prompt=prompt,
            temperature=temperature,
            max_tokens=512,
            context={
                "operation": "query_expansion",
                "profile": profile,
                "preferences": preferences,
                "base_queries": base,
                "discovery_round": discovery_round,
                "excluded_names": excluded_names,
            },
            raw_payload=payload,
        )
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            raw_response = response.json()
            content = raw_response["choices"][0]["message"]["content"]
            data = json.loads(content)
            parsed = [str(q) for q in data.get("queries", []) if q]
            usage = raw_response.get("usage") or {}
            self._logger.log_llm_response(
                call_id=call_id,
                response=content,
                response_json={"queries": parsed},
                tokens_used=usage.get("total_tokens"),
                tokens_prompt=usage.get("prompt_tokens"),
                tokens_completion=usage.get("completion_tokens"),
                raw_response=raw_response,
            )
            return parsed
