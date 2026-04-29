"""
CompanyFinderAgent — Discovers relevant companies based on user skills and job title.
"""
import asyncio
import uuid
from typing import Any, Optional

from .event_logger import AgentEventLogger


class CompanyFinderAgent:
    """
    Finds companies relevant to a candidate's skills using web scraping
    and AI-powered relevance scoring.

    In production, this integrates with:
    - LinkedIn Jobs API / scraper
    - Crunchbase API
    - HackerNews "Who's Hiring" thread
    """

    AGENT_NAME = "CompanyFinderAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        skills: list[str],
        job_title: str,
        count: int = 10,
        **kwargs: Any,
    ) -> list[dict]:
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Starting company discovery for '{job_title}' with skills: {', '.join(skills[:3])}",
            metadata={"skills": skills, "job_title": job_title, "count": count},
        )

        companies = []
        sources = ["LinkedIn", "HackerNews", "Crunchbase", "AngelList"]

        for i, source in enumerate(sources):
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="running",
                message=f"Scanning {source} for {job_title} opportunities...",
                metadata={"source": source, "progress": f"{i+1}/{len(sources)}"},
            )
            await asyncio.sleep(0.5)  # Simulate scraping delay

            # Simulated discovery results
            batch = self._simulate_discovery(source, skills, job_title)
            companies.extend(batch)

        # Deduplicate and rank
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message=f"Ranking {len(companies)} companies by relevance...",
            metadata={"raw_count": len(companies)},
        )
        await asyncio.sleep(0.3)

        ranked = sorted(companies, key=lambda c: c["relevance_score"], reverse=True)[:count]

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Found {len(ranked)} companies matching your profile",
            metadata={"companies": [c["name"] for c in ranked], "count": len(ranked)},
        )

        return ranked

    def _simulate_discovery(
        self, source: str, skills: list[str], job_title: str
    ) -> list[dict]:
        """Simulate company discovery results."""
        sample_companies = [
            {"name": "Stripe", "domain": "stripe.com", "industry": "Fintech", "size": "5000-10000", "relevance_score": 0.95},
            {"name": "OpenAI", "domain": "openai.com", "industry": "AI/ML", "size": "500-1000", "relevance_score": 0.98},
            {"name": "Vercel", "domain": "vercel.com", "industry": "Developer Tools", "size": "100-500", "relevance_score": 0.92},
            {"name": "Anthropic", "domain": "anthropic.com", "industry": "AI/ML", "size": "100-500", "relevance_score": 0.97},
            {"name": "Supabase", "domain": "supabase.com", "industry": "Developer Tools", "size": "50-100", "relevance_score": 0.89},
            {"name": "Linear", "domain": "linear.app", "industry": "Productivity", "size": "50-100", "relevance_score": 0.82},
            {"name": "Cohere", "domain": "cohere.com", "industry": "AI/ML", "size": "100-500", "relevance_score": 0.94},
            {"name": "Mistral", "domain": "mistral.ai", "industry": "AI/ML", "size": "50-100", "relevance_score": 0.91},
        ]
        import random
        return random.sample(sample_companies, min(3, len(sample_companies)))
