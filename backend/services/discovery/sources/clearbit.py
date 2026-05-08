"""Clearbit company enrichment source."""

from __future__ import annotations

import os
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback


class ClearbitEnrichmentSource(CompanySource):
    """Enrich already discovered domains with Clearbit metadata."""

    SOURCE_NAME = "Clearbit"

    def __init__(self) -> None:
        super().__init__()
        self._api_key = os.getenv("CLEARBIT_API_KEY", "")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Clearbit enrichment is available for discovered domains")
        return []

    async def enrich_company(self, company: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key or not company.get("domain"):
            return company
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers={"Authorization": f"Bearer {self._api_key}"}) as client:
            response = await client.get("https://company.clearbit.com/v2/companies/find", params={"domain": company["domain"]})
            response.raise_for_status()
            data = response.json()
        company.setdefault("metadata", {})["clearbit"] = data
        company["size"] = company.get("size") or str(data.get("metrics", {}).get("employees", ""))
        company["industry"] = company.get("industry") or data.get("category", {}).get("industry", "")
        company["logo_url"] = company.get("logo_url") or data.get("logo", "")
        company["linkedin_url"] = company.get("linkedin_url") or data.get("linkedin", {}).get("handle", "")
        return company
