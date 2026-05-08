"""
AI-powered company discovery source.

Queries an LLM to suggest real companies that match the candidate's profile,
preferences, and expanded search queries. Falls back to a curated static list
when no API key is configured.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import CompanySource, ProgressCallback
from .utils import normalize_company


class AIDiscoverySource(CompanySource):
    """Discover companies via LLM-guided research."""

    SOURCE_NAME = "AI Discovery"

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """Ask GPT to suggest companies matching the candidate profile."""
        # Read internal discovery-round keys injected by CompanyDiscoveryService.
        # These vary prompts and exclusion lists across multiple discovery runs.
        excluded_domains: set[str] = set(preferences.get("_excluded_domains") or [])
        excluded_names: set[str] = set(preferences.get("_excluded_names") or [])
        discovery_round: int = int(preferences.get("_discovery_round") or 1)

        await self._notify(
            progress_callback,
            f"Running AI-powered company discovery (round {discovery_round})..."
        )

        if not self._api_key:
            return self._fallback(profile, preferences, excluded_domains, excluded_names)

        skills_str = ", ".join(profile.get("tech_stack", [])[:10])
        roles_str = ", ".join(
            preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        )
        industries_str = ", ".join(preferences.get("industries_of_interest", []))
        work_mode = preferences.get("work_mode", "flexible")
        startup_pref = preferences.get("open_to_startups", True)
        sponsorship = preferences.get("sponsorship_required", False)
        expanded_queries_str = ", ".join(queries[:8]) if queries else ""

        # Build exclusion clause so GPT avoids already-discovered companies
        exclusion_clause = ""
        if excluded_names:
            sample = sorted(excluded_names)[:40]
            exclusion_clause = (
                f"\n\nIMPORTANT: The following companies have ALREADY been suggested. "
                f"Do NOT include them:\n{', '.join(sample)}\n"
                f"Suggest entirely different companies the user has not yet seen."
            )

        # Vary the discovery framing per round so GPT explores different spaces
        round_framing = {
            1: "Include a mix of startups, growth-stage, and established companies.",
            2: "Focus on lesser-known, niche, or emerging companies not in mainstream lists.",
            3: "Focus on international companies, remote-first companies, and non-SF/NYC hubs.",
            4: "Focus on deep-tech, B2B SaaS, and infrastructure companies.",
            5: "Focus on mission-driven, climate-tech, health-tech, and impact companies.",
        }.get(discovery_round, f"Focus on a completely different set of companies than before (diversity round {discovery_round}).")

        # Slightly higher temperature on later rounds to increase variety
        temperature = min(0.7 + (discovery_round - 1) * 0.05, 0.95)

        prompt = f"""You are a job market expert. Suggest {min(count, 30)} specific real companies
actively hiring that match this candidate profile:

Skills: {skills_str}
Target Roles: {roles_str}
Industries of Interest: {industries_str or "Open to any"}
Work mode preference: {work_mode}
Open to startups: {startup_pref}
Needs visa sponsorship: {sponsorship}
Search context: {expanded_queries_str or "general search"}
{exclusion_clause}

{round_framing}

Return ONLY a JSON object with a "companies" array. Each company object must have:
{{
  "name": "exact company name",
  "domain": "company domain (e.g. stripe.com)",
  "description": "1-2 sentence company description",
  "industry": "primary industry",
  "size": "employee count range (e.g. 500-1000)",
  "headquarters": "city, state/country",
  "tech_stack": ["list of technologies they use"],
  "funding_stage": "Seed/Series A/B/C/Public/etc",
  "remote_friendly": true/false,
  "sponsorship_available": true/false/null,
  "hiring_status": "actively_hiring",
  "website_url": "https://...",
  "culture_tags": ["list of culture descriptors"],
  "why_match": "brief explanation of why this company matches"
}}

Only include real companies. Prioritize companies with strong engineering cultures and active hiring."""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a job market expert. Return only valid JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": 4096,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                data = json.loads(content)

                if isinstance(data, list):
                    raw_companies = data
                elif isinstance(data, dict):
                    raw_companies = data.get(
                        "companies",
                        data.get("results", list(data.values())[0] if data else []),
                    )
                else:
                    return self._fallback(profile, preferences, excluded_domains, excluded_names)

                results = [
                    normalize_company(c, self.SOURCE_NAME)
                    for c in raw_companies
                    if isinstance(c, dict) and c.get("name")
                    # Client-side safety net: skip any GPT hallucinates that match excluded domains
                    and (c.get("domain") or "").lower() not in excluded_domains
                ]
                await self._notify(
                    progress_callback, f"AI discovery found {len(results)} companies"
                )
                return results

        except Exception:
            return self._fallback(profile, preferences, excluded_domains, excluded_names)

    @staticmethod
    def _fallback(
        profile: dict[str, Any],
        preferences: dict[str, Any],
        excluded_domains: set[str] | list[str] | None = None,
        excluded_names: set[str] | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Static fallback companies when AI is unavailable."""
        excluded = {str(d).lower().strip().removeprefix("www.") for d in (excluded_domains or [])}
        excluded_company_names = {str(n).lower().strip() for n in (excluded_names or [])}
        fallback = [
            {"name": "OpenAI", "domain": "openai.com", "industry": "AI/ML", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://openai.com", "tech_stack": ["Python", "PyTorch", "Kubernetes", "React"]},
            {"name": "Anthropic", "domain": "anthropic.com", "industry": "AI/ML", "size": "300-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://anthropic.com", "tech_stack": ["Python", "PyTorch", "React", "TypeScript"]},
            {"name": "Google DeepMind", "domain": "deepmind.com", "industry": "AI/ML Research", "size": "1000-5000", "headquarters": "London, UK", "remote_friendly": False, "hiring_status": "hiring", "website_url": "https://deepmind.com", "tech_stack": ["Python", "TensorFlow", "JAX"]},
            {"name": "Cohere", "domain": "cohere.com", "industry": "AI/ML", "size": "200-500", "headquarters": "Toronto, Canada", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cohere.com", "tech_stack": ["Python", "PyTorch", "Go"]},
            {"name": "Mistral AI", "domain": "mistral.ai", "industry": "AI/ML", "size": "50-200", "headquarters": "Paris, France", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://mistral.ai", "tech_stack": ["Python", "PyTorch", "Rust"]},
            {"name": "Databricks", "domain": "databricks.com", "industry": "Data / AI Platform", "size": "5000+", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://databricks.com", "tech_stack": ["Python", "Scala", "Spark"]},
            {"name": "Hugging Face", "domain": "huggingface.co", "industry": "AI/ML", "size": "200-500", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://huggingface.co", "tech_stack": ["Python", "PyTorch", "JavaScript"]},
            {"name": "Figma", "domain": "figma.com", "industry": "Design Tools", "size": "1000-2000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://figma.com", "tech_stack": ["C++", "TypeScript", "React", "WebAssembly"]},
            {"name": "Notion", "domain": "notion.so", "industry": "Productivity", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://notion.so", "tech_stack": ["TypeScript", "React", "Go"]},
            {"name": "Cloudflare", "domain": "cloudflare.com", "industry": "Cloud / Networking", "size": "3000-5000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cloudflare.com", "tech_stack": ["Go", "Rust", "JavaScript"]},
            {"name": "Vercel", "domain": "vercel.com", "industry": "Developer Tools", "size": "200-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://vercel.com", "tech_stack": ["TypeScript", "Next.js", "Rust", "Go"]},
            {"name": "Linear", "domain": "linear.app", "industry": "Productivity / Dev Tools", "size": "50-200", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://linear.app", "tech_stack": ["TypeScript", "React", "Go", "GraphQL"]},
            {"name": "Fly.io", "domain": "fly.io", "industry": "Cloud Infrastructure", "size": "50-200", "headquarters": "Chicago, IL", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://fly.io", "tech_stack": ["Go", "Rust", "Elixir"]},
            {"name": "Modal Labs", "domain": "modal.com", "industry": "AI Infrastructure", "size": "50-100", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://modal.com", "tech_stack": ["Python", "Rust", "Kubernetes"]},
            {"name": "Perplexity AI", "domain": "perplexity.ai", "industry": "AI/ML", "size": "100-300", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://perplexity.ai", "tech_stack": ["Python", "TypeScript", "React"]},
            {"name": "Weights & Biases", "domain": "wandb.ai", "industry": "MLOps", "size": "200-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://wandb.ai", "tech_stack": ["Python", "Go", "TypeScript"]},
            {"name": "Replit", "domain": "replit.com", "industry": "Developer Tools", "size": "100-300", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://replit.com", "tech_stack": ["TypeScript", "Rust", "Python", "GCP"]},
            {"name": "Codeium", "domain": "codeium.com", "industry": "AI / Developer Tools", "size": "100-200", "headquarters": "Mountain View, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://codeium.com", "tech_stack": ["Python", "TypeScript", "Rust"]},
            {"name": "Together AI", "domain": "together.ai", "industry": "AI Infrastructure", "size": "50-150", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://together.ai", "tech_stack": ["Python", "CUDA", "Rust"]},
            {"name": "Replicate", "domain": "replicate.com", "industry": "AI Infrastructure", "size": "50-100", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://replicate.com", "tech_stack": ["Go", "Python", "TypeScript"]},
            {"name": "LangChain", "domain": "langchain.com", "industry": "AI / Developer Tools", "size": "100-200", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://langchain.com", "tech_stack": ["Python", "TypeScript", "React"]},
            {"name": "LlamaIndex", "domain": "llamaindex.ai", "industry": "AI / Developer Tools", "size": "50-100", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://llamaindex.ai", "tech_stack": ["Python", "TypeScript"]},
            {"name": "Pinecone", "domain": "pinecone.io", "industry": "Vector Database", "size": "200-500", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://pinecone.io", "tech_stack": ["Go", "Python", "Kubernetes"]},
            {"name": "Weaviate", "domain": "weaviate.io", "industry": "Vector Database", "size": "100-300", "headquarters": "Amsterdam, Netherlands", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://weaviate.io", "tech_stack": ["Go", "Python", "Kubernetes"]},
            {"name": "Qdrant", "domain": "qdrant.tech", "industry": "Vector Database", "size": "50-100", "headquarters": "Berlin, Germany", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://qdrant.tech", "tech_stack": ["Rust", "Python"]},
            {"name": "Anyscale", "domain": "anyscale.com", "industry": "AI Infrastructure", "size": "200-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://anyscale.com", "tech_stack": ["Python", "Ray", "Kubernetes"]},
            {"name": "RunPod", "domain": "runpod.io", "industry": "AI Infrastructure", "size": "50-200", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://runpod.io", "tech_stack": ["Python", "Kubernetes", "React"]},
            {"name": "Baseten", "domain": "baseten.co", "industry": "MLOps", "size": "50-150", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://baseten.co", "tech_stack": ["Python", "Kubernetes", "TypeScript"]},
            {"name": "Tailscale", "domain": "tailscale.com", "industry": "Networking / Security", "size": "200-500", "headquarters": "Toronto, Canada", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://tailscale.com", "tech_stack": ["Go", "React", "WireGuard"]},
            {"name": "Sentry", "domain": "sentry.io", "industry": "Developer Tools", "size": "300-700", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://sentry.io", "tech_stack": ["Python", "React", "Kafka"]},
            {"name": "Grafana Labs", "domain": "grafana.com", "industry": "Observability", "size": "1000-2000", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://grafana.com", "tech_stack": ["Go", "React", "Kubernetes"]},
            {"name": "PlanetScale", "domain": "planetscale.com", "industry": "Database / Developer Tools", "size": "50-200", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://planetscale.com", "tech_stack": ["Go", "Vitess", "TypeScript"]},
            {"name": "Neon", "domain": "neon.tech", "industry": "Database / Developer Tools", "size": "100-300", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://neon.tech", "tech_stack": ["Rust", "Postgres", "TypeScript"]},
            {"name": "Temporal", "domain": "temporal.io", "industry": "Developer Tools", "size": "200-500", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://temporal.io", "tech_stack": ["Go", "Java", "TypeScript"]},
            {"name": "Sourcegraph", "domain": "sourcegraph.com", "industry": "AI / Developer Tools", "size": "200-500", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://sourcegraph.com", "tech_stack": ["Go", "TypeScript", "React"]},
            {"name": "Railway", "domain": "railway.app", "industry": "Cloud / Developer Tools", "size": "50-100", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://railway.app", "tech_stack": ["TypeScript", "Rust", "React"]},
            {"name": "Render", "domain": "render.com", "industry": "Cloud / Developer Tools", "size": "100-300", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://render.com", "tech_stack": ["Go", "Kubernetes", "React"]},
            {"name": "Aiven", "domain": "aiven.io", "industry": "Cloud Data Infrastructure", "size": "500-1000", "headquarters": "Helsinki, Finland", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://aiven.io", "tech_stack": ["Python", "Go", "Kubernetes"]},
            {"name": "ClickHouse", "domain": "clickhouse.com", "industry": "Database / Analytics", "size": "300-700", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://clickhouse.com", "tech_stack": ["C++", "Go", "TypeScript"]},
            {"name": "MotherDuck", "domain": "motherduck.com", "industry": "Data Infrastructure", "size": "50-150", "headquarters": "Seattle, WA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://motherduck.com", "tech_stack": ["Python", "DuckDB", "TypeScript"]},
            {"name": "Dagster Labs", "domain": "dagster.io", "industry": "Data Infrastructure", "size": "100-300", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://dagster.io", "tech_stack": ["Python", "React", "GraphQL"]},
            {"name": "Astral", "domain": "astral.sh", "industry": "Developer Tools", "size": "10-50", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://astral.sh", "tech_stack": ["Rust", "Python"]},
            {"name": "Turso", "domain": "turso.tech", "industry": "Database / Edge", "size": "10-50", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://turso.tech", "tech_stack": ["Rust", "SQLite", "TypeScript"]},
            {"name": "Clerk", "domain": "clerk.com", "industry": "Developer Tools / Identity", "size": "100-300", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://clerk.com", "tech_stack": ["TypeScript", "React", "Go"]},
            {"name": "Convex", "domain": "convex.dev", "industry": "Developer Tools / Backend", "size": "50-100", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://convex.dev", "tech_stack": ["TypeScript", "React", "Rust"]},
            {"name": "Mintlify", "domain": "mintlify.com", "industry": "Developer Tools", "size": "10-50", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://mintlify.com", "tech_stack": ["TypeScript", "React", "Next.js"]},
            {"name": "Resend", "domain": "resend.com", "industry": "Developer Tools / Email", "size": "10-50", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://resend.com", "tech_stack": ["TypeScript", "React", "Postgres"]},
            {"name": "Inngest", "domain": "inngest.com", "industry": "Developer Tools", "size": "10-50", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://inngest.com", "tech_stack": ["Go", "TypeScript", "React"]},
            {"name": "Trigger.dev", "domain": "trigger.dev", "industry": "Developer Tools", "size": "10-50", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://trigger.dev", "tech_stack": ["TypeScript", "React", "Postgres"]},
            {"name": "Postman", "domain": "postman.com", "industry": "Developer Tools", "size": "1000-2000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://postman.com", "tech_stack": ["JavaScript", "React", "Node.js"]},
            {"name": "Docker", "domain": "docker.com", "industry": "Developer Tools", "size": "500-1000", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://docker.com", "tech_stack": ["Go", "React", "Kubernetes"]},
            {"name": "HashiCorp", "domain": "hashicorp.com", "industry": "Cloud Infrastructure", "size": "2000-5000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://hashicorp.com", "tech_stack": ["Go", "Terraform", "Kubernetes"]},
            {"name": "Roboflow", "domain": "roboflow.com", "industry": "Computer Vision", "size": "50-200", "headquarters": "Remote", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://roboflow.com", "tech_stack": ["Python", "PyTorch", "React"]},
            {"name": "Adept", "domain": "adept.ai", "industry": "AI Agents", "size": "50-200", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://adept.ai", "tech_stack": ["Python", "PyTorch", "React"]},
            {"name": "Harvey", "domain": "harvey.ai", "industry": "AI / Legal Tech", "size": "100-300", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://harvey.ai", "tech_stack": ["Python", "TypeScript", "React"]},
            {"name": "Glean", "domain": "glean.com", "industry": "Enterprise AI Search", "size": "500-1000", "headquarters": "Palo Alto, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://glean.com", "tech_stack": ["Java", "Python", "React"]},
            {"name": "Hebbia", "domain": "hebbia.ai", "industry": "Enterprise AI", "size": "50-200", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://hebbia.ai", "tech_stack": ["Python", "TypeScript", "React"]},
            {"name": "Cognition", "domain": "cognition.ai", "industry": "AI / Developer Tools", "size": "50-200", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cognition.ai", "tech_stack": ["Python", "TypeScript", "React"]},
            {"name": "Cursor", "domain": "cursor.com", "industry": "AI / Developer Tools", "size": "50-200", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cursor.com", "tech_stack": ["TypeScript", "Rust", "React"]},
        ]
        filtered = [
            c for c in fallback
            if c["domain"].lower() not in excluded
            and c["name"].lower() not in excluded_company_names
        ]
        return [normalize_company(c, "AI Discovery") for c in filtered]
