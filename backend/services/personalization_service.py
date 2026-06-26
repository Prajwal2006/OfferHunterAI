"""Personalization profile generation for company outreach."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .ai_common import AIServiceError, OpenAIJsonClient, compact_json, normalize_score


class PersonalizationProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    company_id: str
    fit_score: int = Field(ge=0, le=100)
    outreach_type: str
    tone: str
    company_alignment: list[str] = []
    relevant_projects: list[dict[str, Any]] = []
    relevant_skills: list[str] = []
    suggested_links: list[dict[str, str]] = []
    recommended_hooks: list[str] = []
    email_strategy: dict[str, Any] = {}
    key_points_to_mention: list[str] = []
    personalization_summary: str
    evidence: dict[str, Any] = {}
    generated_by: str = "openai"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PersonalizationService:
    """Combines profile, resume, company, job, and link signals into outreach strategy."""

    def __init__(self) -> None:
        self.ai = OpenAIJsonClient()

    async def generate_profile(
        self,
        *,
        user_id: str,
        company: dict[str, Any],
        user_profile: dict[str, Any] | None = None,
        preferences: dict[str, Any] | None = None,
        resume: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
        links_analysis: dict[str, Any] | None = None,
        use_ai: bool = True,
    ) -> PersonalizationProfile:
        context = {
            "company": company,
            "user_profile": user_profile or {},
            "preferences": preferences or {},
            "resume": self._resume_context(resume),
            "job": job or {},
            "links_analysis": links_analysis or self._analyze_links(user_profile or {}, preferences or {}),
        }
        fallback = self._deterministic_profile(user_id=user_id, context=context)
        fallback.generated_by = "deterministic"
        if not use_ai or not self.ai.enabled:
            return fallback

        system = (
            "You are OfferHunterAI's staff-level Personalization Agent. "
            "Return only valid JSON. Be specific, evidence-based, concise, and never invent unverifiable facts. "
            "Score fit based on explicit overlap between user strengths, company needs, job info, and preferences."
        )
        user = (
            "Generate a production outreach personalization profile with exactly these top-level keys: "
            "fit_score, outreach_type, tone, company_alignment, relevant_projects, relevant_skills, "
            "suggested_links, recommended_hooks, email_strategy, key_points_to_mention, "
            "personalization_summary, evidence.\n"
            "Use arrays of strings except relevant_projects and suggested_links may be objects. "
            "email_strategy should include opening_angle, proof_points, cta, avoid, variant_guidance.\n\n"
            f"Context:\n{compact_json(context)}"
        )
        try:
            data = await self.ai.create_json(
                system=system,
                user=user,
                temperature=0.25,
                max_tokens=2400,
                user_id=user_id,
                context_metadata={
                    "operation": "personalization_profile",
                    "company": company,
                    "user_profile": user_profile or {},
                    "preferences": preferences or {},
                    "resume": self._resume_context(resume),
                    "job": job or {},
                    "links_analysis": context["links_analysis"],
                },
            )
            merged = {**fallback.model_dump(), **data}
            merged["id"] = fallback.id
            merged["user_id"] = user_id
            merged["company_id"] = str(company.get("id") or "")
            merged["fit_score"] = normalize_score(merged.get("fit_score"), fallback.fit_score)
            merged["generated_by"] = "openai"
            return PersonalizationProfile.model_validate(merged)
        except (AIServiceError, ValueError, TypeError):
            return fallback

    def _resume_context(self, resume: dict[str, Any] | None) -> dict[str, Any]:
        if not resume:
            return {}
        text = resume.get("extracted_text") or resume.get("raw_text") or ""
        return {
            "resume_version_id": resume.get("id"),
            "skills": resume.get("extracted_skills") or [],
            "text_excerpt": text[:5000],
        }

    def _analyze_links(self, profile: dict[str, Any], preferences: dict[str, Any]) -> dict[str, Any]:
        links = {
            "github": profile.get("github_url") or (preferences.get("profile_links") or {}).get("github"),
            "linkedin": profile.get("linkedin_url") or (preferences.get("profile_links") or {}).get("linkedin"),
            "portfolio": profile.get("portfolio_url") or (preferences.get("profile_links") or {}).get("portfolio"),
        }
        other_links = profile.get("other_links") or []
        signals = []
        link_text = " ".join([str(v) for v in links.values() if v] + [str(v) for v in other_links]).lower()
        if "github" in link_text:
            signals.append("Public code footprint available")
        if any(term in link_text for term in ["kaggle", "ml", "ai", "openai", "huggingface"]):
            signals.append("AI/ML or data-science signal in public links")
        if any(term in link_text for term in ["devpost", "hackathon", "startup"]):
            signals.append("Builder/startup or hackathon signal")
        return {"links": links, "other_links": other_links, "signals": signals}

    def _deterministic_profile(self, *, user_id: str, context: dict[str, Any]) -> PersonalizationProfile:
        company = context["company"]
        profile = context["user_profile"]
        prefs = context["preferences"]
        job = context["job"]
        resume = context["resume"]

        company_tech = [str(x) for x in company.get("tech_stack") or []]
        user_skills = [str(x) for x in (profile.get("skills") or profile.get("tech_stack") or resume.get("skills") or [])]
        pref_tech = [str(x) for x in prefs.get("preferred_tech_stack") or []]
        job_requirements = [str(x) for x in job.get("requirements") or []]
        job_text = " ".join([job.get("title") or "", job.get("description") or "", " ".join(job_requirements)]).lower()
        company_text = " ".join(
            [
                company.get("name") or "",
                company.get("industry") or "",
                company.get("description") or "",
                company.get("mission") or "",
                " ".join(company_tech),
            ]
        ).lower()

        overlap = self._overlap(user_skills + pref_tech, company_tech + job_requirements + [job_text, company_text])
        projects = self._rank_projects(profile.get("projects") or [], overlap, company_text + " " + job_text)
        leadership = profile.get("leadership") or []
        awards = profile.get("awards") or []
        fit_score = 58 + min(24, len(overlap) * 5) + min(8, len(projects) * 3) + (5 if leadership else 0) + (3 if awards else 0)
        if company.get("hiring_status") in {"actively_hiring", "hiring"}:
            fit_score += 5
        if prefs.get("open_to_startups") and str(company.get("funding_stage", "")).lower() in {"seed", "series a", "yc", "pre-seed"}:
            fit_score += 5

        links = context["links_analysis"].get("links", {})
        suggested_links = [
            {"type": key, "url": value, "reason": f"Supports the outreach proof point around {key} presence"}
            for key, value in links.items()
            if value
        ][:3]
        role = job.get("title") or (prefs.get("preferred_roles") or ["engineering role"])[0]
        name = company.get("name", "the company")
        hooks = [
            f"Connect your {', '.join(overlap[:3]) or 'technical'} background to {name}'s work in {company.get('industry') or 'its market'}.",
            f"Reference {name}'s mission or product direction and keep the ask specific to {role}.",
        ]
        if projects:
            hooks.insert(0, f"Lead with {projects[0].get('name')} as the most relevant proof point.")

        return PersonalizationProfile(
            user_id=user_id,
            company_id=str(company.get("id") or ""),
            fit_score=normalize_score(fit_score),
            outreach_type="job_application" if job else ("founder_outreach" if self._is_startup(company) else "cold_email"),
            tone="professional_startup_friendly" if self._is_startup(company) else "professional_concise",
            company_alignment=[
                item
                for item in [
                    f"Industry alignment with {company.get('industry')}" if company.get("industry") else "",
                    f"Technical overlap: {', '.join(overlap[:6])}" if overlap else "",
                    f"Mission connection: {company.get('mission')[:140]}" if company.get("mission") else "",
                    "Startup ownership fit" if self._is_startup(company) and prefs.get("open_to_startups") else "",
                ]
                if item
            ],
            relevant_projects=projects[:4],
            relevant_skills=overlap[:10] or user_skills[:8],
            suggested_links=suggested_links,
            recommended_hooks=hooks,
            email_strategy={
                "opening_angle": hooks[0],
                "proof_points": [p.get("name") for p in projects[:2]] + overlap[:3],
                "cta": "Ask for a short conversation or guidance on the best hiring path.",
                "avoid": ["Long resume recap", "Generic admiration", "Too many links"],
                "variant_guidance": {
                    "short": "One hook, one proof point, one CTA.",
                    "medium": "Add role/company alignment and a project sentence.",
                    "bold": "Founder-facing value proposition with crisp ambition.",
                },
            },
            key_points_to_mention=[
                point
                for point in [
                    f"Relevant skills: {', '.join(overlap[:5])}" if overlap else "",
                    f"Project evidence: {projects[0].get('name')}" if projects else "",
                    f"Role target: {role}" if role else "",
                ]
                if point
            ],
            personalization_summary=(
                f"{name} is a strong outreach target because the user's background overlaps with "
                f"{', '.join(overlap[:5]) or 'the company needs'} and can be framed through concrete projects."
            ),
            evidence={"skill_overlap": overlap, "link_signals": context["links_analysis"].get("signals", [])},
        )

    def _overlap(self, user_terms: list[str], target_terms: list[str]) -> list[str]:
        haystack = " ".join(target_terms).lower()
        seen: set[str] = set()
        matches = []
        for term in user_terms:
            normalized = re.sub(r"\s+", " ", str(term).strip())
            if not normalized or normalized.lower() in seen:
                continue
            if normalized.lower() in haystack:
                seen.add(normalized.lower())
                matches.append(normalized)
        return matches

    def _rank_projects(self, projects: list[dict[str, Any]], overlap: list[str], target_text: str) -> list[dict[str, Any]]:
        ranked = []
        overlap_text = " ".join(overlap).lower()
        for project in projects:
            text = " ".join(
                [
                    str(project.get("name", "")),
                    str(project.get("description", "")),
                    " ".join([str(x) for x in project.get("tech_used") or []]),
                ]
            ).lower()
            score = sum(1 for term in overlap if term.lower() in text) + sum(1 for token in text.split() if token in target_text)
            if score > 0 or not ranked:
                ranked.append({**project, "relevance_reason": "Matches company or role technical signals", "score": score})
        return sorted(ranked, key=lambda p: p.get("score", 0), reverse=True)

    def _is_startup(self, company: dict[str, Any]) -> bool:
        stage = str(company.get("funding_stage") or "").lower()
        size = str(company.get("size") or "").lower()
        return any(x in stage for x in ["seed", "series", "yc", "pre-seed"]) or any(x in size for x in ["1-", "2-", "10-", "11-", "50"])
