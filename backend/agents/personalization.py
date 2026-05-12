"""PersonalizationAgent - builds structured company-specific outreach profiles."""
from typing import Any

from .event_logger import AgentEventLogger
from services.personalization_service import PersonalizationService


class PersonalizationAgent:
    """Agent wrapper around the production personalization service."""

    AGENT_NAME = "PersonalizationAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger
        self.service = PersonalizationService()

    async def run(
        self,
        task_id: str,
        company: dict[str, Any],
        user_id: str = "anonymous",
        user_profile: dict[str, Any] | None = None,
        preferences: dict[str, Any] | None = None,
        resume: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
        links_analysis: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict:
        company_name = company.get("name", "Unknown")
        domain = company.get("domain", "")

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Starting personalization analysis for {company_name}",
            metadata={"company": company_name, "domain": domain, "user_id": user_id},
        )
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message=f"Matching resume, preferences, links, company data, and role context for {company_name}",
            metadata={"company": company_name, "user_id": user_id},
        )

        profile = await self.service.generate_profile(
            user_id=user_id,
            company=company,
            user_profile=user_profile or kwargs.get("profile"),
            preferences=preferences,
            resume=resume,
            job=job,
            links_analysis=links_analysis,
        )
        result = profile.model_dump()

        try:
            from db.supabase import supabase_client

            await supabase_client.upsert_personalization_profile(result)
        except Exception:
            pass

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Completed personalization for {company_name} with fit score {result.get('fit_score')}",
            metadata={"company": company_name, "insights": result, "user_id": user_id},
        )
        return result
