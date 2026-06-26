"""
EmailWriterAgent — Generates personalized outreach emails using LLM.
"""
import uuid
from typing import Any

from .event_logger import AgentEventLogger
from services.llm_client import chat_json, llm_available


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
        skills: list[str] | None = None,
        job_title: str = "",
        insights: dict[str, Any] | None = None,
        resume_text: str | None = None,
        resume_skills: list[str] | None = None,
        resume_version_id: str | None = None,
        **kwargs: Any,
    ) -> dict:
        company_name = company.get("name", "Unknown")
        email_id = str(uuid.uuid4())

        # Tolerate alternate handoff payloads (e.g. /handoff passes matched_skills
        # and a user_profile instead of skills/job_title).
        user_profile = kwargs.get("user_profile") or {}
        if not skills:
            skills = kwargs.get("matched_skills") or user_profile.get("skills") or []
        if not job_title:
            preferred = user_profile.get("preferred_domains") or []
            job_title = preferred[0] if preferred else ""
        if not resume_text:
            resume_text = user_profile.get("raw_text")

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Starting email generation for {company_name}",
            metadata={"company": company_name, "email_id": email_id},
        )

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message=(
                f"Drafting a personalized email for {company_name} grounded in your resume"
                if llm_available()
                else f"Drafting a starter email for {company_name} (set OPENAI_API_KEY for full personalization)"
            ),
            metadata={"company": company_name},
        )

        # Generate email — real LLM generation grounded in the user's resume,
        # with a deterministic, non-fabricated fallback when no key is set.
        email = await self._generate_email(
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
            from db.supabase import supabase_client
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

    async def _generate_email(
        self,
        company: dict,
        skills: list[str],
        job_title: str,
        insights: dict | None,
        resume_text: str | None,
        resume_skills: list[str] | None,
    ) -> dict:
        """Generate a personalized email via the LLM, grounded in the real resume.

        Falls back to a deterministic template only when no LLM is available.
        Crucially, neither path invents accomplishments — the LLM is instructed to
        use only what is in the resume, and the fallback uses fill-in placeholders.
        """
        name = company.get("name", "the company")
        domain = company.get("domain", "")

        llm_email = await self._generate_email_llm(
            company=company,
            job_title=job_title,
            insights=insights,
            resume_text=resume_text,
            resume_skills=resume_skills,
            skills=skills,
        )
        if llm_email:
            return {
                "company_id": company.get("id", ""),
                "company_name": name,
                "subject": llm_email.get("subject", f"{job_title} interested in {name}"),
                "body": llm_email.get("body", ""),
                "recipient_email": f"careers@{domain}" if domain else "",
                "resume_excerpt": (resume_text or "")[:2000],
                "generated_by": "llm",
            }

        return self._fallback_email(company, skills, job_title, resume_text, resume_skills)

    async def _generate_email_llm(
        self,
        *,
        company: dict,
        job_title: str,
        insights: dict | None,
        resume_text: str | None,
        resume_skills: list[str] | None,
        skills: list[str],
    ) -> dict | None:
        name = company.get("name", "the company")
        industry = company.get("industry", "")
        description = company.get("description", "")
        open_positions = company.get("open_positions") or []
        roles_str = ", ".join(
            str(p.get("title", "")) for p in open_positions[:5] if isinstance(p, dict)
        )
        insight_str = ""
        if insights:
            insight_str = "; ".join(f"{k}: {v}" for k, v in list(insights.items())[:6])

        resume_block = (resume_text or "").strip()[:6000]
        if not resume_block:
            resume_block = "Skills: " + ", ".join((resume_skills or skills or [])[:15])

        system = (
            "You are an expert career coach who writes concise, genuine cold outreach "
            "emails. You ONLY use facts present in the candidate's resume — never invent "
            "metrics, employers, or achievements. If the resume lacks a specific metric, "
            "stay qualitative. Keep it under 180 words, warm but professional, and end "
            "with a low-friction call to action."
        )
        user = f"""Write a personalized cold outreach email.

CANDIDATE TARGET ROLE: {job_title or 'Software Engineer'}

COMPANY:
- Name: {name}
- Industry: {industry}
- About: {description}
- Open roles: {roles_str or 'N/A'}
- Extra signals: {insight_str or 'N/A'}

CANDIDATE RESUME (ground truth — use only this):
{resume_block}

Return ONLY a JSON object: {{"subject": "<subject line>", "body": "<email body with a [Your Name] sign-off>"}}.
The body should reference 2-3 specific, real strengths from the resume that fit this company.
Use '[Hiring Manager]' as the greeting placeholder if no name is known."""

        result = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            max_tokens=900,
        )
        if result and result.get("body"):
            return result
        return None

    def _fallback_email(
        self,
        company: dict,
        skills: list[str],
        job_title: str,
        resume_text: str | None,
        resume_skills: list[str] | None,
    ) -> dict:
        """Honest, non-fabricated starter email used only when no LLM is available."""
        name = company.get("name", "the company")
        domain = company.get("domain", "")
        industry = company.get("industry", "your industry")
        role = job_title or "the role"

        resolved_skills = (resume_skills or skills or [])[:6]
        skills_str = ", ".join(resolved_skills) if resolved_skills else "my background"

        subject = f"{role} interested in {name}"
        body = f"""Hi [Hiring Manager],

I've been following {name}'s work in {industry} and I'm excited about what your team is building.

I'm interested in {role} opportunities and bring experience in {skills_str}. I'd welcome the chance to share how my background could support your goals.

[Add 2-3 specific accomplishments from your resume here.]

Would you be open to a short call this week?

Best,
[Your Name]"""

        return {
            "company_id": company.get("id", ""),
            "company_name": name,
            "subject": subject,
            "body": body,
            "recipient_email": f"careers@{domain}" if domain else "",
            "resume_excerpt": (resume_text or "")[:2000],
            "generated_by": "template",
        }
