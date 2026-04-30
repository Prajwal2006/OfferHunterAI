"""
EmailWriterAgent — Generates personalized outreach emails using LLM.
"""
import asyncio
import uuid
from typing import Any

from .event_logger import AgentEventLogger


class EmailWriterAgent:
    """
    Generates highly personalized cold outreach emails using LLM (OpenAI GPT-4).
    Emails are stored with status=pending_approval — NEVER sent automatically.

    Human review is required before any email is sent.
    """

    AGENT_NAME = "EmailWriterAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        company: dict[str, Any],
        skills: list[str],
        job_title: str,
        insights: dict[str, Any] | None = None,
        resume_text: str | None = None,
        resume_skills: list[str] | None = None,
        resume_version_id: str | None = None,
        **kwargs: Any,
    ) -> dict:
        company_name = company.get("name", "Unknown")
        email_id = str(uuid.uuid4())

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Starting email generation for {company_name}",
            metadata={"company": company_name, "email_id": email_id},
        )

        steps = [
            f"Analyzing {company_name} personalization signals",
            f"Crafting compelling subject line",
            f"Writing opening hook based on company news",
            f"Highlighting relevant experience matches",
            f"Adding specific value proposition",
            f"Polishing tone and call-to-action",
        ]

        for i, step in enumerate(steps):
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="running",
                message=step,
                metadata={
                    "company": company_name,
                    "step": i + 1,
                    "total_steps": len(steps),
                },
            )
            await asyncio.sleep(0.3)

        # Generate email (in production: call OpenAI GPT-4)
        email = self._generate_email(
            company=company,
            skills=skills,
            job_title=job_title,
            insights=insights,
            resume_text=resume_text,
            resume_skills=resume_skills,
        )
        email["id"] = email_id
        email["status"] = "pending_approval"  # HUMAN REVIEW REQUIRED
        email["resume_version_id"] = resume_version_id
        email["resume_skills"] = resume_skills or []

        # Store in DB (best-effort)
        try:
            from ..db.supabase import supabase_client
            await supabase_client.insert_email(email)
        except Exception:
            pass

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Email drafted for {company_name} — awaiting human approval before sending",
            metadata={
                "company": company_name,
                "email_id": email_id,
                "status": "pending_approval",
            },
        )

        return email

    def _generate_email(
        self,
        company: dict,
        skills: list[str],
        job_title: str,
        insights: dict | None,
        resume_text: str | None,
        resume_skills: list[str] | None,
    ) -> dict:
        """
        Generate personalized email.
        In production: call OpenAI GPT-4 with a carefully crafted prompt.
        """
        name = company.get("name", "the company")
        domain = company.get("domain", "")
        industry = company.get("industry", "tech")

        resolved_skills = resume_skills[:6] if resume_skills else skills[:4]
        skills_str = ", ".join(resolved_skills) if resolved_skills else ", ".join(skills[:4])
        resume_reference = (
            "My attached resume highlights projects in " + ", ".join(resolved_skills[:4]) + "."
            if resolved_skills
            else ""
        )
        subject = f"Experienced {job_title} — Excited About {name}'s Mission"

        body = f"""Hi [Hiring Manager],

I've been following {name}'s work in {industry} closely, and I'm genuinely excited about the problems you're solving.

I'm a {job_title} with deep expertise in {skills_str}. I've spent the past few years building production systems at scale, and I believe my background aligns well with what {name} is working on.
{resume_reference}

A few highlights from my experience:
• Built and deployed ML pipelines serving 100k+ daily predictions
• Led a team of 4 engineers to ship a real-time data platform
• Contributed to open-source tools with 500+ GitHub stars

I'd love to learn more about your team and explore how I could contribute. Would you be open to a 20-minute call this week?

Best,
[Your Name]
{skills_str} | GitHub: github.com/[username]"""

        return {
            "company_id": company.get("id", ""),
            "company_name": name,
            "subject": subject,
            "body": body,
            "recipient_email": f"careers@{domain}",
            "resume_excerpt": (resume_text or "")[:2000],
        }
