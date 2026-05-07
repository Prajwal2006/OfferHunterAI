"""
Shared utilities for company discovery sources.

Provides normalization, inference, and URL helpers used across all sources.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


# ─── HTTP Headers ─────────────────────────────────────────────────────────────

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "OfferHunterAI/1.0 (job-discovery-bot; contact: support@offerhunterai.com)",
    "Accept": "application/json",
}


# ─── URL Helpers ──────────────────────────────────────────────────────────────

def slugify_domain(company_name: str) -> str:
    """Convert company name to a guessed .com domain slug."""
    slug = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
    return f"{slug}.com"


def extract_domain_from_url(url: str) -> str:
    """Extract the bare domain (no www) from a URL string."""
    match = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", url or "")
    return match.group(1) if match else ""


def normalize_url(url: str) -> str:
    """Ensure a URL has an https:// scheme."""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


# ─── Company Normalization ────────────────────────────────────────────────────

def normalize_company(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Ensure a company dict has all expected keys with safe defaults.

    All source connectors must return dicts passing through this function.
    """
    return {
        "name": raw.get("name", ""),
        "domain": raw.get("domain") or slugify_domain(raw.get("name", "unknown")),
        "description": raw.get("description", ""),
        "mission": raw.get("mission", ""),
        "industry": raw.get("industry", ""),
        "size": raw.get("size", ""),
        "tech_stack": raw.get("tech_stack") or [],
        "funding_stage": raw.get("funding_stage", ""),
        "founded_year": raw.get("founded_year"),
        "headquarters": raw.get("headquarters", ""),
        "website_url": raw.get("website_url", ""),
        "linkedin_url": raw.get("linkedin_url", ""),
        "logo_url": raw.get("logo_url", ""),
        "hiring_status": raw.get("hiring_status", "unknown"),
        "remote_friendly": raw.get("remote_friendly"),
        "sponsorship_available": raw.get("sponsorship_available"),
        "open_positions": raw.get("open_positions") or [],
        "culture_tags": raw.get("culture_tags") or [],
        "source": source,
        "source_url": raw.get("source_url", ""),
        "relevance_score": float(raw.get("relevance_score", 0.5) or 0.5),
        # Discovery metadata
        "discovery_queries": raw.get("discovery_queries") or [],
        "enrichment_version": raw.get("enrichment_version", 0),
    }


def startup_priority_score(company: dict[str, Any]) -> tuple[float, float]:
    """
    Compute a priority score that biases toward startups and known hiring sources.

    Returns a tuple (structural_score, relevance_score) for multi-key sorting.
    """
    size = (company.get("size") or "").lower()
    stage = (company.get("funding_stage") or "").lower()
    source = (company.get("source") or "").lower()

    score = 0.0
    if any(t in size for t in ["<50", "1-10", "10-50", "11-50", "50-200", "51-200", "small"]):
        score += 1.2
    elif any(t in size for t in ["200-1000", "201-1000", "mid"]):
        score += 0.6
    elif any(t in size for t in ["1000", "5000", "enterprise"]):
        score += 0.1

    if any(t in stage for t in ["pre-seed", "seed", "series a", "yc", "series b"]):
        score += 0.8

    if source in {"wellfound", "workatastartup", "hackernews"}:
        score += 0.5

    return (score, float(company.get("relevance_score") or 0.5))


# ─── Text-Based Inference Helpers ─────────────────────────────────────────────

def infer_industry(text: str) -> str:
    """Infer primary industry from free-form text."""
    lowered = text.lower()
    industry_map: dict[str, list[str]] = {
        "AI / ML": ["ai", "machine learning", "llm", "foundation model", "agentic", "generative ai"],
        "Fintech": ["fintech", "payments", "banking", "lending", "invoice", "financial"],
        "Healthcare / Biotech": ["healthcare", "biotech", "clinical", "medical", "drug", "pharma"],
        "Developer Tools": ["developer", "devtool", "api", "sdk", "observability", "devops", "ci/cd"],
        "Cybersecurity": ["security", "identity", "compliance", "fraud", "threat", "zero trust"],
        "Enterprise SaaS": ["saas", "workflow", "crm", "sales", "erp", "operations"],
        "Robotics / Hardware": ["robotics", "drone", "autonomous", "hardware", "embedded"],
        "Data / Analytics": ["data platform", "analytics", "warehouse", "etl", "bi"],
        "Edtech": ["education", "learning", "edtech", "tutoring", "upskilling"],
        "Climate / Sustainability": ["climate", "carbon", "clean energy", "sustainability", "green"],
    }
    for industry, keywords in industry_map.items():
        if any(kw in lowered for kw in keywords):
            return industry
    return ""


def infer_company_size(text: str) -> str:
    """Infer company size category from text."""
    lowered = text.lower()
    for pattern in [r"(\d{1,4})\+? employees", r"team of (\d{1,4})"]:
        m = re.search(pattern, lowered)
        if m:
            count = int(m.group(1))
            if count < 50:
                return "Startup (< 50)"
            if count < 200:
                return "Small (50-200)"
            if count < 1000:
                return "Mid-size (200-1000)"
            if count < 5000:
                return "Large (1000-5000)"
            return "Enterprise (5000+)"
    if any(t in lowered for t in ["seed stage", "early-stage", "founding team", "series a"]):
        return "Startup (< 50)"
    return ""


def infer_tech_stack(text: str) -> list[str]:
    """Extract technology mentions from text."""
    lowered = text.lower()
    tech_keywords: dict[str, list[str]] = {
        "Python": ["python"],
        "TypeScript": ["typescript"],
        "JavaScript": ["javascript"],
        "React": ["react"],
        "Next.js": ["next.js", "nextjs"],
        "Node.js": ["node.js", "nodejs"],
        "Go": [" golang", " go ", "go services"],
        "Rust": ["rust"],
        "Java": ["java"],
        "Scala": ["scala"],
        "C++": ["c++"],
        "Kubernetes": ["kubernetes", "k8s"],
        "AWS": ["aws", "amazon web services"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure"],
        "Postgres": ["postgres", "postgresql"],
        "Redis": ["redis"],
        "PyTorch": ["pytorch"],
        "TensorFlow": ["tensorflow"],
        "dbt": ["dbt"],
        "Kafka": ["kafka"],
    }
    found = [tech for tech, patterns in tech_keywords.items()
             if any(p in lowered for p in patterns)]
    return found[:10]


def infer_funding_stage(text: str) -> str:
    """Extract funding stage from free text."""
    lowered = text.lower()
    for stage in ["pre-seed", "seed", "series a", "series b", "series c", "series d", "series e", "ipo", "public"]:
        if stage in lowered:
            return stage.title()
    if "y combinator" in lowered or re.search(r"\b[wsf]\d{2}\b", lowered):
        return "YC-backed"
    return ""


def infer_headquarters(text: str) -> str:
    """Extract headquarters location from text."""
    m = re.search(
        r"(?:based in|headquartered in|located in|offices? in)\s+([A-Z][A-Za-z .,-]{3,60})",
        text,
    )
    if m:
        return m.group(1).strip()
    return ""


def infer_culture_tags(text: str) -> list[str]:
    """Extract culture signals from text."""
    lowered = text.lower()
    tag_map: dict[str, list[str]] = {
        "remote": ["remote", "distributed", "work from anywhere"],
        "startup": ["early-stage", "founding", "startup"],
        "fast-paced": ["fast-paced", "move fast", "high velocity"],
        "mission-driven": ["mission-driven", "purpose", "impact"],
        "ownership": ["ownership", "high agency", "autonomy"],
        "research": ["research", "experimentation", "r&d"],
        "diversity": ["diversity", "inclusion", "dei"],
        "open-source": ["open source", "open-source", "oss"],
    }
    return [tag for tag, kws in tag_map.items() if any(kw in lowered for kw in kws)][:6]
