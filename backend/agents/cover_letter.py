"""
CoverLetterAgent — Generates a tailored cover letter grounded in the real resume.

Produces a complete, ready-to-edit cover letter for a specific company/role using
the candidate's actual resume. Real LLM generation when an OpenAI key is set, with
an honest, resume-derived fallback otherwise. Never invents experience or metrics.
"""
from typing import Any

from .event_logger import AgentEventLogger
from services.llm_client import chat_json, llm_available


class CoverLetterAgent:
    AGENT_NAME = "CoverLetterAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        company: dict[str, Any] | None = None,
        resume_text: str | None = None,
        user_profile: dict[str, Any] | None = None,
        job_title: str = "",
        tone: str = "professional",
        **kwargs: Any,
    ) -> dict[str, Any]:
        company = company or {}
        company_name = company.get("name", "the company")
        user_profile = user_profile or {}
        resume_text = (resume_text or user_profile.get("raw_text") or "").strip()
        applicant_name = (user_profile.get("full_name") or "").strip()

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Writing a cover letter for {company_name}",
            metadata={"company": company_name},
        )

        if not resume_text:
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="failed",
                message="No resume text available. Upload a resume first.",
                metadata={"company": company_name},
            )
            return {"company": company_name, "error": "no_resume"}

        result = await self._generate(company, resume_text, job_title, applicant_name, tone)

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Cover letter ready for {company_name}",
            metadata={"company": company_name, "generated_by": result.get("generated_by")},
        )
        return result

    async def _generate(
        self,
        company: dict[str, Any],
        resume_text: str,
        job_title: str,
        applicant_name: str,
        tone: str,
    ) -> dict[str, Any]:
        name = company.get("name", "the company")
        industry = company.get("industry", "")
        description = company.get("description", "")
        open_positions = company.get("open_positions") or []
        role = job_title or next(
            (str(p.get("title", "")) for p in open_positions if isinstance(p, dict) and p.get("title")),
            "",
        )

        system = (
            "You are an expert cover-letter writer. You write a complete, specific, "
            "one-page cover letter grounded ONLY in the candidate's actual resume — "
            "never invent employers, metrics, or achievements. Tie the candidate's real "
            f"experience to the target company. Tone: {tone}. 250-350 words, 3-4 short "
            "paragraphs, no clichés."
        )
        sign_off = applicant_name or "[Your Name]"
        user = f"""Write a tailored cover letter.

COMPANY: {name}
INDUSTRY: {industry}
ABOUT: {description}
TARGET ROLE: {role or 'an open role that fits the candidate'}
APPLICANT NAME: {sign_off}

CANDIDATE RESUME (ground truth — use only this):
{resume_text[:7000]}

Return ONLY a JSON object: {{"cover_letter": "<the full letter, including greeting and sign-off>"}}.
Use 'Dear Hiring Manager,' if no specific name is known, and sign off as '{sign_off}'."""

        result = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            max_tokens=900,
        )
        if result and result.get("cover_letter"):
            return {
                "company": name,
                "role": role,
                "cover_letter": result["cover_letter"],
                "generated_by": "llm",
            }

        return self._fallback(name, role, industry, applicant_name)

    def _fallback(
        self, name: str, role: str, industry: str, applicant_name: str
    ) -> dict[str, Any]:
        """Honest scaffold (no fabricated specifics) when no LLM is available."""
        role_str = role or "the open role"
        sign_off = applicant_name or "[Your Name]"
        letter = f"""Dear Hiring Manager,

I'm writing to express my interest in {role_str} at {name}. Your work in {industry or 'this space'} resonates with the kind of problems I want to help solve, and I believe my background is a strong fit.

[In 2-3 sentences, connect your most relevant experience to this role — reference a specific project or responsibility from your resume and the concrete result it produced.]

[In 2-3 sentences, explain why {name} specifically: what about their product, mission, or engineering culture draws you, and how you would contribute in the first few months.]

I'd welcome the chance to discuss how I can contribute to {name}. Thank you for your time and consideration.

Sincerely,
{sign_off}"""
        return {
            "company": name,
            "role": role,
            "cover_letter": letter,
            "generated_by": "template",
        }
