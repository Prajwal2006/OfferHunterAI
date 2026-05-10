"""EmailWriterAgent - generates human-reviewed outreach drafts."""
from typing import Any

from .event_logger import AgentEventLogger
from services.email_writer_service import EmailWriterService
from services.versioning_service import VersioningService


class EmailWriterAgent:
    """Generates personalized outreach drafts and stores immutable initial versions."""

    AGENT_NAME = "EmailWriterAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger
        self.service = EmailWriterService()
        self.versioning = VersioningService()

    async def run(
        self,
        task_id: str,
        company: dict[str, Any],
        skills: list[str] | None = None,
        job_title: str | None = None,
        insights: dict[str, Any] | None = None,
        personalization: dict[str, Any] | None = None,
        user_id: str = "anonymous",
        user_profile: dict[str, Any] | None = None,
        preferences: dict[str, Any] | None = None,
        resume: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
        resume_text: str | None = None,
        resume_skills: list[str] | None = None,
        resume_version_id: str | None = None,
        **kwargs: Any,
    ) -> dict:
        company_name = company.get("name", "Unknown")
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Starting email generation for {company_name}",
            metadata={"company": company_name},
        )

        if not job and job_title:
            job = {"title": job_title}
        if not resume and (resume_text or resume_skills or resume_version_id):
            resume = {
                "id": resume_version_id,
                "extracted_text": resume_text or "",
                "extracted_skills": resume_skills or skills or [],
            }
        personalization = personalization or insights or {}

        draft = await self.service.generate_email(
            user_id=user_id,
            company=company,
            personalization=personalization,
            user_profile=user_profile,
            preferences=preferences,
            resume=resume,
            job=job,
            recipient=recipient,
            outreach_type=kwargs.get("outreach_type"),
        )
        result = draft.model_dump()
        result["resume_version_id"] = resume_version_id or (resume or {}).get("id")
        result["resume_skills"] = resume_skills or skills or []

        try:
            from db.supabase import supabase_client

            stored = await supabase_client.upsert_email_draft({**result, "version_number": 1})
            version = self.versioning.create_version(
                draft={**stored, "version_number": 0},
                event_type="generated",
                editor="ai",
                changes={"task_id": task_id},
            )
            await supabase_client.insert_email_version(version)
            await supabase_client.insert_generated_subjects(stored.get("id") or result["id"], result.get("subjects") or [])

            # Legacy table compatibility for existing review/pipeline screens.
            await supabase_client.insert_email(
                {
                    "id": stored.get("id") or result["id"],
                    "company_id": result.get("company_id"),
                    "company_name": result.get("company_name"),
                    "subject": result.get("subject"),
                    "body": result.get("body"),
                    "recipient_email": result.get("recipient_email"),
                    "status": "pending_approval",
                    "resume_version_id": result.get("resume_version_id"),
                    "resume_skills": result.get("resume_skills") or [],
                }
            )
            result = stored
        except Exception:
            pass

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Email draft created for {company_name} and queued for human review",
            metadata={"company": company_name, "draft_id": result.get("id")},
        )
        return result
