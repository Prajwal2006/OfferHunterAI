"""
EmbeddingService — Semantic embedding generation and similarity utilities.

Uses OpenAI text-embedding-3-small for cost-effective, high-quality
semantic representations of user profiles and companies.

Embeddings are cached in-process (LRU-style hash map) to avoid redundant
API calls during a single pipeline run.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
from typing import Any

import httpx

# ─── Module-level embedding cache ─────────────────────────────────────────────
# Shared across all service instances within one process lifetime.
_embedding_cache: dict[str, list[float]] = {}
_CACHE_MAX = 2048  # evict oldest entries beyond this limit


class EmbeddingService:
    """
    Generate and compare semantic embeddings via the OpenAI Embeddings API.

    Attributes:
        MODEL:      OpenAI model identifier.
        DIMENSIONS: Embedding vector length for text-embedding-3-small.
    """

    MODEL = "text-embedding-3-small"
    DIMENSIONS = 1536

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")

    # ─── Core Embedding Methods ───────────────────────────────────────────────

    async def create_embedding(self, text: str) -> list[float]:
        """
        Generate a semantic embedding for the given text.

        Returns a zero vector of DIMENSIONS length when the API is unavailable
        or the API key is not configured, so callers receive a graceful degradation
        rather than an exception.
        """
        if not self._api_key or not text.strip():
            return [0.0] * self.DIMENSIONS

        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "input": text[:8000],
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                embedding: list[float] = response.json()["data"][0]["embedding"]
        except Exception:
            return [0.0] * self.DIMENSIONS

        # Store in cache with simple eviction
        if len(_embedding_cache) >= _CACHE_MAX:
            oldest = next(iter(_embedding_cache))
            del _embedding_cache[oldest]
        _embedding_cache[cache_key] = embedding
        return embedding

    async def create_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts concurrently.

        Uses asyncio.gather for parallel requests, up to 10 at a time to
        respect rate limits.
        """
        semaphore = asyncio.Semaphore(10)

        async def _embed(text: str) -> list[float]:
            async with semaphore:
                return await self.create_embedding(text)

        return list(await asyncio.gather(*[_embed(t) for t in texts]))

    # ─── Similarity Helpers ───────────────────────────────────────────────────

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """
        Compute cosine similarity between two embedding vectors.

        Returns a value in [0.0, 1.0]. Returns 0.0 for mismatched or zero vectors.
        """
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (mag_a * mag_b)))

    # ─── Profile & Company Embeddings ─────────────────────────────────────────

    async def create_profile_embedding(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> list[float]:
        """
        Build a single combined embedding from a user's profile + preferences.

        Concatenates the most semantically rich fields to maximise signal.
        """
        parts: list[str] = []

        if profile.get("summary"):
            parts.append(profile["summary"])

        skills = list(profile.get("skills", [])) + list(profile.get("tech_stack", []))
        if skills:
            parts.append("Skills: " + ", ".join(skills[:20]))

        domains = profile.get("preferred_domains", [])
        if domains:
            parts.append("Domains: " + ", ".join(domains[:5]))

        roles = preferences.get("preferred_roles", [])
        if roles:
            parts.append("Seeking: " + ", ".join(roles[:5]))

        industries = preferences.get("industries_of_interest", [])
        if industries:
            parts.append("Industries: " + ", ".join(industries[:5]))

        work_mode = preferences.get("work_mode", "")
        if work_mode:
            parts.append(f"Work mode: {work_mode}")

        return await self.create_embedding(" | ".join(parts))

    async def create_company_embedding(self, company: dict[str, Any]) -> list[float]:
        """Build a semantic embedding from the most informative company fields."""
        parts: list[str] = []

        if company.get("name"):
            parts.append(company["name"])
        if company.get("description"):
            parts.append(company["description"])
        if company.get("mission"):
            parts.append(company["mission"])
        if company.get("industry"):
            parts.append(company["industry"])

        tech = company.get("tech_stack", [])
        if tech:
            parts.append("Tech: " + ", ".join(tech[:10]))

        tags = company.get("culture_tags", [])
        if tags:
            parts.append("Culture: " + ", ".join(tags[:5]))

        roles = [p.get("title", "") for p in (company.get("open_positions") or [])[:3] if p.get("title")]
        if roles:
            parts.append("Hiring for: " + ", ".join(roles))

        return await self.create_embedding(" | ".join(parts))

    # ─── Semantic Ranking ─────────────────────────────────────────────────────

    async def semantic_rank(
        self,
        query_embedding: list[float],
        companies: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], float]]:
        """
        Rank a list of companies by cosine similarity to the query embedding.

        Returns:
            List of (company, similarity_score) tuples sorted descending.
            similarity_score is in [0.0, 1.0].
        """
        if not any(query_embedding):
            # No embedding available — return companies with neutral score
            return [(c, 0.5) for c in companies]

        # Build company embeddings concurrently
        company_embeddings = await self.create_batch_embeddings([
            self._company_text(c) for c in companies
        ])

        results: list[tuple[dict[str, Any], float]] = []
        for company, embedding in zip(companies, company_embeddings):
            sim = self.cosine_similarity(query_embedding, embedding)
            results.append((company, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @staticmethod
    def _company_text(company: dict[str, Any]) -> str:
        """Concatenate key company fields into a single text for embedding."""
        parts = [
            company.get("name", ""),
            company.get("description", ""),
            company.get("mission", ""),
            company.get("industry", ""),
            "Tech: " + ", ".join(company.get("tech_stack", [])[:8]),
        ]
        return " | ".join(p for p in parts if p)
