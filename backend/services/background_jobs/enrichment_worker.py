from __future__ import annotations

import asyncio
from typing import Any

try:
    from ..company_enrichment import CompanyEnrichmentService
except ImportError:
    from backend.services.company_enrichment import CompanyEnrichmentService


async def run_enrichment_worker(
    *,
    companies: list[dict[str, Any]],
    profile: dict[str, Any],
    timeout_seconds: float = 90.0,
) -> list[dict[str, Any]]:
    """Enrich discovered companies in the background with a hard timeout."""
    if not companies:
        return companies

    enricher = CompanyEnrichmentService()
    return await asyncio.wait_for(
        enricher.batch_enrich(companies, profile=profile, max_concurrent=5, top_n=min(30, len(companies))),
        timeout=timeout_seconds,
    )
