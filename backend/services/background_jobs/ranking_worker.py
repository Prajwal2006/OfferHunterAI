from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is in Python path for both local and Vercel deployments
_backend_root = str(Path(__file__).resolve().parent.parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from services.company_ranker import CompanyRankerService
from services.company_scoring import CompanyScoringService


async def run_ranking_worker(
    *,
    companies: list[dict[str, Any]],
    profile: dict[str, Any],
    preferences: dict[str, Any],
    timeout_seconds: float = 120.0,
) -> list[dict[str, Any]]:
    """Compute ranking and extended scoring in the background with timeout protection."""
    if not companies:
        return companies

    ranker = CompanyRankerService()
    scorer = CompanyScoringService()

    ranked = await asyncio.wait_for(
        ranker.rank(companies=companies, profile=profile, preferences=preferences),
        timeout=timeout_seconds,
    )

    base_rankings = {
        (c.get("domain") or "").lower(): c.get("ranking", {})
        for c in ranked
    }
    semantic_scores = {
        (c.get("domain") or "").lower(): c.get("ranking", {}).get("semantic_similarity", 0.5)
        for c in ranked
    }

    return scorer.score_companies(
        companies=ranked,
        profile=profile,
        preferences=preferences,
        semantic_scores=semantic_scores,
        base_rankings=base_rankings,
    )
