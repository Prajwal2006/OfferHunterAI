"""Shared helpers for public applicant-tracking-system adapters."""

from __future__ import annotations

import asyncio
import re
import os
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from models.work_mode import normalize_company_work_mode, normalize_job_work_mode

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

# High-recall set of real public ATS board slugs (Greenhouse / Lever / Ashby /
# Workable). Each ATS adapter probes this same superset; slugs that do not exist
# on a given ATS simply 404 and are skipped. The list is intentionally weighted
# toward startups, scale-ups, and niche companies — i.e. employers whose roles
# rarely get promoted on LinkedIn/Indeed but are openly posted on their own
# applicant-tracking boards ("jobs that are not that publicized").
#
# Extend at runtime without code changes via the OFFERHUNTER_BOARD_SLUGS env var.
DEFAULT_STARTUP_BOARDS = [
    # ── AI / ML labs & infrastructure ─────────────────────────────────────────
    "openai", "anthropic", "cohere", "huggingface", "mistral", "perplexityai",
    "perplexity", "scaleai", "adept", "character", "runwayml", "elevenlabs",
    "suno", "contextualai", "writer", "glean", "harvey", "sierra", "cresta",
    "togetherai", "together", "fireworksai", "baseten", "modal", "replicate",
    "runpod", "anyscale", "lambdalabs", "weightsandbiases", "wandb", "comet",
    "deepgram", "assemblyai", "pinecone", "weaviate", "qdrant", "chroma",
    "llamaindex", "langchain", "unstructured", "nomic", "imbue", "essentialai",
    # ── Developer tools / platform ────────────────────────────────────────────
    "vercel", "netlify", "render", "railway", "fly", "supabase", "planetscale",
    "neon", "cockroachlabs", "temporal", "inngest", "trigger", "sourcegraph",
    "sentry", "grafana", "launchdarkly", "postman", "hashicorp", "docker",
    "gitpod", "retool", "linear", "raycast", "warp", "astral", "turso", "clerk",
    "workos", "convex", "resend", "knock", "liveblocks", "mintlify", "stytch",
    "tigerbeetle", "deno", "bun", "ngrok", "depot", "speakeasy",
    # ── Data / analytics ──────────────────────────────────────────────────────
    "databricks", "confluent", "fivetran", "airbyte", "dbtlabs", "hex",
    "dagster", "prefect", "mage", "motherduck", "clickhouse", "starburst",
    "tecton", "hightouch", "census", "rudderstack", "amplitude", "mixpanel",
    "metabase", "preset", "monte-carlo", "cube",
    # ── Fintech ───────────────────────────────────────────────────────────────
    "stripe", "ramp", "brex", "mercury", "plaid", "deel", "rippling", "gusto",
    "checkr", "modern-treasury", "moderntreasury", "unit", "lithic", "increase",
    "column", "marqeta", "alloy", "pomelo", "alpaca", "wealthfront", "betterment",
    "chime", "affirm", "tabby", "tradeio",
    # ── Security ──────────────────────────────────────────────────────────────
    "tailscale", "1password", "vanta", "drata", "snyk", "wiz", "abnormal",
    "huntress", "semgrep", "doppler", "infisical", "teleport", "oso",
    # ── Productivity / SaaS / vertical ────────────────────────────────────────
    "notion", "figma", "canva", "miro", "loom", "airtable", "asana", "webflow",
    "calendly", "zapier", "gong", "pylon", "ashby", "rippling-eng", "front",
    "vanta-eng", "instabase", "ironclad", "ramp-eng", "applied-intuition",
    "appliedintuition", "anduril", "shield-ai", "saronic", "ramp-jobs",
    # ── Health / bio / climate / hardware ─────────────────────────────────────
    "tempus", "color", "devoted-health", "cityblock", "commure", "openevidence",
    "watershed", "crusoe", "form-energy", "formenergy", "kodiak", "zipline",
    "physicsx", "pano", "verkada", "samsara", "rivos", "groq", "etched",
    "celestial", "cerebras", "sambanova",
]


async def gather_within_budget(
    factories: list[Callable[[], Awaitable[Any]]],
    budget_seconds: float,
) -> list[Any]:
    """Run many coroutines and return whatever finished within the time budget.

    The orchestrator wraps each source in a hard ``asyncio.wait_for`` that cancels
    the whole ``search`` coroutine on timeout — discarding every result. When we
    probe 150+ ATS boards, a slow tail of a handful of boards could otherwise nuke
    all the matches that already came back. This keeps an internal deadline safely
    under the source timeout, cancels stragglers, and returns the partial results.
    """
    tasks = [asyncio.ensure_future(factory()) for factory in factories]
    if not tasks:
        return []
    done, pending = await asyncio.wait(tasks, timeout=budget_seconds)
    for task in pending:
        task.cancel()
    results: list[Any] = []
    for task in done:
        try:
            results.append(task.result())
        except Exception:
            continue
    return results


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
    normalized_jobs = [normalize_job_work_mode(job, source=source) for job in jobs]
    text = " ".join(
        str(v)
        for job in normalized_jobs
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
        "remote_friendly": any(job.get("work_mode") == "remote" for job in normalized_jobs) or any(job_is_remote(job) for job in normalized_jobs),
        "open_positions": normalized_jobs[:20],
        "culture_tags": list(dict.fromkeys(["startup", *infer_culture_tags(text)]))[:6],
        "source_url": source_url,
        "website_url": website_url,
        "logo_url": logo_url,
        "discovery_queries": [],
        "relevance_score": min(0.95, 0.55 + min(len(jobs), 8) * 0.04),
    }
    return normalize_company_work_mode(normalize_company(company, source), source=source)
