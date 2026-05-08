"""
CompanyEnrichmentService — Enrich company profiles with hiring signals,
tech stack detection, GitHub stats, and growth velocity.

Enrichment runs asynchronously and should never block the main ranking pipeline.
The service is designed to be called in the background after initial discovery.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx

GITHUB_API_URL = "https://api.github.com"


class CompanyEnrichmentService:
    """
    Enrich company dicts with additional signals beyond what discovery provides.

    Signals added:
    - hiring_signal_count:  number of open positions detected
    - github_stars:         GitHub org total stars (proxy for dev mindshare)
    - github_repos:         public repo count
    - growth_velocity:      inferred growth signals (hiring_fast, scaling, etc.)
    - ai_adoption:          whether the company has public AI/ML infrastructure
    - remote_confidence:    more precise remote-friendliness score (0-1)
    - enriched:             True when enrichment ran successfully
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._github_token = os.getenv("GITHUB_TOKEN", "")

    # ─── Public API ───────────────────────────────────────────────────────────

    async def enrich(
        self,
        company: dict[str, Any],
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Enrich a single company dict with additional intelligence signals.

        Runs GitHub and hiring-signal sub-tasks in parallel. AI gap-fill is
        used only when key fields are still missing after those checks.

        Args:
            company: Normalized company dict.
            profile: Optional user profile for personalization hints.

        Returns:
            Mutated company dict with enrichment fields added.
        """
        if company.get("enriched"):
            return company

        tasks = [
            self._fetch_github_signals(company),
            self._detect_hiring_signals(company),
        ]
        github_data, hiring_data = await asyncio.gather(*tasks, return_exceptions=True)

        if isinstance(github_data, dict):
            company.update(github_data)

        if isinstance(hiring_data, dict):
            company.update(hiring_data)

        # Use AI to fill remaining gaps if key fields are still empty
        sparse = (
            not company.get("description") or len(company.get("description", "")) < 80
        ) and not company.get("tech_stack")

        if sparse and self._api_key:
            try:
                ai_data = await self._ai_gap_fill(company)
                for key, val in ai_data.items():
                    if not company.get(key) or company.get(key) in ("", "Other", "Unknown", "unknown", []):
                        company[key] = val
            except Exception:
                pass

        company["enriched"] = True
        company["enrichment_version"] = 1
        return company

    async def batch_enrich(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any] | None = None,
        max_concurrent: int = 5,
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Enrich a batch of companies concurrently.

        Args:
            companies:      List of company dicts.
            profile:        Optional user profile.
            max_concurrent: Maximum simultaneous enrichment tasks.
            top_n:          If set, only enrich the first N companies.

        Returns:
            Companies list with enrichment applied in-place.
        """
        targets = companies[:top_n] if top_n else companies
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _enrich_one(c: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await self.enrich(c, profile)
                except Exception:
                    return c

        enriched = list(await asyncio.gather(*[_enrich_one(c) for c in targets]))

        # Replace first N companies with enriched versions; keep rest unchanged
        result = list(enriched) + list(companies[len(targets):])
        return result

    # ─── GitHub Signals ───────────────────────────────────────────────────────

    async def _fetch_github_signals(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Look up the company's GitHub organisation for developer credibility signals.
        Returns partial dict to merge into the company.
        """
        name = company.get("name", "")
        domain = company.get("domain", "")
        if not name and not domain:
            return {}

        # Try to guess the GitHub org handle from the company name/domain
        slug = re.sub(r"[^a-zA-Z0-9-]", "", name.lower().replace(" ", "-"))
        domain_part = domain.split(".")[0] if domain else ""

        guesses = list({slug, domain_part, slug.replace("-", "")})

        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            for handle in guesses:
                if not handle:
                    continue
                try:
                    response = await client.get(f"{GITHUB_API_URL}/orgs/{handle}")
                    if response.status_code == 200:
                        data = response.json()
                        repos_resp = await client.get(
                            f"{GITHUB_API_URL}/orgs/{handle}/repos",
                            params={"per_page": 30, "sort": "stars"},
                        )
                        total_stars = 0
                        if repos_resp.status_code == 200:
                            repos = repos_resp.json()
                            total_stars = sum(r.get("stargazers_count", 0) for r in repos)

                        return {
                            "github_org": handle,
                            "github_url": data.get("html_url", ""),
                            "github_repos": data.get("public_repos", 0),
                            "github_stars": total_stars,
                            "github_followers": data.get("followers", 0),
                        }
                except Exception:
                    continue

        return {}

    # ─── Hiring Signal Detection ──────────────────────────────────────────────

    async def _detect_hiring_signals(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Detect hiring velocity and growth signals from open positions and metadata.
        """
        open_positions = company.get("open_positions", []) or []
        position_count = len(open_positions)

        # Identify engineering vs non-engineering roles
        eng_keywords = {
            "engineer", "developer", "scientist", "researcher", "architect",
            "devops", "sre", "data", "ml", "ai", "infra", "backend", "frontend",
        }
        eng_roles = [
            p for p in open_positions
            if any(kw in (p.get("title") or "").lower() for kw in eng_keywords)
        ]

        growth_signals: list[str] = []
        if position_count > 10:
            growth_signals.append("rapid_hiring")
        elif position_count > 5:
            growth_signals.append("actively_expanding")
        elif position_count > 0:
            growth_signals.append("selective_hiring")

        if len(eng_roles) > 3:
            growth_signals.append("engineering_heavy_hiring")

        description = (company.get("description", "") or "").lower()
        if any(kw in description for kw in ["series b", "series c", "recently raised", "just raised"]):
            growth_signals.append("recently_funded")
        if any(kw in description for kw in ["fast-growing", "hypergrowth", "scaling fast"]):
            growth_signals.append("hypergrowth")

        result: dict[str, Any] = {
            "hiring_signal_count": position_count,
            "engineering_role_count": len(eng_roles),
            "growth_signals": growth_signals,
        }

        # Infer remote confidence score
        remote_signals = 0
        if company.get("remote_friendly"):
            remote_signals += 2
        if "remote" in description:
            remote_signals += 1
        if any("remote" in (p.get("work_mode") or "") for p in open_positions):
            remote_signals += 1
        result["remote_confidence"] = min(1.0, remote_signals / 4.0)

        # Infer AI adoption
        tech = [t.lower() for t in (company.get("tech_stack") or [])]
        ai_tech = {"pytorch", "tensorflow", "jax", "transformers", "langchain", "openai", "llm"}
        result["ai_adoption"] = bool(ai_tech & set(tech))

        return result

    # ─── AI Gap Fill ──────────────────────────────────────────────────────────

    async def _ai_gap_fill(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Use GPT to fill in sparse company profile fields.
        Only called when scraping produced insufficient data.
        """
        name = company.get("name", company.get("domain", "Unknown"))
        domain = company.get("domain", "")
        existing_desc = company.get("description", "")

        prompt = (
            f"Provide a concise company intelligence profile for:\n"
            f"Company: {name}\n"
            f"Domain: {domain}\n"
            f"Known info: {existing_desc[:200] or 'None'}\n\n"
            f"Return JSON with these fields (only fill what you can confidently infer):\n"
            f'{{"description": "...", "mission": "...", "industry": "...", '
            f'"size": "e.g. 1-50", "tech_stack": [...], "funding_stage": "...", '
            f'"headquarters": "city, country", "culture_tags": [...], '
            f'"remote_friendly": true/false, "hiring_status": "unknown"}}'
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
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
                            "content": "You are a company research expert. Return only valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 600,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])
