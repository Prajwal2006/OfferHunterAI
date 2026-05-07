"""
AI-powered company discovery source.

Queries an LLM to suggest real companies that match the candidate's profile,
preferences, and expanded search queries. Falls back to a curated static list
when no API key is configured.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import normalize_company


class AIDiscoverySource(CompanySource):
    """Discover companies via LLM-guided research."""

    SOURCE_NAME = "AI Discovery"

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """Ask GPT to suggest companies matching the candidate profile."""
        await self._notify(progress_callback, "Running AI-powered company discovery...")

        if not self._api_key:
            return self._fallback(profile, preferences)

        skills_str = ", ".join(profile.get("tech_stack", [])[:10])
        roles_str = ", ".join(
            preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        )
        industries_str = ", ".join(preferences.get("industries_of_interest", []))
        work_mode = preferences.get("work_mode", "flexible")
        startup_pref = preferences.get("open_to_startups", True)
        sponsorship = preferences.get("sponsorship_required", False)
        expanded_queries_str = ", ".join(queries[:8]) if queries else ""

        prompt = f"""You are a job market expert. Suggest {min(count, 25)} specific real companies
actively hiring that match this candidate profile:

Skills: {skills_str}
Target Roles: {roles_str}
Industries of Interest: {industries_str or "Open to any"}
Work mode preference: {work_mode}
Open to startups: {startup_pref}
Needs visa sponsorship: {sponsorship}
Search context: {expanded_queries_str or "general search"}

Return ONLY a JSON object with a "companies" array. Each company object must have:
{{
  "name": "exact company name",
  "domain": "company domain (e.g. stripe.com)",
  "description": "1-2 sentence company description",
  "industry": "primary industry",
  "size": "employee count range (e.g. 500-1000)",
  "headquarters": "city, state/country",
  "tech_stack": ["list of technologies they use"],
  "funding_stage": "Seed/Series A/B/C/Public/etc",
  "remote_friendly": true/false,
  "sponsorship_available": true/false/null,
  "hiring_status": "actively_hiring",
  "website_url": "https://...",
  "culture_tags": ["list of culture descriptors"],
  "why_match": "brief explanation of why this company matches"
}}

Only include real companies. Include a mix of startups, growth-stage, and established companies.
Prioritize companies with strong engineering cultures and active hiring."""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a job market expert. Return only valid JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4096,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                data = json.loads(content)

                if isinstance(data, list):
                    raw_companies = data
                elif isinstance(data, dict):
                    raw_companies = data.get(
                        "companies",
                        data.get("results", list(data.values())[0] if data else []),
                    )
                else:
                    return self._fallback(profile, preferences)

                results = [
                    normalize_company(c, self.SOURCE_NAME)
                    for c in raw_companies
                    if isinstance(c, dict) and c.get("name")
                ]
                await self._notify(
                    progress_callback, f"AI discovery found {len(results)} companies"
                )
                return results

        except Exception:
            return self._fallback(profile, preferences)

    @staticmethod
    def _fallback(
        profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Static fallback companies when AI is unavailable."""
        fallback = [
            {"name": "OpenAI", "domain": "openai.com", "industry": "AI/ML", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://openai.com", "tech_stack": ["Python", "PyTorch", "Kubernetes", "React"]},
            {"name": "Anthropic", "domain": "anthropic.com", "industry": "AI/ML", "size": "300-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://anthropic.com", "tech_stack": ["Python", "PyTorch", "React", "TypeScript"]},
            {"name": "Google DeepMind", "domain": "deepmind.com", "industry": "AI/ML Research", "size": "1000-5000", "headquarters": "London, UK", "remote_friendly": False, "hiring_status": "hiring", "website_url": "https://deepmind.com", "tech_stack": ["Python", "TensorFlow", "JAX"]},
            {"name": "Cohere", "domain": "cohere.com", "industry": "AI/ML", "size": "200-500", "headquarters": "Toronto, Canada", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cohere.com", "tech_stack": ["Python", "PyTorch", "Go"]},
            {"name": "Mistral AI", "domain": "mistral.ai", "industry": "AI/ML", "size": "50-200", "headquarters": "Paris, France", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://mistral.ai", "tech_stack": ["Python", "PyTorch", "Rust"]},
            {"name": "Databricks", "domain": "databricks.com", "industry": "Data / AI Platform", "size": "5000+", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://databricks.com", "tech_stack": ["Python", "Scala", "Spark"]},
            {"name": "Hugging Face", "domain": "huggingface.co", "industry": "AI/ML", "size": "200-500", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://huggingface.co", "tech_stack": ["Python", "PyTorch", "JavaScript"]},
            {"name": "Figma", "domain": "figma.com", "industry": "Design Tools", "size": "1000-2000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://figma.com", "tech_stack": ["C++", "TypeScript", "React", "WebAssembly"]},
            {"name": "Notion", "domain": "notion.so", "industry": "Productivity", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://notion.so", "tech_stack": ["TypeScript", "React", "Go"]},
            {"name": "Cloudflare", "domain": "cloudflare.com", "industry": "Cloud / Networking", "size": "3000-5000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cloudflare.com", "tech_stack": ["Go", "Rust", "JavaScript"]},
        ]
        return [normalize_company(c, "AI Discovery") for c in fallback]
