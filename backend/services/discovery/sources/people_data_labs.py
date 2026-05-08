"""People Data Labs growth signal adapter."""

from __future__ import annotations

import os
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback


class PeopleDataLabsSource(CompanySource):
    """Enrich companies with employee and engineering growth signals."""

    SOURCE_NAME = "PeopleDataLabs"

    def __init__(self) -> None:
        super().__init__()
        self._api_key = os.getenv("PDL_API_KEY", "")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        if not self._api_key:
            await self._notify(progress_callback, "People Data Labs skipped: PDL_API_KEY is not configured")
        return []

    async def enrich_company(self, company: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key or not company.get("domain"):
            return company
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers={"X-Api-Key": self._api_key}) as client:
            response = await client.get("https://api.peopledatalabs.com/v5/company/enrich", params={"website": company["domain"]})
            response.raise_for_status()
            data = response.json().get("data") or {}
        company.setdefault("metadata", {})["people_data_labs"] = data
        company["size"] = company.get("size") or str(data.get("employee_count", ""))
        return company
