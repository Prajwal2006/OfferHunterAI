from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is in Python path for both local and Vercel deployments
_backend_root = str(Path(__file__).resolve().parent.parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from services.company_enrichment import CompanyEnrichmentService


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
    effective_timeout = max(timeout_seconds, min(360.0, 30.0 + (len(companies) * 3.0)))
    return await asyncio.wait_for(
        enricher.batch_enrich(companies, profile=profile, max_concurrent=5, top_n=len(companies)),
        timeout=effective_timeout,
    )
