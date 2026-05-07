"""
CompanyRankerService — AI-powered weighted scoring to rank companies for a user.

Produces a detailed ranking with per-dimension scores, explanation, strengths,
gaps, and improvement suggestions for each company.

The ranker now integrates with EmbeddingService to add a semantic similarity
signal that captures profile↔company fit beyond keyword overlap.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

# Lazy import of EmbeddingService to avoid circular imports
_embedding_service_instance = None


def _get_embedding_service():
    global _embedding_service_instance
    if _embedding_service_instance is None:
        try:
            from .embedding_service import EmbeddingService
        except ImportError:
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).resolve().parent.parent))
            from backend.services.embedding_service import EmbeddingService
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance


# ─── Scoring Weights ──────────────────────────────────────────────────────────
# semantic_similarity slot replaces a portion of skills_match weight

WEIGHTS = {
    "skills_match":        0.18,
    "interests_match":     0.13,
    "tech_stack_match":    0.13,
    "hiring_likelihood":   0.15,
    "location_match":      0.10,
    "compensation_match":  0.06,
    "visa_compatibility":  0.07,
    "resume_match":        0.03,
    "company_size_match":  0.05,
    "semantic_similarity": 0.10,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6, "Weights must sum to 1.0"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _list_overlap_score(list_a: list[str], list_b: list[str]) -> float:
    """Score based on set overlap. Returns 0.0–1.0."""
    if not list_a or not list_b:
        return 0.5  # neutral when data is missing
    a = set(s.lower() for s in list_a)
    b = set(s.lower() for s in list_b)
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _score_visa(company: dict[str, Any], prefs: dict[str, Any]) -> float:
    needs_sponsorship = prefs.get("sponsorship_required", False)
    company_sponsors = company.get("sponsorship_available")
    if not needs_sponsorship:
        return 1.0
    if company_sponsors is True:
        return 1.0
    if company_sponsors is False:
        return 0.1
    return 0.5  # unknown


def _score_location(company: dict[str, Any], prefs: dict[str, Any]) -> float:
    preferred_locations = [loc.lower() for loc in prefs.get("preferred_locations", [])]
    work_mode_pref = (prefs.get("work_mode") or "flexible").lower()
    company_remote = company.get("remote_friendly")
    company_hq = (company.get("headquarters") or "").lower()
    open_to_relocation = prefs.get("open_to_relocation", True)

    # Remote preference matches remote company
    if work_mode_pref in ("remote", "flexible") and company_remote:
        return 1.0

    if not preferred_locations:
        return 0.7  # neutral

    for loc in preferred_locations:
        if loc in company_hq:
            return 1.0

    if open_to_relocation:
        return 0.6

    return 0.3


def _score_company_size(company: dict[str, Any], prefs: dict[str, Any]) -> float:
    size_prefs = prefs.get("company_size_pref", [])
    company_size = company.get("size", "")
    if not company_size:
        return 0.7

    if not size_prefs:
        size_lower = company_size.lower()
        if any(x in size_lower for x in ["<50", "1-10", "10-50", "11-50", "seed", "pre-seed"]):
            return 1.0
        if any(x in size_lower for x in ["50-200", "51-200", "small"]):
            return 0.9
        if any(x in size_lower for x in ["200-1000", "201-1000", "mid"]):
            return 0.7
        if any(x in size_lower for x in ["1000-5000", "1001-5000", "large"]):
            return 0.45
        if "5000" in size_lower or "enterprise" in size_lower:
            return 0.3
        return 0.7

    size_lower = company_size.lower()
    for pref in size_prefs:
        pref_lower = pref.lower()
        if "startup" in pref_lower and any(x in size_lower for x in ["<50", "10-50", "50"]):
            return 1.0
        if "small" in pref_lower and "50" in size_lower:
            return 1.0
        if "mid" in pref_lower and any(x in size_lower for x in ["200", "500", "1000"]):
            return 1.0
        if "large" in pref_lower and any(x in size_lower for x in ["1000", "5000"]):
            return 1.0
        if "enterprise" in pref_lower and "5000" in size_lower:
            return 1.0

    return 0.4


def _score_hiring_likelihood(company: dict[str, Any]) -> float:
    status = company.get("hiring_status", "unknown")
    mapping = {
        "actively_hiring": 1.0,
        "hiring": 0.8,
        "unknown": 0.5,
        "not_hiring": 0.1,
    }
    return mapping.get(status, 0.5)


# ─── Service ──────────────────────────────────────────────────────────────────

class CompanyRankerService:
    """
    Ranks a list of companies for a given user profile and preferences.
    Optionally enriches each ranking with an AI-generated explanation.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def rank(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        enrich_with_ai: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Score and rank companies. Returns list sorted by match_score descending.
        Each company gains a `ranking` key with scores + explanation.

        Now includes semantic_similarity computed via OpenAI embeddings when
        an API key is available (gracefully falls back to 0.5 when not).
        """
        if not companies:
            return []

        user_skills = profile.get("skills", []) + profile.get("tech_stack", [])
        user_domains = profile.get("preferred_domains", [])
        preferred_roles = preferences.get("preferred_roles", [])
        preferred_tech = preferences.get("preferred_tech_stack", []) or profile.get("tech_stack", [])
        industries_of_interest = preferences.get("industries_of_interest", [])

        # ── Compute profile embedding once for all companies ──────────────────
        semantic_scores: dict[str, float] = {}
        try:
            emb_svc = _get_embedding_service()
            profile_emb = await emb_svc.create_profile_embedding(profile, preferences)
            if any(profile_emb):
                # Batch company text → embeddings concurrently
                company_texts = [emb_svc._company_text(c) for c in companies]
                company_embs = await emb_svc.create_batch_embeddings(company_texts)
                for company, c_emb in zip(companies, company_embs):
                    domain = (company.get("domain") or "").lower()
                    semantic_scores[domain] = emb_svc.cosine_similarity(profile_emb, c_emb)
        except Exception:
            pass  # Semantic scoring is best-effort

        ranked = []
        for company in companies:
            skills_match = _list_overlap_score(user_skills, company.get("tech_stack", []))
            tech_stack_match = _list_overlap_score(preferred_tech, company.get("tech_stack", []))

            # Interests: match preferred roles + domains against company industry + culture
            interests_targets = list(set(preferred_roles + user_domains + industries_of_interest))
            interests_sources = [
                company.get("industry", ""),
                *company.get("culture_tags", []),
            ]
            interests_match = _list_overlap_score(interests_targets, interests_sources) if interests_targets else 0.6

            hiring_likelihood = _score_hiring_likelihood(company)
            location_match = _score_location(company, preferences)
            visa_compatibility = _score_visa(company, preferences)
            company_size_match = _score_company_size(company, preferences)

            # Compensation: rough heuristic based on company size/stage
            salary_min = preferences.get("salary_min") or 0
            salary_max = preferences.get("salary_max") or 999999
            compensation_match = self._score_compensation(company, salary_min, salary_max)

            # Resume match: keyword overlap between resume keywords and company description
            resume_keywords = profile.get("keywords", [])
            company_text_tokens = (
                (company.get("description") or "").lower().split()
                + (company.get("industry") or "").lower().split()
                + [t.lower() for t in company.get("culture_tags", [])]
            )
            resume_match = _list_overlap_score(resume_keywords, company_text_tokens)

            # Semantic similarity from embeddings (0.5 neutral when unavailable)
            domain = (company.get("domain") or "").lower()
            semantic_similarity = semantic_scores.get(domain, 0.5)

            # Weighted final score
            match_score = (
                WEIGHTS["skills_match"] * skills_match
                + WEIGHTS["interests_match"] * interests_match
                + WEIGHTS["tech_stack_match"] * tech_stack_match
                + WEIGHTS["hiring_likelihood"] * hiring_likelihood
                + WEIGHTS["location_match"] * location_match
                + WEIGHTS["compensation_match"] * compensation_match
                + WEIGHTS["visa_compatibility"] * visa_compatibility
                + WEIGHTS["resume_match"] * resume_match
                + WEIGHTS["company_size_match"] * company_size_match
                + WEIGHTS["semantic_similarity"] * semantic_similarity
            )

            ranking = {
                "match_score": round(match_score, 3),
                "resume_match": round(resume_match, 3),
                "skills_match": round(skills_match, 3),
                "interests_match": round(interests_match, 3),
                "location_match": round(location_match, 3),
                "compensation_match": round(compensation_match, 3),
                "tech_stack_match": round(tech_stack_match, 3),
                "visa_compatibility": round(visa_compatibility, 3),
                "hiring_likelihood": round(hiring_likelihood, 3),
                "company_size_match": round(company_size_match, 3),
                "semantic_similarity": round(semantic_similarity, 3),
                "match_explanation": "",
                "strengths": [],
                "gaps": [],
                "suggestions": [],
                "signal_source": "embedding+keywords" if any(semantic_scores.values()) else "keywords",
            }

            # Build human-readable strengths and gaps
            if skills_match >= 0.6:
                ranking["strengths"].append("Strong tech stack alignment")
            if semantic_similarity >= 0.70:
                ranking["strengths"].append("High semantic profile match")
            if hiring_likelihood >= 0.8:
                ranking["strengths"].append("Actively hiring")
            if location_match >= 0.9:
                ranking["strengths"].append("Location match")
            if visa_compatibility >= 0.9:
                ranking["strengths"].append("Likely sponsors visas")
            if interests_match >= 0.6:
                ranking["strengths"].append("Industry/domain match")
            if company_size_match >= 0.85:
                ranking["strengths"].append("Smaller-company opportunity match")

            if skills_match < 0.3:
                ranking["gaps"].append("Limited tech stack overlap")
                ranking["suggestions"].append("Highlight transferable skills in your application")
            if visa_compatibility < 0.5:
                ranking["gaps"].append("Visa sponsorship uncertain")
                ranking["suggestions"].append("Confirm sponsorship policy before applying")
            if location_match < 0.4:
                ranking["gaps"].append("Location mismatch")
                ranking["suggestions"].append("Check remote options or discuss relocation")

            company["relevance_score"] = round(match_score, 3)
            company["ranking"] = ranking
            ranked.append(company)

        ranked.sort(key=lambda c: c["ranking"]["match_score"], reverse=True)

        # Drop companies that are clearly irrelevant to the candidate.
        # Only prune when there are more results than needed, so we don't
        # accidentally return an empty list when discovery is sparse.
        has_industry_prefs = bool(
            preferences.get("preferred_roles")
            or preferences.get("industries_of_interest")
            or profile.get("preferred_domains")
        )
        if has_industry_prefs and len(ranked) > 5:
            ranked = [
                c for c in ranked
                if not (
                    c["ranking"]["interests_match"] < 0.05
                    and c["ranking"]["match_score"] < 0.45
                )
            ]

        # Enrich top 15 with AI explanations (batch for efficiency)
        if enrich_with_ai and self._api_key:
            top = ranked[:15]
            try:
                await self._enrich_with_ai(top, profile, preferences)
            except Exception:
                pass

        return ranked

    @staticmethod
    def _score_compensation(
        company: dict[str, Any], salary_min: int, salary_max: int
    ) -> float:
        """Rough compensation score based on company stage/size."""
        stage = (company.get("funding_stage") or "").lower()
        size = (company.get("size") or "").lower()

        # Estimate market range
        if any(x in stage for x in ["public", "series d", "series e", "series f"]):
            market_min, market_max = 150000, 400000
        elif any(x in stage for x in ["series c", "series b"]):
            market_min, market_max = 130000, 280000
        elif any(x in stage for x in ["series a", "seed"]):
            market_min, market_max = 100000, 200000
        elif "yc" in stage:
            market_min, market_max = 100000, 180000
        elif "5000" in size:
            market_min, market_max = 140000, 350000
        else:
            market_min, market_max = 100000, 200000

        if salary_max == 999999 or salary_max == 0:
            return 0.7  # no preference, neutral

        # Overlap between user range and market range
        overlap_start = max(salary_min, market_min)
        overlap_end = min(salary_max, market_max)
        if overlap_start >= overlap_end:
            return 0.2

        user_range = max(salary_max - salary_min, 1)
        overlap = overlap_end - overlap_start
        return min(overlap / user_range, 1.0)

    async def _enrich_with_ai(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> None:
        """
        Generate AI match explanations for each company in a single batch call.
        Mutates companies in place.
        """
        profile_summary = (
            f"Skills: {', '.join(profile.get('skills', [])[:8])}\n"
            f"Tech stack: {', '.join(profile.get('tech_stack', [])[:6])}\n"
            f"Target roles: {', '.join(preferences.get('preferred_roles', []) or profile.get('preferred_domains', []))}\n"
            f"Work mode: {preferences.get('work_mode', 'flexible')}"
        )

        company_list = "\n".join(
            f"{i+1}. {c['name']} ({c.get('industry', '')}) — {c.get('description', '')[:100]}"
            for i, c in enumerate(companies)
        )

        prompt = f"""For each company below, write a 1-2 sentence explanation of why it matches this candidate.

Candidate:
{profile_summary}

Companies:
{company_list}

Return a JSON object where keys are company names and values are explanation strings."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 2048,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            explanations: dict[str, str] = json.loads(data["choices"][0]["message"]["content"])

        for company in companies:
            name = company.get("name", "")
            if name in explanations:
                company["ranking"]["match_explanation"] = explanations[name]
