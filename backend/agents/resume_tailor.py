"""
ResumeTailorAgent — Suggests resume changes tailored to a specific company/role.

Analyzes the candidate's actual resume against the target company's roles and
tech stack and proposes concrete, grounded edits. Real LLM generation when an
OpenAI key is configured; an honest, resume-derived fallback otherwise.
"""
from typing import Any

from .event_logger import AgentEventLogger
from services.llm_client import chat_json, llm_available


class ResumeTailorAgent:
    """
    Analyzes the job/company context and the candidate's real resume to suggest
    bullet rewrites, keywords to add, and gaps to address.
    """

    AGENT_NAME = "ResumeTailorAgent"

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        company: dict[str, Any] | None = None,
        resume_text: str | None = None,
        user_profile: dict[str, Any] | None = None,
        job_title: str = "",
        **kwargs: Any,
    ) -> dict:
        company = company or {}
        company_name = company.get("name", "Unknown")
        resume_text = (resume_text or (user_profile or {}).get("raw_text") or "").strip()

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Tailoring resume for {company_name}",
            metadata={"company": company_name},
        )

        if not resume_text:
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="failed",
                message="No resume text available to tailor. Upload a resume first.",
                metadata={"company": company_name},
            )
            return {"company": company_name, "error": "no_resume"}

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message=(
                f"Analyzing your resume against {company_name}'s roles"
                if llm_available()
                else f"Generating resume guidance for {company_name} (set OPENAI_API_KEY for tailored rewrites)"
            ),
            metadata={"company": company_name},
        )

        tailored = await self._tailor(company, resume_text, job_title, user_profile or {})

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Resume suggestions ready for {company_name}",
            metadata={"company": company_name, **tailored},
        )

        return tailored

    async def _tailor(
        self,
        company: dict[str, Any],
        resume_text: str,
        job_title: str,
        user_profile: dict[str, Any],
    ) -> dict[str, Any]:
        name = company.get("name", "the company")
        industry = company.get("industry", "")
        tech_stack = ", ".join(company.get("tech_stack", [])[:12])
        open_positions = company.get("open_positions") or []
        roles_str = ", ".join(
            str(p.get("title", "")) for p in open_positions[:5] if isinstance(p, dict)
        ) or job_title

        system = (
            "You are an expert technical resume reviewer. You suggest concrete, honest "
            "improvements grounded ONLY in the candidate's actual resume. Never fabricate "
            "experience, metrics, or employers. Rewrites must preserve truth while improving "
            "clarity, impact, and alignment to the target role."
        )
        user = f"""Tailor this resume for a specific company.

TARGET COMPANY: {name}
INDUSTRY: {industry}
TARGET ROLE(S): {roles_str or 'N/A'}
COMPANY TECH STACK: {tech_stack or 'N/A'}

CANDIDATE RESUME (ground truth):
{resume_text[:7000]}

Return ONLY a JSON object:
{{
  "summary": "2-3 sentence assessment of fit and what to emphasize",
  "suggested_bullets": ["rewritten or new bullet grounded in the resume", "..."],
  "keywords_to_add": ["relevant keyword from the role the resume is missing", "..."],
  "gaps": ["honest gap between the resume and this role", "..."]
}}
Provide 3-5 suggested_bullets and 3-6 keywords_to_add."""

        result = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.5,
            max_tokens=1100,
        )
        if result and (result.get("suggested_bullets") or result.get("summary")):
            return {
                "company": name,
                "summary": result.get("summary", ""),
                "suggested_bullets": result.get("suggested_bullets", [])[:6],
                "keywords_added": result.get("keywords_to_add", [])[:8],
                "gaps": result.get("gaps", [])[:6],
                "generated_by": "llm",
            }

        return self._fallback(company, resume_text, user_profile, roles_str)

    def _fallback(
        self,
        company: dict[str, Any],
        resume_text: str,
        user_profile: dict[str, Any],
        roles_str: str,
    ) -> dict[str, Any]:
        """Honest, resume-derived guidance when no LLM is available."""
        name = company.get("name", "the company")
        company_keywords = [
            *company.get("tech_stack", []),
            *(company.get("culture_tags", []) or []),
        ]
        resume_lower = resume_text.lower()
        missing = [k for k in company_keywords if k and k.lower() not in resume_lower][:6]

        return {
            "company": name,
            "summary": (
                f"Align your resume with {name}'s focus on {roles_str or 'this role'}. "
                "Lead each bullet with a concrete outcome and mirror the company's vocabulary "
                "where it honestly reflects your experience."
            ),
            "suggested_bullets": [
                "Rewrite your top 3 bullets to start with an action verb and an outcome "
                "(what changed, by how much) using numbers already true to your work.",
                "Surface projects that use the same tools as the target role near the top.",
                "Trim unrelated experience so the most relevant work is most visible.",
            ],
            "keywords_added": missing,
            "gaps": (
                [f"Resume does not yet mention: {', '.join(missing)}"] if missing else []
            ),
            "generated_by": "template",
        }
