"""Shared helpers for public applicant-tracking-system adapters."""

from __future__ import annotations

import re
import os
from typing import Any
from urllib.parse import urlparse

from ...company_sources.utils import (
    extract_domain_from_url,
    infer_culture_tags,
    infer_industry,
    infer_tech_stack,
    normalize_company,
    slugify_domain,
)


ENGINEERING_TERMS = {
    "engineer",
    "developer",
    "software",
    "backend",
    "frontend",
    "fullstack",
    "full-stack",
    "platform",
    "infrastructure",
    "devops",
    "sre",
    "data",
    "machine learning",
    "ml",
    "ai",
    "research",
    "security",
    "cloud",
}

DEFAULT_STARTUP_BOARDS = [
    "openai",
    "anthropic",
    "stripe",
    "airbnb",
    "databricks",
    "notion",
    "figma",
    "ramp",
    "rippling",
    "brex",
    "deel",
    "zapier",
    "linear",
    "vercel",
    "retool",
    "mercury",
    "scaleai",
    "cohere",
    "huggingface",
    "mistral",
    "perplexity",
    "cursor",
    "modal",
    "baseten",
    "togetherai",
    "replicate",
    "langchain",
    "pinecone",
    "weaviate",
    "qdrant",
    "sentry",
    "grafana",
    "docker",
    "hashicorp",
    "cloudflare",
    "sourcegraph",
    "render",
    "railway",
    "neon",
    "temporal",
    "tailscale",
]


def board_slugs_from_context(profile: dict[str, Any], preferences: dict[str, Any]) -> list[str]:
    """Build a high-recall list of ATS board slugs to probe."""
    def as_list(value: Any) -> list[Any]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [value]

    env_boards = [
        item.strip()
        for item in os.getenv("OFFERHUNTER_BOARD_SLUGS", "").split(",")
        if item.strip()
    ]
    configured = (
        as_list(preferences.get("company_board_slugs"))
        + as_list(preferences.get("target_companies"))
        + env_boards
    )
    excluded = {str(d).split(".")[0].lower() for d in preferences.get("_excluded_domains", [])}
    values = list(configured) + DEFAULT_STARTUP_BOARDS
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        slug = re.sub(r"[^a-z0-9-]", "", str(raw).lower().replace(" ", ""))
        if not slug or slug in seen or slug in excluded:
            continue
        seen.add(slug)
        result.append(slug)
    return result


def job_matches(job: dict[str, Any], queries: list[str], profile: dict[str, Any], preferences: dict[str, Any]) -> bool:
    """Return true when a job is relevant enough to include its company."""
    roles = preferences.get("preferred_roles") or profile.get("preferred_domains") or []
    skills = profile.get("skills", []) + profile.get("tech_stack", [])
    haystack = " ".join(
        str(v)
        for v in [
            job.get("title"),
            job.get("location"),
            job.get("department"),
            job.get("description"),
            job.get("content"),
            " ".join(job.get("tags", []) or []),
        ]
        if v
    ).lower()
    needles = [*queries[:10], *roles[:5], *skills[:8], *ENGINEERING_TERMS]
    return any(str(term).lower() in haystack for term in needles if term)


def job_is_remote(job: dict[str, Any]) -> bool:
    text = " ".join(str(v) for v in job.values() if isinstance(v, (str, int, float))).lower()
    return "remote" in text or "anywhere" in text


def domain_from_company_url(url: str, company_name: str) -> str:
    domain = extract_domain_from_url(url or "")
    if domain and not domain.endswith(("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com")):
        return domain
    return slugify_domain(company_name)


def source_url_domain(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc.removeprefix("www.")


def normalize_job_board_company(
    *,
    source: str,
    company_name: str,
    board_slug: str,
    jobs: list[dict[str, Any]],
    source_url: str,
    website_url: str = "",
    logo_url: str = "",
) -> dict[str, Any]:
    text = " ".join(
        str(v)
        for job in jobs
        for v in [job.get("title"), job.get("description"), job.get("content"), job.get("department")]
        if v
    )
    company = {
        "name": company_name or board_slug.replace("-", " ").title(),
        "domain": domain_from_company_url(website_url, company_name or board_slug),
        "description": f"Actively hiring via {source}; matched {len(jobs)} relevant open roles.",
        "industry": infer_industry(text),
        "tech_stack": infer_tech_stack(text),
        "hiring_status": "actively_hiring",
        "remote_friendly": any(job_is_remote(job) for job in jobs),
        "open_positions": jobs[:20],
        "culture_tags": list(dict.fromkeys(["startup", *infer_culture_tags(text)]))[:6],
        "source_url": source_url,
        "website_url": website_url,
        "logo_url": logo_url,
        "discovery_queries": [],
        "relevance_score": min(0.95, 0.55 + min(len(jobs), 8) * 0.04),
    }
    return normalize_company(company, source)
