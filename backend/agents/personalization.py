"""
PersonalizationAgent — Extracts company-specific insights for personalized outreach.

Builds personalization signals from the real data already gathered during
discovery (industry, tech stack, open roles, description) and, when an OpenAI key
is available, distills a short, grounded summary. It never fabricates news or
facts about a company.
"""
from typing import Any

from .event_logger import AgentEventLogger
from services.llm_client import chat_json, llm_available


class PersonalizationAgent:
    """Derive outreach personalization signals from real, discovered company data."""

    AGENT_NAME = "PersonalizationAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        company: dict[str, Any],
        **kwargs: Any,
    ) -> dict:
        company_name = company.get("name", "Unknown")
        domain = company.get("domain", "")

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Building personalization signals for {company_name}",
            metadata={"company": company_name, "domain": domain},
        )

        insights = self._base_insights(company)

        llm_summary = await self._llm_summary(company)
        if llm_summary:
            insights.update(llm_summary)

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Personalization ready for {company_name} — {len(insights)} signals",
            metadata={"company": company_name, "insights": insights},
        )

        return insights

    def _base_insights(self, company: dict[str, Any]) -> dict[str, Any]:
        """Ground insights in fields already populated by the discovery sources."""
        open_positions = company.get("open_positions") or []
        roles = [
            str(p.get("title", "")).strip()
            for p in open_positions
            if isinstance(p, dict) and p.get("title")
        ]
        insights: dict[str, Any] = {}
        if company.get("tech_stack"):
            insights["tech_stack"] = company.get("tech_stack", [])[:10]
        if company.get("industry"):
            insights["industry"] = company.get("industry")
        if company.get("description"):
            insights["about"] = company.get("description")
        if roles:
            insights["open_roles"] = roles[:8]
        if company.get("culture_tags"):
            insights["culture_signals"] = company.get("culture_tags", [])[:6]
        if company.get("hiring_status"):
            insights["hiring_status"] = company.get("hiring_status")
        return insights

    async def _llm_summary(self, company: dict[str, Any]) -> dict[str, Any] | None:
        if not llm_available():
            return None
        name = company.get("name", "the company")
        context = {
            "name": name,
            "industry": company.get("industry", ""),
            "description": company.get("description", ""),
            "tech_stack": company.get("tech_stack", [])[:12],
            "open_roles": [
                p.get("title")
                for p in (company.get("open_positions") or [])[:6]
                if isinstance(p, dict)
            ],
        }
        result = await chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You summarize a company for personalized job outreach. Use ONLY the "
                        "provided facts — do not invent news, funding, or products."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Given this company data, return ONLY a JSON object with "
                        '"talking_points" (2-3 short, specific hooks an applicant could '
                        'reference) and "why_relevant" (one sentence). Data:\n'
                        f"{context}"
                    ),
                },
            ],
            temperature=0.5,
            max_tokens=400,
        )
        if not result:
            return None
        cleaned: dict[str, Any] = {}
        if result.get("talking_points"):
            cleaned["talking_points"] = result["talking_points"]
        if result.get("why_relevant"):
            cleaned["why_relevant"] = result["why_relevant"]
        return cleaned or None
