"""AI email generation service with structured variants and subjects."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .ai_common import AIServiceError, OpenAIJsonClient, compact_json


class GeneratedEmailDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    company_id: str
    company_name: str
    outreach_type: str
    tone: str
    selected_variant: str = "medium"
    subject: str
    body: str
    variants: dict[str, str]
    subjects: list[dict[str, str]]
    recipient_email: str | None = None
    status: str = "pending_approval"
    generation_metadata: dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EmailWriterService:
    """Writes concise, human outreach emails from a personalization profile."""

    def __init__(self) -> None:
        self.ai = OpenAIJsonClient()

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
        fallback = self._deterministic_email(
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
            return fallback

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
                "Open directly with the candidate's interest or with a sharp hook, depending on the variant.",
                "Mention internship availability and whether the candidate is open to full-time or part-time work when preferences include it.",
                "Include the strongest relevant links from portfolio, GitHub, LinkedIn, or other profile links.",
                "Use Markdown-style bold sparingly for 1-3 skimmable labels or value points in the body, such as **Availability** or **Portfolio**.",
                "Do not sound AI-generated.",
                "Avoid generic template phrases.",
                "Do not overload with more than three proof points.",
                "No fabricated metrics.",
                "Keep short under 150 words, medium under 260 words, bold under 220 words.",
            ],
        }
        system = (
            "You are OfferHunterAI's Email Writer Agent. Return only valid JSON. "
            "Write human, concise, deeply personalized career outreach. "
            "Every draft must sound like the candidate wrote it personally in first person. "
            "Use natural plain text with light Markdown emphasis where useful."
        )
        user = (
            "Generate JSON with keys: selected_variant, subject, body, variants, subjects, generation_metadata. "
            "variants must include short, medium, bold_founder. subjects must include professional, startup_style, "
            "curiosity_based, role_focused objects with label and subject. Select medium by default. "
            "The medium variant should be a polished direct internship/outreach email. "
            "The short variant should start quickly and stay concise. "
            "The bold_founder variant should begin with a hook line that makes the reader want to keep reading. "
            f"Context:\n{compact_json(context)}"
        )
        try:
            data = await self.ai.create_json(system=system, user=user, temperature=0.55, max_tokens=2600)
            merged = {**fallback.model_dump(), **data}
            merged["id"] = fallback.id
            merged["user_id"] = user_id
            merged["company_id"] = str(company.get("id") or "")
            merged["company_name"] = company.get("name") or fallback.company_name
            merged["outreach_type"] = outreach_type or personalization.get("outreach_type") or fallback.outreach_type
            merged["tone"] = personalization.get("tone") or fallback.tone
            selected = merged.get("selected_variant") or "medium"
            variants = merged.get("variants") or fallback.variants
            variants = {key: self._sanitize_first_person(str(value)) for key, value in variants.items()}
            merged["variants"] = variants
            merged["body"] = self._sanitize_first_person(variants.get(selected) or merged.get("body") or fallback.body)
            if not merged.get("subject") and merged.get("subjects"):
                merged["subject"] = merged["subjects"][0].get("subject")
            return GeneratedEmailDraft.model_validate(merged)
        except (AIServiceError, ValueError, TypeError):
            return fallback

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
        skills = personalization.get("relevant_skills") or user_profile.get("skills") or []
        projects = personalization.get("relevant_projects") or user_profile.get("projects") or []
        links = self._collect_links(user_profile, preferences, personalization)
        greeting = f"Dear {company_name} Team,"
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
            "I hope you are doing well.\n\n"
            f"My name is {full_name}, and {education_line} I am reaching out to express my strong interest in a 3-month summer internship opportunity with {company_name}.\n\n"
            f"{availability_line} I would bring full commitment, energy, and ownership from day one. I am not looking to contribute only in a narrow technical capacity; I can help across engineering, product, research, and operations where useful.\n\n"
            f"{highlight_line} My strongest technical overlap is **{skill_line}**.{project_line}\n\n"
            f"What excites me most about {company_name} is {company_interest} I would love the chance to support your team this summer in any way that creates value.\n\n"
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
        variants = {
            "short": self._sanitize_first_person(short),
            "medium": self._sanitize_first_person(medium),
            "bold_founder": self._sanitize_first_person(bold),
        }
        subjects = [
            {"label": "Professional", "subject": f"Summer internship interest - {company_name}"},
            {"label": "Startup-style", "subject": f"Builder interested in helping {company_name} this summer"},
            {"label": "Curiosity-based", "subject": f"Could I support {company_name} this summer?"},
            {"label": "Role-focused", "subject": f"{role} internship interest - {skill_line.split(',')[0]} experience"},
        ]
        return GeneratedEmailDraft(
            user_id=user_id,
            company_id=str(company.get("id") or ""),
            company_name=company_name,
            outreach_type=outreach_type or personalization.get("outreach_type") or "cold_email",
            tone=personalization.get("tone") or "professional_concise",
            subject=subjects[0]["subject"],
            body=variants["medium"],
            variants=variants,
            subjects=subjects,
            recipient_email=recipient.get("email"),
            generation_metadata={
                "fit_score": personalization.get("fit_score"),
                "strategy": personalization.get("email_strategy") or {},
                "generated_without_openai": not self.ai.enabled,
            },
        )

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
