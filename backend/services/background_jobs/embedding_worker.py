from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is in Python path for both local and Vercel deployments
_backend_root = str(Path(__file__).resolve().parent.parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from services.embedding_service import EmbeddingService


async def run_embedding_worker(
    *,
    companies: list[dict[str, Any]],
    per_company_timeout_seconds: float = 20.0,
) -> dict[str, list[float]]:
    """Create company embeddings in the background with per-company hard timeouts."""
    if not companies:
        return {}

    service = EmbeddingService()
    embeddings: dict[str, list[float]] = {}

    async def embed_one(company: dict[str, Any]) -> tuple[str, list[float]]:
        key = (company.get("domain") or company.get("id") or company.get("name") or "").lower().strip()
        if not key:
            return "", []
        try:
            embedding = await asyncio.wait_for(
                service.create_company_embedding(company),
                timeout=per_company_timeout_seconds,
            )
            return key, embedding
        except Exception:
            return key, []

    results = await asyncio.gather(*[embed_one(c) for c in companies], return_exceptions=False)
    for key, embedding in results:
        if key and embedding:
            embeddings[key] = embedding

    return embeddings
