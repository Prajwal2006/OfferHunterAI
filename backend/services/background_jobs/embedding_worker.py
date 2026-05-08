from __future__ import annotations

import asyncio
from typing import Any

try:
    from ..embedding_service import EmbeddingService
except ImportError:
    from backend.services.embedding_service import EmbeddingService


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
