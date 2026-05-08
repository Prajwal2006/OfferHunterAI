"""Crunchbase discovery and enrichment adapter."""

from __future__ import annotations

import os
from typing import Any

import httpx

from ...company_sources.utils import extract_domain_from_url, normalize_company
from .base import CompanySource, ProgressCallback


class CrunchbaseSource(CompanySource):
    """Discover recently funded companies when Crunchbase credentials are configured."""

    SOURCE_NAME = "Crunchbase"
    DEFAULT_TIMEOUT_SECONDS = 20.0

    def __init__(self) -> None:
        super().__init__()
        self._api_key = os.getenv("CRUNCHBASE_API_KEY", "")
        self._base_url = os.getenv("CRUNCHBASE_API_BASE", "https://api.crunchbase.com/api/v4")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        if not self._api_key:
            await self._notify(progress_callback, "Crunchbase skipped: CRUNCHBASE_API_KEY is not configured")
            return []

        await self._notify(progress_callback, "Searching Crunchbase for funding and growth signals...")
        headers = {"X-cb-user-key": self._api_key, "Content-Type": "application/json"}
        companies: list[dict[str, Any]] = []
        terms = queries[:4] or preferences.get("industries_of_interest", [])[:3] or ["artificial intelligence"]

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            for term in terms:
                try:
                    response = await client.post(
                        f"{self._base_url}/searches/organizations",
                        json={
                            "query": [{"type": "predicate", "field_id": "short_description", "operator_id": "contains", "values": [term]}],
                            "field_ids": ["identifier", "short_description", "website_url", "categories", "num_employees_enum", "last_funding_type"],
                            "limit": 25,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                except Exception:
                    continue

                for entity in data.get("entities", []):
                    props = entity.get("properties") or {}
                    identifier = props.get("identifier") or {}
                    name = identifier.get("value") or identifier.get("permalink") or ""
                    website = props.get("website_url") or ""
                    if not name:
                        continue
                    companies.append(normalize_company({
                        "name": name,
                        "domain": extract_domain_from_url(website),
                        "description": props.get("short_description", ""),
                        "industry": ", ".join(c.get("value", "") for c in props.get("categories", [])[:2] if isinstance(c, dict)),
                        "size": props.get("num_employees_enum", ""),
                        "funding_stage": props.get("last_funding_type", ""),
                        "website_url": website,
                        "hiring_status": "unknown",
                        "source_url": identifier.get("entity_def_id", ""),
                    }, self.SOURCE_NAME))

        await self._notify(progress_callback, f"Crunchbase found {len(companies[:50])} companies")
        return companies[:50]
