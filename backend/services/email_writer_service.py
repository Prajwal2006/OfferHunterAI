"""AI email generation service for one personalized cold email draft."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .ai_common import AIServiceError, OpenAIJsonClient, compact_json
from .logger_service import get_logger


DEFAULT_TEMPLATE_FALLBACK_NOTICE = "USING DEFAULT TEMPLATE EMAIL BECAUSE OPENAI EMAIL GENERATION FAILED OR WAS DISABLED"


class GeneratedEmailDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    company_id: str
    company_name: str
    outreach_type: str
    tone: str
    subject: str
    body: str
    recipient_email: str | None = None
    status: str = "pending_approval"
    generation_source: str = "openai"
    generation_status: str = "completed"
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_call_id: str | None = None
    prompt_version: str = "email_single_v1"
    generation_error: str | None = None
    generation_context_summary: dict[str, Any] = {}
    generation_metadata: dict[str, Any] = {}
    generation_attempt: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EmailWriterService:
    """Writes concise, human outreach emails from a personalization profile."""

    def __init__(self) -> None:
        self.ai = OpenAIJsonClient()
        self.logger = get_logger()

    async def generate_email(
        self,
        *,
        user_id: str,
        company: dict[str, Any],
        personalization: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        preferences: dict[str, Any] | None = None,
        resume: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
        recipient: dict[str, Any] | None = None,
        outreach_type: str | None = None,
        use_ai: bool = True,
    ) -> GeneratedEmailDraft:
        fallback = self._safe_deterministic_email(
            user_id=user_id,
            company=company,
            personalization=personalization,
            user_profile=user_profile or {},
            preferences=preferences or {},
            resume=resume or {},
            job=job or {},
            recipient=recipient or {},
            outreach_type=outreach_type,
        )
        if not use_ai or not self.ai.enabled:
            reason = "OUTREACH_DRAFT_USE_AI is disabled" if not use_ai else "OpenAI client is not configured"
            return self._use_default_template(
                fallback,
                reason=reason,
                user_id=user_id,
                company=company,
                personalization=personalization,
                use_ai=use_ai,
            )

        context = {
            "company": company,
            "personalization": personalization,
            "user_profile": user_profile or {},
            "preferences": preferences or {},
            "resume_excerpt": (resume or {}).get("extracted_text", "")[:4500],
            "job": job or {},
            "recipient": recipient or {},
            "email_rules": [
                "Write every email body in FIRST PERSON from the candidate's perspective.",
                "Use I, me, my, and mine. Never say the user, the candidate, the applicant, or this profile.",
                "Do not write phrases like 'the user is qualified in'; write 'I have experience in' instead.",
                "Open directly with a specific candidate-company fit hook.",
                "Sound like a strong, thoughtful student/operator writing one personal note, not a cover letter.",
                "Make the first two sentences specific to the company and the candidate's fit.",
                "Mention internship availability and whether the candidate is open to full-time or part-time work when preferences include it.",
                "Include the strongest relevant links from portfolio, GitHub, LinkedIn, or other profile links.",
                "Use Markdown-style bold sparingly for 1-3 skimmable labels or value points in the body, such as **Availability** or **Portfolio**.",
                "Do not sound AI-generated.",
                "Avoid generic template phrases.",
                "Avoid 'I hope you are doing well' unless no better opener is available.",
                "Avoid overexplaining. Prefer precise, confident sentences.",
                "Do not overload with more than three proof points.",
                "No fabricated metrics.",
                "Write exactly one email body under 240 words.",
            ],
        }
        system = (
            "You are OfferHunterAI's Email Writer Agent. Return only valid JSON. "
            "Write human, concise, deeply personalized career outreach. "
            "Every draft must sound like the candidate wrote it personally in first person. "
            "Use natural plain text with light Markdown emphasis where useful. "
            "Optimize for a reply from a busy founder, recruiter, or hiring manager."
        )
        user = (
            "Generate JSON with exactly these keys: subject, body, generation_metadata. "
            "Return one polished cold email only. Do not return variants or multiple subject options. "
            "The email should be warm, direct, easy to skim, and specific to this company. "
            "When the recipient is unknown, use a clean greeting such as 'Hi [Company] team,' instead of a formal 'Dear'. "
            f"Context:\n{compact_json(context)}"
        )
        try:
            result = await self.ai.create_json_detailed(
                system=system,
                user=user,
                temperature=0.55,
                max_tokens=1400,
                user_id=user_id,
                context_metadata={
                    "operation": "email_writer",
                    "company": company,
                    "personalization": personalization,
                    "user_profile": user_profile or {},
                    "preferences": preferences or {},
                    "resume": resume or {},
                    "job": job or {},
                    "recipient": recipient or {},
                    "outreach_type": outreach_type,
                },
            )
            data = result.data
            merged = {**fallback.model_dump(), **data}
            merged["id"] = fallback.id
            merged["user_id"] = user_id
            merged["company_id"] = str(company.get("id") or "")
            merged["company_name"] = company.get("name") or fallback.company_name
            merged["outreach_type"] = outreach_type or personalization.get("outreach_type") or fallback.outreach_type
            merged["tone"] = personalization.get("tone") or fallback.tone
            merged["subject"] = str(merged.get("subject") or fallback.subject).strip()
            merged["body"] = self._sanitize_first_person(str(merged.get("body") or fallback.body))
            metadata = merged.get("generation_metadata") if isinstance(merged.get("generation_metadata"), dict) else {}
            context_summary = self._context_summary(company, personalization, user_profile or {}, preferences or {}, resume or {})
            attempt = {
                "draft_id": fallback.id,
                "user_id": user_id,
                "company_id": str(company.get("id") or ""),
                "provider": result.provider,
                "model": result.model,
                "status": "completed",
                "prompt_version": "email_single_v1",
                "request_payload": result.request_payload,
                "context_payload": result.context_payload or {},
                "raw_response": result.raw_response,
                "parsed_response": data,
                "tokens_prompt": result.tokens_prompt,
                "tokens_completion": result.tokens_completion,
                "tokens_total": result.tokens_total,
                "duration_ms": result.duration_ms,
                "completed_at": datetime.utcnow().isoformat(),
            }
            merged["generation_metadata"] = {
                **metadata,
                "generated_with_ai": True,
                "used_default_template": False,
            }
            merged["generation_source"] = "openai"
            merged["generation_status"] = "completed"
            merged["llm_provider"] = result.provider
            merged["llm_model"] = result.model
            merged["llm_call_id"] = result.call_id
            merged["prompt_version"] = "email_single_v1"
            merged["generation_context_summary"] = context_summary
            merged["generation_attempt"] = attempt
            return GeneratedEmailDraft.model_validate(merged)
        except (AIServiceError, ValueError, TypeError) as exc:
            return self._use_default_template(
                fallback,
                reason=f"{exc.__class__.__name__}: {exc}",
                user_id=user_id,
                company=company,
                personalization=personalization,
                use_ai=use_ai,
            )

    def _use_default_template(
        self,
        draft: GeneratedEmailDraft,
        *,
        reason: str,
        user_id: str,
        company: dict[str, Any],
        personalization: dict[str, Any],
        use_ai: bool,
    ) -> GeneratedEmailDraft:
        details = {
            "user_id": user_id,
            "company_id": company.get("id"),
            "company_name": company.get("name"),
            "reason": reason,
            "ai_requested": use_ai,
            "openai_enabled": self.ai.enabled,
            "fit_score": personalization.get("fit_score"),
            "draft_id": draft.id,
        }
        draft.generation_metadata = {
            **(draft.generation_metadata or {}),
            "generated_with_ai": False,
            "used_default_template": True,
            "default_template_notice": DEFAULT_TEMPLATE_FALLBACK_NOTICE,
            "default_template_reason": reason,
            "ai_requested": use_ai,
            "openai_enabled": self.ai.enabled,
        }
        draft.generation_source = "default_template"
        draft.generation_status = "fallback"
        draft.generation_error = reason
        draft.llm_provider = "openai" if self.ai.enabled else None
        draft.llm_model = self.ai.model if self.ai.enabled else None
        draft.prompt_version = "email_single_v1"
        draft.generation_context_summary = self._context_summary(company, personalization, {}, {}, {})
        draft.generation_attempt = {
            "draft_id": draft.id,
            "user_id": user_id,
            "company_id": str(company.get("id") or ""),
            "provider": "openai",
            "model": self.ai.model if self.ai.enabled else None,
            "status": "fallback",
            "prompt_version": "email_single_v1",
            "request_payload": {},
            "context_payload": {
                "company": company,
                "personalization": personalization,
            },
            "parsed_response": {"subject": draft.subject, "body": draft.body},
            "error": reason,
            "completed_at": datetime.utcnow().isoformat(),
        }
        self.logger.log_loud_marker(
            DEFAULT_TEMPLATE_FALLBACK_NOTICE,
            details,
            include_llm_debug=True,
        )
        return draft

    def _deterministic_email(
        self,
        *,
        user_id: str,
        company: dict[str, Any],
        personalization: dict[str, Any],
        user_profile: dict[str, Any],
        preferences: dict[str, Any],
        resume: dict[str, Any],
        job: dict[str, Any],
        recipient: dict[str, Any],
        outreach_type: str | None,
    ) -> GeneratedEmailDraft:
        company_name = company.get("name") or "your team"
        role = job.get("title") or (preferences.get("preferred_roles") or ["software engineering"])[0]
        full_name = user_profile.get("full_name") or "Your Name"
        resume_text = resume.get("extracted_text") or resume.get("raw_text") or ""
        raw_skills = personalization.get("relevant_skills") or user_profile.get("skills") or []
        skills = [str(skill).strip() for skill in raw_skills if skill is not None and str(skill).strip()]
        projects = personalization.get("relevant_projects") or user_profile.get("projects") or []
        links = self._collect_links(user_profile, preferences, personalization)
        greeting = f"Hi {company_name} team,"
        skill_line = ", ".join(skills[:3]) if skills else "shipping practical software"
        education_line = self._education_line(user_profile, resume_text)
        availability_line = self._availability_line(preferences)
        highlight_line = self._highlight_line(user_profile, resume_text, skills, projects)
        company_interest = self._company_interest(company, company_name)
        project_line = self._project_line(projects, skills)
        link_line = self._link_line(links)
        signoff_links = ""
        if links:
            signoff_links = "\n\n" + self._compact_link_line(links)
        cta = "I would be grateful for the opportunity to speak with you about any current or upcoming internship openings."
        if outreach_type == "networking":
            cta = "I would be grateful for the chance to learn more about your team and where someone with my background could be useful."

        medium = (
            f"{greeting}\n\n"
            f"I came across {company_name} and was drawn to {company_interest} {education_line}\n\n"
            f"I am looking for a 3-month summer internship where I can contribute quickly. {availability_line} "
            f"My strongest technical overlap is **{skill_line}**.{project_line}\n\n"
            f"{highlight_line} I would bring energy, ownership, and range across engineering, product, research, or operations wherever the team needs leverage.\n\n"
            f"{link_line}"
            f"{cta}\n\n"
            f"Best,\n{full_name}"
        )
        short = (
            f"{greeting}\n\n"
            f"I am reaching out because {company_name} looks like a team where I could make a useful summer contribution quickly. "
            f"{education_line} My background spans **{skill_line}**, and I am open to full-time or part-time internship support depending on what your team needs.\n\n"
            f"{highlight_line}{signoff_links}\n\n"
            f"{cta}\n\nBest,\n{full_name}"
        )
        bold = (
            f"{greeting}\n\n"
            f"I can move quickly across software, product, and research, and {company_name} looks like exactly the kind of team where that range can create leverage.\n\n"
            f"I am interested in a 3-month summer internship and can be flexible between **full-time and part-time** depending on your needs. "
            f"{highlight_line} I would bring hands-on experience in **{skill_line}**, strong ownership, and a willingness to jump into the work that matters most.\n\n"
            f"{link_line}"
            f"If there is room for an ambitious {role} profile this summer, I would love to talk.\n\n"
            f"Best,\n{full_name}"
        )
        fallback_body = self._sanitize_first_person(medium)
        fallback_subject = f"Summer internship interest - {company_name}"
        return GeneratedEmailDraft(
            user_id=user_id,
            company_id=str(company.get("id") or ""),
            company_name=company_name,
            outreach_type=outreach_type or personalization.get("outreach_type") or "cold_email",
            tone=personalization.get("tone") or "professional_concise",
            subject=fallback_subject,
            body=fallback_body,
            recipient_email=recipient.get("email"),
            generation_source="default_template",
            generation_status="fallback",
            prompt_version="email_single_v1",
            generation_context_summary=self._context_summary(company, personalization, user_profile, preferences, resume),
            generation_metadata={
                "fit_score": personalization.get("fit_score"),
                "strategy": personalization.get("email_strategy") or {},
                "generated_without_openai": not self.ai.enabled,
                "generated_with_ai": False,
            },
        )

    def _safe_deterministic_email(
        self,
        *,
        user_id: str,
        company: dict[str, Any],
        personalization: dict[str, Any],
        user_profile: dict[str, Any],
        preferences: dict[str, Any],
        resume: dict[str, Any],
        job: dict[str, Any],
        recipient: dict[str, Any],
        outreach_type: str | None,
    ) -> GeneratedEmailDraft:
        try:
            return self._deterministic_email(
                user_id=user_id,
                company=company,
                personalization=personalization,
                user_profile=user_profile,
                preferences=preferences,
                resume=resume,
                job=job,
                recipient=recipient,
                outreach_type=outreach_type,
            )
        except Exception as exc:
            company_name = company.get("name") or "your team"
            self.logger.log_error(
                error_type="deterministic_email_fallback_failed",
                message=str(exc),
                user_id=user_id,
                context={"company_id": company.get("id"), "company_name": company_name},
                severity="warning",
            )
            return GeneratedEmailDraft(
                user_id=user_id,
                company_id=str(company.get("id") or ""),
                company_name=company_name,
                outreach_type=outreach_type or personalization.get("outreach_type") or "cold_email",
                tone=personalization.get("tone") or "professional_concise",
                subject=f"Internship interest - {company_name}",
                body=(
                    f"Hi {company_name} team,\n\n"
                    "I am reaching out because I would love to contribute to your team this summer. "
                    "I am looking for an internship where I can add value quickly and learn from strong builders.\n\n"
                    "I can share my resume, GitHub, and portfolio and would be grateful for a quick conversation "
                    "if there is a fit for current or upcoming openings.\n\n"
                    "Best,\n"
                    f"{user_profile.get('full_name') or 'Candidate'}"
                ),
                recipient_email=recipient.get("email") if isinstance(recipient, dict) else None,
                generation_source="default_template",
                generation_status="fallback",
                prompt_version="email_single_v1",
                generation_context_summary=self._context_summary(company, personalization, user_profile, preferences, resume),
                generation_metadata={
                    "fit_score": personalization.get("fit_score"),
                    "strategy": personalization.get("email_strategy") or {},
                    "generated_without_openai": not self.ai.enabled,
                    "generated_with_ai": False,
                    "safe_fallback": True,
                },
            )

    def _context_summary(
        self,
        company: dict[str, Any],
        personalization: dict[str, Any],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        resume: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "company": {
                "name": company.get("name"),
                "domain": company.get("domain"),
                "industry": company.get("industry"),
                "description": company.get("description") or company.get("mission"),
            },
            "fit_score": personalization.get("fit_score"),
            "relevant_skills": personalization.get("relevant_skills") or [],
            "recommended_hooks": personalization.get("recommended_hooks") or [],
            "user_name": profile.get("full_name"),
            "preferred_roles": preferences.get("preferred_roles") or [],
            "employment_type": preferences.get("employment_type") or [],
            "resume_version_id": resume.get("id"),
        }

    def _education_line(self, profile: dict[str, Any], resume_text: str) -> str:
        education = profile.get("education") or []
        if education:
            first = education[0]
            if isinstance(first, dict):
                institution = first.get("institution") or first.get("school") or ""
                field = first.get("field") or first.get("major") or first.get("degree") or "Computer Science"
                honors = " in the Honors College" if "honors college" in resume_text.lower() else ""
                if institution:
                    return f"I am a {field} student{honors} at {self._format_institution(institution)}."
        if "university of alabama" in resume_text.lower():
            return "I am a Computer Science student in the Honors College at the University of Alabama."
        return "I am a computer science student and builder."

    def _availability_line(self, preferences: dict[str, Any]) -> str:
        employment = {str(item).lower() for item in preferences.get("employment_type") or []}
        earliest = preferences.get("earliest_start")
        if "internship" in employment and {"full_time", "full-time", "part_time", "part-time"} & employment:
            line = "Although the internship timeframe may be short, I can be flexible between full-time and part-time support based on what would help most."
        elif "internship" in employment:
            line = "Although the internship timeframe may be short, I can commit fully to making the summer useful for your team."
        elif {"full_time", "full-time"} & employment:
            line = "I am also open to full-time opportunities where I can grow with the team."
        elif {"part_time", "part-time"} & employment:
            line = "I am open to part-time opportunities where I can contribute consistently around my academic schedule."
        else:
            line = "I am flexible on format and would be happy to discuss what kind of contribution would be most useful."
        if earliest:
            line += f" My earliest start date is {earliest}."
        return line

    def _highlight_line(
        self,
        profile: dict[str, Any],
        resume_text: str,
        skills: list[Any],
        projects: list[dict[str, Any]],
    ) -> str:
        lower_resume = resume_text.lower()
        highlights = []
        if "cloudattack" in lower_resume:
            cloudattack = "I am the Co-Founder and Chief Product Officer of CloudAttack"
            if "thousand" in lower_resume:
                cloudattack += ", an EdTech startup that has helped thousands of learners"
            highlights.append(cloudattack + ".")
        leadership = profile.get("leadership") or []
        if leadership and not highlights:
            first = leadership[0]
            if isinstance(first, dict):
                title = first.get("title") or first.get("role") or "a leadership role"
                org = first.get("organization") or first.get("company") or ""
                highlights.append(f"I have also held {title}{f' at {org}' if org else ''}.")
        if "undergraduate research" in lower_resume or "research" in lower_resume:
            highlights.append("I am currently involved in undergraduate research.")
        if "microsoft" in lower_resume and ("certification" in lower_resume or "certified" in lower_resume):
            highlights.append("I also hold Microsoft certifications.")
        if projects:
            project = projects[0]
            name = project.get("name")
            if name:
                highlights.append(f"I have built projects like {name} that connect engineering, design, and real-world problem solving.")
        if not highlights:
            skill_line = ", ".join([str(s) for s in skills[:4]]) or "software development, cloud computing, AI, and product building"
            highlights.append(f"My background includes {skill_line}.")
        return " ".join(highlights[:3])

    def _project_line(self, projects: list[dict[str, Any]], skills: list[Any]) -> str:
        if not projects:
            return ""
        project = projects[0]
        name = project.get("name")
        if not name:
            return ""
        tech = ", ".join([str(x) for x in (project.get("tech_used") or skills[:2]) if x])
        if tech:
            return f" One relevant example is {name}, where I worked with {tech}."
        return f" One relevant example is {name}."

    def _company_interest(self, company: dict[str, Any], company_name: str) -> str:
        industry = company.get("industry")
        description = company.get("description") or company.get("mission")
        if industry:
            return f"the opportunity to contribute to a company building in {industry}."
        if description:
            return f"the opportunity to contribute to {str(description)[:160].rstrip()}."
        return f"the chance to contribute to what {company_name} is building."

    def _collect_links(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        personalization: dict[str, Any],
    ) -> list[dict[str, str]]:
        raw_links = {
            "portfolio": profile.get("portfolio_url") or (preferences.get("profile_links") or {}).get("portfolio"),
            "github": profile.get("github_url") or (preferences.get("profile_links") or {}).get("github"),
            "linkedin": profile.get("linkedin_url") or (preferences.get("profile_links") or {}).get("linkedin"),
        }
        for key, value in (preferences.get("profile_links") or {}).items():
            raw_links.setdefault(str(key), value)
        for link in personalization.get("suggested_links") or []:
            if isinstance(link, dict) and link.get("url"):
                raw_links.setdefault(str(link.get("type") or "link"), link.get("url"))
        return [
            {"type": self._format_link_type(str(key)), "url": self._normalize_url(str(value))}
            for key, value in raw_links.items()
            if value
        ][:4]

    def _link_line(self, links: list[dict[str, str]]) -> str:
        if not links:
            return ""
        lines = ["I have attached my resume for your reference. You can also review my work here:"]
        for link in links[:3]:
            lines.append(f"**{link['type']}**: {link['url']}")
        return "\n".join(lines) + "\n\n"

    def _compact_link_line(self, links: list[dict[str, str]]) -> str:
        return " | ".join([f"{link['type']}: {link['url']}" for link in links[:3]])

    def _normalize_url(self, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            return f"https://{value}"
        return value

    def _format_institution(self, institution: str) -> str:
        institution = institution.strip()
        if institution.lower().startswith("university of "):
            return f"the {institution}"
        return institution

    def _format_link_type(self, key: str) -> str:
        labels = {
            "github": "GitHub",
            "linkedin": "LinkedIn",
            "portfolio": "Portfolio",
            "devpost": "Devpost",
            "kaggle": "Kaggle",
            "leetcode": "LeetCode",
        }
        return labels.get(key.lower(), key.title())

    def _sanitize_first_person(self, text: str) -> str:
        replacements = [
            (r"\bthe user is qualified in\b", "I have experience in"),
            (r"\bthe user has experience in\b", "I have experience in"),
            (r"\bthe user's background\b", "my background"),
            (r"\bthe user's\b", "my"),
            (r"\bthe user\b", "I"),
            (r"\bthis candidate's\b", "my"),
            (r"\bthe candidate's\b", "my"),
            (r"\bthis candidate is\b", "I am"),
            (r"\bthe candidate is\b", "I am"),
            (r"\bthe candidate has\b", "I have"),
            (r"\bthe candidate can\b", "I can"),
            (r"\bthe candidate\b", "I"),
            (r"\bthe applicant's\b", "my"),
            (r"\bthe applicant is\b", "I am"),
            (r"\bthe applicant has\b", "I have"),
            (r"\bthe applicant\b", "I"),
        ]
        cleaned = text.strip()
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bI is\b", "I am", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bI has\b", "I have", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bI was qualified\b", "I am qualified", cleaned, flags=re.IGNORECASE)
        return cleaned
