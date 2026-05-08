"""Recursive opportunity graph expansion primitives."""

from __future__ import annotations

from typing import Any


class RecursiveExpansionService:
    """Generate second-order discovery seeds from companies already found."""

    _COMPETITOR_HINTS = {
        "Vector Database": ["vector database", "retrieval infrastructure", "RAG platform"],
        "AI Infrastructure": ["model serving", "GPU cloud", "MLOps platform"],
        "Developer Tools": ["developer productivity", "cloud dev environment", "observability startup"],
        "Fintech": ["payments infrastructure", "expense management", "banking API"],
        "Cybersecurity": ["identity security", "cloud security", "compliance automation"],
    }

    def expand(
        self,
        companies: list[dict[str, Any]],
        *,
        max_queries: int = 12,
    ) -> dict[str, Any]:
        """Return adjacent queries and graph edges for recursive discovery."""
        queries: list[str] = []
        edges: list[dict[str, str]] = []
        seen_queries: set[str] = set()

        for company in companies[:40]:
            name = company.get("name") or company.get("domain") or ""
            industry = company.get("industry") or ""
            tech_stack = company.get("tech_stack") or []

            for hint in self._COMPETITOR_HINTS.get(industry, []):
                if hint not in seen_queries:
                    seen_queries.add(hint)
                    queries.append(hint)
                edges.append({"from": name, "to_query": hint, "relationship": "same_domain"})

            for tech in tech_stack[:3]:
                query = f"{tech} startup"
                if query.lower() not in seen_queries:
                    seen_queries.add(query.lower())
                    queries.append(query)
                edges.append({"from": name, "to_query": query, "relationship": "same_stack"})

            stage = str(company.get("funding_stage") or "").lower()
            if any(token in stage for token in ["seed", "series a", "yc"]):
                query = f"{industry or 'startup'} seed stage"
                if query.lower() not in seen_queries:
                    seen_queries.add(query.lower())
                    queries.append(query)
                edges.append({"from": name, "to_query": query, "relationship": "similar_stage"})

        return {"queries": queries[:max_queries], "edges": edges[:100]}
