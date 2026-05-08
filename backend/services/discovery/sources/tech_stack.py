"""BuiltWith/Wappalyzer style tech-stack enrichment."""

from __future__ import annotations

from typing import Any

from .base import CompanySource, ProgressCallback


class TechStackEnrichmentSource(CompanySource):
    """Infer tech-stack signals from known metadata and open roles."""

    SOURCE_NAME = "TechStackEnrichment"

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        await self._notify(progress_callback, "Tech-stack enrichment runs after company discovery")
        return []

    @staticmethod
    def infer_usage(company: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(
            [
                company.get("description", ""),
                " ".join(company.get("tech_stack", []) or []),
                " ".join(p.get("title", "") + " " + p.get("description", "") for p in company.get("open_positions", []) or []),
            ]
        ).lower()
        technologies = {
            "React": ["react"],
            "Next.js": ["next.js", "nextjs"],
            "AWS": ["aws", "amazon web services"],
            "OpenAI": ["openai", "gpt", "llm"],
            "LangChain": ["langchain"],
            "Stripe": ["stripe"],
            "Vercel": ["vercel"],
        }
        found = [name for name, terms in technologies.items() if any(term in text for term in terms)]
        return {"inferred_tech_stack": found, "ai_stack_signal": any(t in found for t in ["OpenAI", "LangChain"])}
