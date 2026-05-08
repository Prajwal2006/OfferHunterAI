"""
CompanyScoringService — Intelligent multi-signal company ranking engine.

Extends the base weighted ranking in company_ranker.py with additional
intelligence signals:

  - semantic_similarity:   embedding cosine similarity between profile and company
  - growth_velocity:       inferred hiring/funding momentum
  - funding_recency:       freshness of latest funding round
  - ai_adoption_bonus:     bonus for AI-native companies (where relevant)
  - enrichment_confidence: trust score based on data completeness

All signals are combined with a transparent weighted formula, and a
ScoreBreakdown object is returned for full explainability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# ─── Score Weights ────────────────────────────────────────────────────────────
# Must sum to 1.0 (assertion below)

EXTENDED_WEIGHTS: dict[str, float] = {
    # Core signals (from company_ranker.py)
    "skills_match":        0.18,
    "interests_match":     0.12,
    "tech_stack_match":    0.12,
    "hiring_likelihood":   0.12,
    "location_match":      0.08,
    "compensation_match":  0.05,
    "visa_compatibility":  0.05,
    "resume_match":        0.03,
    "company_size_match":  0.04,
    # Extended signals (new in this service)
    "semantic_similarity": 0.10,
    "growth_velocity":     0.06,
    "funding_recency":     0.05,
}

assert abs(sum(EXTENDED_WEIGHTS.values()) - 1.0) < 1e-6, (
    f"EXTENDED_WEIGHTS must sum to 1.0, got {sum(EXTENDED_WEIGHTS.values())}"
)


# ─── Score Breakdown ──────────────────────────────────────────────────────────

@dataclass
class ScoreBreakdown:
    """
    Fully explainable per-dimension ranking for a single company.

    All raw signal fields are in [0.0, 1.0]. weighted_total is the final score.
    """
    # Core signals
    skills_match: float = 0.0
    interests_match: float = 0.0
    tech_stack_match: float = 0.0
    hiring_likelihood: float = 0.0
    location_match: float = 0.0
    compensation_match: float = 0.0
    visa_compatibility: float = 0.0
    resume_match: float = 0.0
    company_size_match: float = 0.0
    # Extended signals
    semantic_similarity: float = 0.0
    growth_velocity: float = 0.0
    funding_recency: float = 0.0

    # Derived
    weighted_total: float = 0.0
    confidence: float = 1.0          # how much data was available to compute score
    match_explanation: str = ""
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    signal_weights: dict[str, float] = field(default_factory=lambda: dict(EXTENDED_WEIGHTS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Signal Implementations ───────────────────────────────────────────────────

def _score_growth_velocity(company: dict[str, Any]) -> float:
    """
    Score growth momentum from enrichment signals.
    Returns 0.0–1.0.
    """
    signals: list[str] = company.get("growth_signals", []) or []
    score = 0.5  # neutral baseline

    boost_map = {
        "hypergrowth": 0.5,
        "rapid_hiring": 0.35,
        "recently_funded": 0.30,
        "actively_expanding": 0.20,
        "engineering_heavy_hiring": 0.15,
        "selective_hiring": 0.05,
    }
    for signal, boost in boost_map.items():
        if signal in signals:
            score = min(1.0, score + boost)

    return round(score, 3)


def _score_funding_recency(company: dict[str, Any]) -> float:
    """
    Score the recency / attractiveness of the funding stage.
    Recently-funded seed/Series A companies score highest; pre-IPO and
    very early pre-seed score slightly lower; public companies neutral.
    """
    stage = (company.get("funding_stage") or "").lower()
    if not stage:
        return 0.5  # unknown

    stage_scores = {
        "pre-seed": 0.55,
        "seed": 0.80,
        "series a": 0.90,
        "series b": 0.85,
        "series c": 0.75,
        "series d": 0.65,
        "series e": 0.55,
        "yc-backed": 0.82,
        "yc s": 0.80,
        "yc w": 0.80,
        "ipo": 0.60,
        "public": 0.50,
    }
    for key, val in stage_scores.items():
        if key in stage:
            return val
    return 0.5


def _score_data_confidence(company: dict[str, Any]) -> float:
    """Estimate how complete/trustworthy the company data is."""
    fields_present = sum([
        bool(company.get("description")),
        bool(company.get("tech_stack")),
        bool(company.get("industry")),
        bool(company.get("headquarters")),
        bool(company.get("funding_stage")),
        bool(company.get("size")),
        bool(company.get("open_positions")),
    ])
    return round(fields_present / 7.0, 2)


# ─── Service ──────────────────────────────────────────────────────────────────

class CompanyScoringService:
    """
    Compute extended multi-signal scores for a list of companies.

    This service is designed to be called AFTER basic ranking so that it can
    layer in enrichment-dependent signals (growth velocity, funding recency,
    semantic similarity) that may not be available at initial discovery time.
    """

    def score_companies(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        semantic_scores: dict[str, float] | None = None,
        base_rankings: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Re-score and re-rank companies using the extended signal set.

        Args:
            companies:       List of (possibly enriched) company dicts.
            profile:         Parsed user profile.
            preferences:     User job preferences.
            semantic_scores: Optional map of company domain → semantic similarity [0-1].
            base_rankings:   Optional map of company domain → existing ranking dict
                             from CompanyRankerService (used to inherit base signals).

        Returns:
            Companies list sorted by extended score descending.
            Each company gains an "extended_ranking" key with full ScoreBreakdown.
        """
        semantic_scores = semantic_scores or {}
        base_rankings = base_rankings or {}
        scored: list[dict[str, Any]] = []

        for company in companies:
            domain = (company.get("domain") or "").lower()
            base = base_rankings.get(domain, {})

            # ── Inherit base signals or recompute neutral defaults ──────────
            skills_match = float(base.get("skills_match", 0.5))
            interests_match = float(base.get("interests_match", 0.5))
            tech_stack_match = float(base.get("tech_stack_match", 0.5))
            hiring_likelihood = float(base.get("hiring_likelihood", 0.5))
            location_match = float(base.get("location_match", 0.5))
            compensation_match = float(base.get("compensation_match", 0.5))
            visa_compatibility = float(base.get("visa_compatibility", 0.5))
            resume_match = float(base.get("resume_match", 0.5))
            company_size_match = float(base.get("company_size_match", 0.5))

            # ── Extended signals ─────────────────────────────────────────────
            semantic_similarity = float(semantic_scores.get(domain, 0.5))
            growth_velocity = _score_growth_velocity(company)
            funding_recency = _score_funding_recency(company)
            confidence = _score_data_confidence(company)

            # ── Weighted total ────────────────────────────────────────────────
            weighted_total = (
                EXTENDED_WEIGHTS["skills_match"] * skills_match
                + EXTENDED_WEIGHTS["interests_match"] * interests_match
                + EXTENDED_WEIGHTS["tech_stack_match"] * tech_stack_match
                + EXTENDED_WEIGHTS["hiring_likelihood"] * hiring_likelihood
                + EXTENDED_WEIGHTS["location_match"] * location_match
                + EXTENDED_WEIGHTS["compensation_match"] * compensation_match
                + EXTENDED_WEIGHTS["visa_compatibility"] * visa_compatibility
                + EXTENDED_WEIGHTS["resume_match"] * resume_match
                + EXTENDED_WEIGHTS["company_size_match"] * company_size_match
                + EXTENDED_WEIGHTS["semantic_similarity"] * semantic_similarity
                + EXTENDED_WEIGHTS["growth_velocity"] * growth_velocity
                + EXTENDED_WEIGHTS["funding_recency"] * funding_recency
            )

            # ── Build breakdown ───────────────────────────────────────────────
            breakdown = ScoreBreakdown(
                skills_match=round(skills_match, 3),
                interests_match=round(interests_match, 3),
                tech_stack_match=round(tech_stack_match, 3),
                hiring_likelihood=round(hiring_likelihood, 3),
                location_match=round(location_match, 3),
                compensation_match=round(compensation_match, 3),
                visa_compatibility=round(visa_compatibility, 3),
                resume_match=round(resume_match, 3),
                company_size_match=round(company_size_match, 3),
                semantic_similarity=round(semantic_similarity, 3),
                growth_velocity=round(growth_velocity, 3),
                funding_recency=round(funding_recency, 3),
                weighted_total=round(weighted_total, 3),
                confidence=round(confidence, 2),
                signal_weights=dict(EXTENDED_WEIGHTS),
            )

            # ── Strengths / gaps ──────────────────────────────────────────────
            if skills_match >= 0.65:
                breakdown.strengths.append("Strong tech stack alignment")
            if semantic_similarity >= 0.70:
                breakdown.strengths.append("High semantic profile match")
            if hiring_likelihood >= 0.80:
                breakdown.strengths.append("Actively hiring")
            if location_match >= 0.90:
                breakdown.strengths.append("Location / remote match")
            if visa_compatibility >= 0.90:
                breakdown.strengths.append("Likely sponsors visas")
            if growth_velocity >= 0.75:
                breakdown.strengths.append("High growth momentum")
            if funding_recency >= 0.80:
                breakdown.strengths.append("Recently or well-funded")
            if company.get("ai_adoption"):
                breakdown.strengths.append("AI-native technology culture")
            if company.get("github_stars", 0) > 500:
                breakdown.strengths.append("Strong developer mindshare (GitHub)")

            if skills_match < 0.30:
                breakdown.gaps.append("Limited tech stack overlap")
                breakdown.suggestions.append("Highlight transferable skills in cover letter")
            if visa_compatibility < 0.50:
                breakdown.gaps.append("Visa sponsorship uncertain")
                breakdown.suggestions.append("Confirm sponsorship policy before applying")
            if location_match < 0.40:
                breakdown.gaps.append("Location mismatch")
                breakdown.suggestions.append("Check remote options or discuss relocation")
            if semantic_similarity < 0.30:
                breakdown.gaps.append("Profile-company semantic fit is low")
                breakdown.suggestions.append("Tailor your resume to use the company's language")

            company["extended_ranking"] = breakdown.to_dict()
            company["relevance_score"] = round(weighted_total, 3)
            scored.append(company)

        scored.sort(key=lambda c: c["extended_ranking"]["weighted_total"], reverse=True)
        return scored
