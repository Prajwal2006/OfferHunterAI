"""GitHub organization and repository based company discovery."""

from __future__ import annotations

import os
from typing import Any

import httpx

from ...company_sources.utils import infer_industry, infer_tech_stack, normalize_company, slugify_domain
from .base import CompanySource, ProgressCallback


class GitHubDiscoverySource(CompanySource):
    """Discover OSS-heavy developer tooling, infra, and AI companies."""

    SOURCE_NAME = "GitHubDiscovery"
    DEFAULT_TIMEOUT_SECONDS = 16.0

    def __init__(self) -> None:
        super().__init__()
        self._token = os.getenv("GITHUB_TOKEN", "")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Mining GitHub for OSS companies and hiring repos...")
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        search_terms = queries[:4] or preferences.get("preferred_roles", [])[:2] or ["ai infrastructure"]
        companies: dict[str, dict[str, Any]] = {}

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            for term in search_terms:
                q = f'{term} hiring OR careers stars:>300 fork:false'
                try:
                    data = await self._get_json(
                        client,
                        "https://api.github.com/search/repositories",
                        params={"q": q, "sort": "updated", "order": "desc", "per_page": 20},
                        cache_key=f"github:{q}",
                    )
                except Exception:
                    continue

                for repo in data.get("items", []) if isinstance(data, dict) else []:
                    owner = repo.get("owner") or {}
                    org = owner.get("login", "")
                    # Only treat real GitHub Organizations as companies. Personal
                    # accounts (owner type "User") are individual developers, not
                    # employers, and previously polluted results with handles like
                    # "moimikey" or "aasthas2022" that carry no open roles.
                    if not org or owner.get("type") != "Organization":
                        continue
                    text = " ".join([repo.get("name", ""), repo.get("description", ""), term])
                    company = companies.setdefault(org.lower(), {
                        "name": org.replace("-", " ").title(),
                        "domain": slugify_domain(org),
                        "description": repo.get("description", "") or f"Active open-source organization matching {term}.",
                        "industry": infer_industry(text) or "Developer Tools",
                        "tech_stack": infer_tech_stack(text),
                        "hiring_status": "unknown",
                        "remote_friendly": None,
                        "culture_tags": ["open-source", "developer-community"],
                        "source_url": owner.get("html_url", ""),
                        "github_org": org,
                        "github_repos": 0,
                        "github_stars": 0,
                    })
                    company["github_repos"] += 1
                    company["github_stars"] += int(repo.get("stargazers_count") or 0)
                    if "hiring" in text.lower() or "careers" in text.lower():
                        company["hiring_status"] = "hiring"

        results = [normalize_company(c, self.SOURCE_NAME) for c in companies.values()]
        results.sort(key=lambda c: c.get("github_stars", 0), reverse=True)
        await self._notify(progress_callback, f"GitHub discovery found {len(results[:40])} OSS-led companies")
        return results[:40]
