"""
CompanyDiscoveryService — Multi-source company intelligence discovery engine.

Sources (via pluggable CompanySource connectors):
1. Hacker News "Who's Hiring" thread (Algolia API)
2. RemoteOK public API
3. Work at a Startup (YC job board)
4. Wellfound / AngelList
5. YCombinator company directory (Algolia API)
6. AI-powered discovery (GPT)

Pipeline:
  query_expansion → parallel source search → dedup → quality check →
  optional second pass → priority sort → return top N
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ─── New service imports ───────────────────────────────────────────────────────
try:
    from .query_expansion import QueryExpansionService
    from .company_sources import (
        HackerNewsSource,
        RemoteOKSource,
        WorkAtAStartupSource,
        WellfoundSource,
        YCCompaniesSource,
        AIDiscoverySource,
    )
    from ..db.supabase import supabase_client
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from backend.services.query_expansion import QueryExpansionService
    from backend.services.company_sources import (
        HackerNewsSource,
        RemoteOKSource,
        WorkAtAStartupSource,
        WellfoundSource,
        YCCompaniesSource,
        AIDiscoverySource,
    )
    from backend.db.supabase import supabase_client


# ─── Constants ────────────────────────────────────────────────────────────────

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
REMOTEOK_URL = "https://remoteok.com/api"
YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
GITHUB_API_URL = "https://api.github.com"
WELLFOUND_JOBS_URL = "https://wellfound.com/jobs"
WORK_AT_A_STARTUP_URL = "https://www.workatastartup.com/jobs"

DEFAULT_HEADERS = {
    "User-Agent": "OfferHunterAI/1.0 (job-discovery-bot; contact: support@offerhunterai.com)",
    "Accept": "application/json",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify_domain(company_name: str) -> str:
    """Convert company name to a guessed domain."""
    slug = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
    return f"{slug}.com"


def _extract_domain_from_url(url: str) -> str:
    match = re.search(r"(?:https?://)?(?:www\.)?([^/\s]+)", url or "")
    return match.group(1) if match else ""


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _normalize_company(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """Ensure a company dict has all expected keys."""
    return {
        "name": raw.get("name", ""),
        "domain": raw.get("domain", _slugify_domain(raw.get("name", "unknown"))),
        "description": raw.get("description", ""),
        "mission": raw.get("mission", ""),
        "industry": raw.get("industry", ""),
        "size": raw.get("size", ""),
        "tech_stack": raw.get("tech_stack", []),
        "funding_stage": raw.get("funding_stage", ""),
        "founded_year": raw.get("founded_year"),
        "headquarters": raw.get("headquarters", ""),
        "website_url": raw.get("website_url", ""),
        "linkedin_url": raw.get("linkedin_url", ""),
        "logo_url": raw.get("logo_url", ""),
        "hiring_status": raw.get("hiring_status", "unknown"),
        "remote_friendly": raw.get("remote_friendly"),
        "sponsorship_available": raw.get("sponsorship_available"),
        "open_positions": raw.get("open_positions", []),
        "culture_tags": raw.get("culture_tags", []),
        "source": source,
        "source_url": raw.get("source_url", ""),
        "relevance_score": raw.get("relevance_score", 0.5),
    }


def _domain_key(value: str) -> str:
    """Normalize domains/URLs for workspace exclusion and deduplication."""
    if not value:
        return ""
    parsed = urlparse(_normalize_url(value.strip().lower()))
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.removeprefix("www.").strip()


def _startup_priority_score(company: dict[str, Any]) -> tuple[float, float]:
    size = (company.get("size") or "").lower()
    stage = (company.get("funding_stage") or "").lower()
    source = (company.get("source") or "").lower()

    score = 0.0
    if any(token in size for token in ["<50", "1-10", "10-50", "11-50", "50-200", "51-200", "small"]):
        score += 1.2
    elif any(token in size for token in ["200-1000", "201-1000", "mid"]):
        score += 0.6
    elif any(token in size for token in ["1000", "5000", "enterprise"]):
        score += 0.1

    if any(token in stage for token in ["pre-seed", "seed", "series a", "yc", "series b"]):
        score += 0.8

    if source in {"wellfound", "workatastartup", "hackernews"}:
        score += 0.5

    return (score, float(company.get("relevance_score", 0.5) or 0.5))


# ─── Service ──────────────────────────────────────────────────────────────────

class CompanyDiscoveryService:
    """
    Multi-source company intelligence discovery engine.

    Orchestrates pluggable CompanySource connectors, AI query expansion,
    deduplication, and an iterative feedback loop to ensure quality and
    diversity of results.
    """

    # Quality thresholds for the feedback loop
    _MIN_DIVERSITY_SOURCES = 4      # At least N distinct sources represented
    _MIN_COMPANIES = 35             # Re-search if fewer than N unique companies found
    _MAX_FEEDBACK_ROUNDS = 3        # How many additional search rounds to run

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._github_token = os.getenv("GITHUB_TOKEN", "")
        # Service dependencies
        self._query_expander = QueryExpansionService()
        self._sources: list = [
            HackerNewsSource(),
            RemoteOKSource(),
            WorkAtAStartupSource(),
            WellfoundSource(),
            YCCompaniesSource(),
            AIDiscoverySource(api_key=self._api_key, model=self._model),
        ]
        self._source_modes: dict[str, set[str]] = {
            "all": {s.SOURCE_NAME for s in self._sources},
            "startups": {"HackerNews", "WorkAtAStartup", "Wellfound", "YCombinator", "AI Discovery"},
            "yc": {"YCombinator", "WorkAtAStartup"},
            "remote": {"RemoteOK", "HackerNews", "Wellfound"},
            "ai": {"AI Discovery", "HackerNews", "Wellfound", "RemoteOK"},
            "fortune500": {"AI Discovery", "RemoteOK", "HackerNews"},
            "stealth": {"AI Discovery", "HackerNews"},
            "international": {"RemoteOK", "Wellfound", "AI Discovery"},
            "visa": {"AI Discovery", "RemoteOK", "Wellfound", "HackerNews"},
        }

    async def discover(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        target_count: int = 30,
        progress_callback: Any = None,
        excluded_domains: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Discover companies via multi-source parallel search with query expansion
        and an iterative feedback loop.

        Args:
            profile:           Parsed resume profile.
            preferences:       User job preferences.
            target_count:      Target number of unique NEW companies to return.
            progress_callback: async callable(source_name, message) for SSE.
            excluded_domains:  Domains already in the user's workspace — these
                               are injected into the AI prompt and filtered out
                               of final results so every run returns fresh companies.

        Returns:
            Deduplicated, priority-sorted list of company dicts.
        """
        requested_count = max(target_count, 1)
        discovery_target = max(requested_count, 60)
        excluded = {_domain_key(d) for d in (excluded_domains or []) if d}

        # ── Inject internal keys so AI source can vary its prompt ─────────────
        # Mutate a shallow copy so we don't pollute the caller's preferences dict.
        prefs = dict(preferences)
        prefs["_excluded_domains"] = list(excluded)
        prefs["_excluded_names"] = list(prefs.get("_excluded_names") or [])
        prefs["_discovery_round"] = int(prefs.get("_discovery_round") or 1)

        # Request more than target_count to compensate for exclusion filtering
        inner_target = discovery_target + max(len(excluded) // 2, 20)

        # ── Phase 1: Expand queries ───────────────────────────────────────────
        if progress_callback:
            await progress_callback("QueryExpansion", "Expanding search queries with AI...")
        try:
            queries = await self._query_expander.expand_queries(profile, prefs)
        except Exception:
            queries = self._query_expander._base_queries(profile, prefs)

        if progress_callback:
            await progress_callback(
                "QueryExpansion",
                f"Generated {len(queries)} search queries: {', '.join(queries[:5])}{'...' if len(queries) > 5 else ''}",
            )

        # ── Phase 2: Run all sources in parallel ──────────────────────────────
        if progress_callback:
            await progress_callback(
                "Discovery",
                "Searching Hacker News, RemoteOK, Work at a Startup, Wellfound, YC, and AI sources...",
            )
        source_mode = str(preferences.get("source_mode") or "all").strip().lower()
        allowed_sources = self._source_modes.get(source_mode, self._source_modes["all"])
        active_sources = [s for s in self._sources if s.SOURCE_NAME in allowed_sources]
        companies = await self._run_all_sources(
            profile,
            prefs,
            queries,
            progress_callback,
            active_sources,
        )

        # ── Phase 3: Dedup ────────────────────────────────────────────────────
        companies = self._deduplicate(companies)
        if progress_callback:
            await progress_callback("Discovery", f"Deduplicated to {len(companies)} unique companies")

        # ── Phase 4: Feedback loop (second pass if quality is low) ────────────
        companies = await self._feedback_loop(
            companies, profile, prefs, queries, inner_target, progress_callback
        )

        # ── Phase 4.5: Filter clearly irrelevant industries ───────────────────
        companies = self._filter_industry_mismatch(companies, profile, preferences)

        # ── Phase 4.6: Remove companies already in the user's workspace ───────
        if excluded:
            before = len(companies)
            companies = [
                c for c in companies
                if _domain_key(c.get("domain") or c.get("website_url") or "") not in excluded
            ]
            if progress_callback and before != len(companies):
                await progress_callback(
                    "Discovery",
                    f"Filtered out {before - len(companies)} already-discovered companies — "
                    f"{len(companies)} new companies remaining",
                )

        # ── Phase 5: Sort by startup priority + relevance ─────────────────────
        companies.sort(key=_startup_priority_score, reverse=True)
        return companies[:discovery_target]

    # ─── Internal Pipeline Helpers ────────────────────────────────────────────

    # ── Industry exclusion lists ──────────────────────────────────────────────
    _TECH_INDICATORS = {
        "software", "developer", "engineer", "ml", "ai", "data", "cloud",
        "devops", "backend", "frontend", "fullstack", "full-stack", "saas",
        "platform", "infrastructure", "security", "cybersecurity", "fintech",
        "edtech", "healthtech", "deep learning", "machine learning",
    }

    # Industries that are unambiguously non-tech when user is targeting tech roles
    _OFF_DOMAIN_INDUSTRIES = {
        "travel", "hospitality", "hotel", "tourism", "restaurant", "food service",
        "retail", "fashion", "apparel", "beauty", "cosmetics",
        "construction", "real estate", "property",
        "transportation", "logistics", "trucking", "freight",
        "agriculture", "farming",
        "manufacturing", "automotive",
        "staffing", "recruitment", "temp agency",
    }

    def _filter_industry_mismatch(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Remove companies in clearly unrelated industries when the user has
        explicit tech/software role preferences.

        Only activates when the user's target roles/skills indicate a tech background;
        otherwise returns companies unchanged to avoid over-filtering.
        """
        all_roles = [
            r.lower()
            for r in (
                preferences.get("preferred_roles", [])
                + profile.get("preferred_domains", [])
                + profile.get("skills", [])[:5]
            )
        ]
        industries_pref = [
            i.lower() for i in preferences.get("industries_of_interest", [])
        ]

        # Only apply if user has clear tech signals
        user_is_tech = any(
            ind in " ".join(all_roles) for ind in self._TECH_INDICATORS
        ) or any(ind in " ".join(industries_pref) for ind in self._TECH_INDICATORS)

        if not user_is_tech:
            return companies

        filtered: list[dict[str, Any]] = []
        for company in companies:
            industry = (company.get("industry") or "").lower()
            name = (company.get("name") or "").lower()
            culture_tags = [t.lower() for t in company.get("culture_tags", [])]

            # If the company explicitly opts into tech, keep it regardless
            company_text = f"{industry} {name} {' '.join(culture_tags)}"
            if any(ind in company_text for ind in self._TECH_INDICATORS):
                filtered.append(company)
                continue

            # Reject companies whose industry is unambiguously off-domain
            if any(off in company_text for off in self._OFF_DOMAIN_INDUSTRIES):
                continue

            # Keep anything else (industry unknown / neutral)
            filtered.append(company)

        return filtered

    async def _run_all_sources(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: Any,
        sources: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Run all CompanySource connectors in parallel with individual timeouts.
        Each source gets a dedicated progress callback so SSE updates are per-source.
        """
        async def _run_source(source) -> list[dict[str, Any]]:
            started = time.perf_counter()
            log_base = {
                "user_id": preferences.get("_user_id"),
                "discovery_session_id": preferences.get("_discovery_session_id"),
                "source": source.SOURCE_NAME,
                "query_used": queries[:12],
                "started_at": datetime.utcnow().isoformat(),
            }
            try:
                result = await asyncio.wait_for(
                    source.search(profile, preferences, queries, progress_callback),
                    timeout=30.0,
                )
                await self._record_source_log({
                    **log_base,
                    "status": "success",
                    "result_count": len(result),
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "completed_at": datetime.utcnow().isoformat(),
                })
                return result
            except asyncio.TimeoutError:
                if progress_callback:
                    await progress_callback(source.SOURCE_NAME, f"{source.SOURCE_NAME} timed out")
                await self._record_source_log({
                    **log_base,
                    "status": "timeout",
                    "error": "Timed out after 30 seconds",
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "completed_at": datetime.utcnow().isoformat(),
                })
                return []
            except Exception as exc:
                if progress_callback:
                    await progress_callback(
                        source.SOURCE_NAME,
                        f"{source.SOURCE_NAME} failed: {type(exc).__name__}",
                    )
                await self._record_source_log({
                    **log_base,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "completed_at": datetime.utcnow().isoformat(),
                })
                return []

        results = await asyncio.gather(*[_run_source(s) for s in sources])
        all_companies: list[dict[str, Any]] = []
        for source, result in zip(sources, results):
            if result:
                all_companies.extend(result)
                if progress_callback:
                    await progress_callback(
                        source.SOURCE_NAME,
                        f"{source.SOURCE_NAME}: +{len(result)} companies",
                    )
        return all_companies

    @staticmethod
    async def _record_source_log(log: dict[str, Any]) -> None:
        if not log.get("user_id"):
            return
        try:
            await supabase_client.insert_discovery_source_log(log)
        except Exception:
            pass

    async def _feedback_loop(
        self,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        base_queries: list[str],
        target_count: int,
        progress_callback: Any,
    ) -> list[dict[str, Any]]:
        """
        Iterative quality improvement: if results are sparse or lack diversity,
        run additional passes with expanded queries.
        """
        sources_present = len({c.get("source", "") for c in companies})

        if (
            len(companies) >= self._MIN_COMPANIES
            and sources_present >= self._MIN_DIVERSITY_SOURCES
        ):
            return companies  # Quality is good, skip feedback rounds

        for round_num in range(self._MAX_FEEDBACK_ROUNDS):
            if len(companies) >= target_count:
                break

            if progress_callback:
                await progress_callback(
                    "Discovery",
                    f"Quality check: {len(companies)} companies from {sources_present} sources. "
                    f"Running additional discovery pass ({round_num + 1}/{self._MAX_FEEDBACK_ROUNDS})...",
                )

            # Use the AI source with more variation on each pass and exclude
            # companies already found in earlier passes so the graph expands.
            try:
                existing_domains = {
                    _domain_key(c.get("domain") or c.get("website_url") or "")
                    for c in companies
                    if c.get("domain") or c.get("website_url")
                }
                existing_names = {
                    (c.get("name") or "").lower().strip()
                    for c in companies
                    if c.get("name")
                }
                round_preferences = dict(preferences)
                round_preferences["_excluded_domains"] = sorted(
                    set(round_preferences.get("_excluded_domains") or []) | existing_domains
                )
                round_preferences["_excluded_names"] = sorted(
                    set(round_preferences.get("_excluded_names") or []) | existing_names
                )
                round_preferences["_discovery_round"] = (
                    int(round_preferences.get("_discovery_round") or 1) + round_num + 1
                )
                ai_source = AIDiscoverySource(api_key=self._api_key, model=self._model)
                additional = await asyncio.wait_for(
                    ai_source.search(
                        profile,
                        round_preferences,
                        base_queries[3:] + base_queries[:3],  # shifted queries
                        progress_callback,
                        count=max(target_count - len(companies) + 10, 25),
                    ),
                    timeout=45.0,
                )
                companies.extend(additional)
                companies = self._deduplicate(companies)
                sources_present = len({c.get("source", "") for c in companies})
            except Exception as exc:
                if progress_callback:
                    await progress_callback(
                        "Discovery",
                        f"Additional discovery pass failed: {type(exc).__name__}",
                    )
                break

        return companies

    @staticmethod
    def _deduplicate(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate companies by domain (case-insensitive)."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for company in companies:
            domain = _domain_key(company.get("domain") or company.get("website_url") or "")
            if domain and domain not in seen:
                seen.add(domain)
                unique.append(company)
            elif not domain:
                # No domain — use name as dedup key
                name_key = (company.get("name") or "").lower().strip()
                if name_key and name_key not in seen:
                    seen.add(name_key)
                    unique.append(company)
        return unique

    async def profile_company_website(self, website_url: str) -> dict[str, Any]:
        """Build a company profile from a user-supplied company website."""
        normalized_url = _normalize_url(website_url.strip())
        if not normalized_url:
            raise ValueError("A company website URL is required")

        domain = _extract_domain_from_url(normalized_url)
        if not domain:
            raise ValueError("Invalid company website URL")

        page_urls = [normalized_url]
        page_urls.extend(
            [
                urljoin(normalized_url, "/about"),
                urljoin(normalized_url, "/careers"),
                urljoin(normalized_url, "/jobs"),
            ]
        )

        pages: list[tuple[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for page_url in page_urls:
                try:
                    response = await client.get(page_url)
                    if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                        pages.append((page_url, response.text))
                except Exception:
                    continue

        if not pages:
            raise ValueError("Could not scrape the company website")

        home_url, home_html = pages[0]
        soup = BeautifulSoup(home_html, "html.parser")
        meta_description = (
            (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "")
            or (soup.find("meta", attrs={"property": "og:description"}) or {}).get("content", "")
        )
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
        site_name = ((soup.find("meta", attrs={"property": "og:site_name"}) or {}).get("content", "") or "").strip()

        text_chunks: list[str] = []
        careers_links: list[dict[str, str]] = []
        linkedin_url = ""

        for page_url, html in pages:
            page_soup = BeautifulSoup(html, "html.parser")
            for script in page_soup(["script", "style", "noscript"]):
                script.decompose()
            text = re.sub(r"\s+", " ", page_soup.get_text(" ", strip=True))
            if text:
                text_chunks.append(text[:4000])

            for anchor in page_soup.find_all("a", href=True):
                href = urljoin(page_url, anchor["href"])
                label = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
                href_lower = href.lower()
                label_lower = label.lower()
                if not linkedin_url and "linkedin.com/company/" in href_lower:
                    linkedin_url = href
                if any(token in href_lower for token in ["/careers", "/jobs", "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com"]):
                    careers_links.append({"title": label or "Open roles", "url": href})
                elif any(token in label_lower for token in ["careers", "jobs", "join us", "open roles", "we're hiring"]):
                    careers_links.append({"title": label or "Open roles", "url": href})

        combined_text = " ".join(text_chunks)
        name = site_name or self._infer_company_name(title, domain)
        description = meta_description or self._extract_description_from_text(combined_text)
        remote_friendly = any(token in combined_text.lower() for token in ["remote", "distributed", "work from anywhere"])
        hiring_status = "actively_hiring" if careers_links or any(token in combined_text.lower() for token in ["join us", "we're hiring", "open roles", "careers"]) else "unknown"

        company = {
            "name": name,
            "domain": domain,
            "website_url": home_url,
            "source_url": normalized_url,
            "source": "Website Submission",
            "description": description,
            "mission": self._extract_mission_from_text(combined_text),
            "industry": self._infer_industry(combined_text),
            "size": self._infer_company_size(combined_text),
            "tech_stack": self._infer_tech_stack(combined_text),
            "funding_stage": self._infer_funding_stage(combined_text),
            "headquarters": self._infer_headquarters(combined_text),
            "linkedin_url": linkedin_url,
            "hiring_status": hiring_status,
            "remote_friendly": remote_friendly,
            "open_positions": careers_links[:8],
            "culture_tags": self._infer_culture_tags(combined_text),
        }

        # If key fields are sparse (SPA / CSR site), enrich with AI
        sparse = (not description or len(description) < 80) and not company["tech_stack"]
        if sparse and self._api_key:
            try:
                company = await self._ai_enrich_company(company, combined_text)
            except Exception:
                pass

        return _normalize_company(company, "Website Submission")

    # ─── HackerNews Who's Hiring ──────────────────────────────────────────────

    async def _discover_from_hn(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Search HN 'Who is Hiring' monthly thread comments via Algolia API.
        First finds the latest hiring thread, then searches its comments for
        matching roles/skills using the pipe-delimited hiring post format.
        """
        roles = preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        skills = profile.get("tech_stack", [])[:5]
        query_terms = list(roles[:2]) + list(skills[:3])
        if not query_terms:
            query_terms = ["software engineer"]
        query = " ".join(query_terms)

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=DEFAULT_HEADERS) as client:
                # Step 1: Find the latest "Ask HN: Who is hiring?" story
                hiring_resp = await client.get(
                    HN_ALGOLIA_URL,
                    params={
                        "query": "Ask HN: Who is hiring?",
                        "tags": "ask_hn",
                        "numericFilters": "created_at_i>1700000000",
                        "hitsPerPage": 3,
                    },
                )
                story_id = None
                if hiring_resp.status_code == 200:
                    stories = hiring_resp.json().get("hits", [])
                    if stories:
                        story_id = stories[0].get("objectID")

                # Step 2: Search comments on that thread matching user skills
                params: dict = {
                    "query": query,
                    "numericFilters": "created_at_i>1700000000",
                    "hitsPerPage": 50,
                }
                if story_id:
                    params["tags"] = f"comment,story_{story_id}"
                else:
                    # Fallback: search all HN comments tagged with job-related terms
                    params["tags"] = "comment"
                    params["query"] = f"hiring {query}"

                response = await client.get(HN_ALGOLIA_URL, params=params)
                if response.status_code != 200:
                    return []

                hits = response.json().get("hits", [])

        except Exception:
            return []

        companies = []
        for hit in hits:
            title = hit.get("story_title", "") or ""
            text = hit.get("comment_text", "") or hit.get("story_text", "") or ""
            if not text:
                continue
            extracted = self._extract_companies_from_hn_post(title, text)
            companies.extend(extracted)

        return [_normalize_company(c, "HackerNews") for c in companies[:10]]

    def _extract_companies_from_hn_post(
        self, title: str, text: str
    ) -> list[dict[str, Any]]:
        """Extract structured company info from an HN post."""
        companies = []

        # Common HN hiring post format: "CompanyName | Role | Location | Remote"
        pipe_pattern = re.compile(r"^([A-Z][A-Za-z0-9 .,&!-]{2,40})\s*\|", re.MULTILINE)
        matches = pipe_pattern.findall(text[:3000])

        for name in matches[:5]:
            name = name.strip()
            if len(name) > 3 and not name.lower().startswith(("we ", "our ", "the ")):
                url_match = re.search(
                    rf"(?:https?://)?(?:www\.)?[\w-]+\.(?:com|io|ai|co|org)",
                    text,
                    re.IGNORECASE,
                )
                companies.append({
                    "name": name,
                    "domain": _slugify_domain(name),
                    "source_url": url_match.group(0) if url_match else "",
                    "hiring_status": "actively_hiring",
                    "description": f"Hiring via Hacker News: {title[:100]}",
                })

        return companies

    # ─── RemoteOK ─────────────────────────────────────────────────────────────

    async def _discover_from_remoteok(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetch jobs from RemoteOK free API and extract companies.
        """
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={**DEFAULT_HEADERS, "Accept": "application/json"},
                follow_redirects=True,
            ) as client:
                response = await client.get(REMOTEOK_URL)
                if response.status_code != 200:
                    return []
                jobs = response.json()
        except Exception:
            return []

        # Filter jobs by relevance to user profile
        skills = set(s.lower() for s in profile.get("skills", []) + profile.get("tech_stack", []))
        roles = [r.lower() for r in (preferences.get("preferred_roles") or profile.get("preferred_domains", []))]

        seen_companies: dict[str, dict[str, Any]] = {}

        for job in jobs:
            if not isinstance(job, dict):
                continue

            company_name = job.get("company", "")
            if not company_name:
                continue

            title = (job.get("position", "") or "").lower()
            job_tags = set(t.lower() for t in (job.get("tags", []) or []))

            # Check relevance
            role_match = any(r in title for r in roles) if roles else True
            skill_match = bool(skills & job_tags)

            if not (role_match or skill_match) and roles:
                continue

            if company_name not in seen_companies:
                company_url = job.get("url", "")
                domain = _extract_domain_from_url(company_url)

                seen_companies[company_name] = {
                    "name": company_name,
                    "domain": domain or _slugify_domain(company_name),
                    "logo_url": job.get("company_logo", ""),
                    "hiring_status": "actively_hiring",
                    "remote_friendly": True,
                    "open_positions": [],
                    "source_url": f"https://remoteok.com",
                }

            seen_companies[company_name]["open_positions"].append({
                "title": job.get("position", ""),
                "url": job.get("url", ""),
                "work_mode": "remote",
                "salary_range": f"${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}" if job.get("salary_min") else "",
                "posted_at": job.get("date", ""),
            })

        companies = [_normalize_company(c, "RemoteOK") for c in seen_companies.values()]
        return companies[:15]

    async def _discover_from_workatastartup(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Scrape Work at a Startup for smaller YC-backed companies and roles."""
        role = quote((preferences.get("preferred_roles") or profile.get("preferred_domains") or ["software-engineer"])[0].lower().replace(" ", "-"))
        remote_only = (preferences.get("work_mode") or "").lower() == "remote"
        target_url = f"{WORK_AT_A_STARTUP_URL}/r/{role}" if remote_only else f"{WORK_AT_A_STARTUP_URL}/l/{role}"

        try:
            async with httpx.AsyncClient(timeout=20.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
                response = await client.get(target_url)
                if response.status_code != 200:
                    response = await client.get(WORK_AT_A_STARTUP_URL)
                if response.status_code != 200:
                    return []
                soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            return []

        companies: dict[str, dict[str, Any]] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/companies/" not in href:
                continue

            line = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            if not line:
                continue

            company_name, descriptor = self._parse_workatastartup_company_line(line)
            company_url = urljoin(WORK_AT_A_STARTUP_URL, href)
            job_anchor = anchor.find_next("a", href=re.compile(r"/jobs/\d+"))
            job_title = job_anchor.get_text(" ", strip=True) if job_anchor else ""
            job_url = urljoin(WORK_AT_A_STARTUP_URL, job_anchor["href"]) if job_anchor else company_url

            company = companies.setdefault(company_name, {
                "name": company_name,
                "domain": _slugify_domain(company_name),
                "description": descriptor,
                "industry": self._infer_industry(descriptor),
                "size": "Startup (< 50)",
                "funding_stage": "YC-backed",
                "hiring_status": "actively_hiring",
                "remote_friendly": "remote" in line.lower(),
                "website_url": "",
                "source_url": company_url,
                "open_positions": [],
                "culture_tags": ["startup", "yc"],
            })
            if job_title:
                company["open_positions"].append({
                    "title": job_title,
                    "url": job_url,
                    "work_mode": "remote" if "remote" in line.lower() else "hybrid_or_onsite",
                })

        return [_normalize_company(c, "WorkAtAStartup") for c in companies.values()][:15]

    async def _discover_from_wellfound(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Best-effort scrape for Wellfound startup listings. Returns [] if blocked."""
        role_terms = preferences.get("preferred_roles") or profile.get("preferred_domains") or ["software engineer"]
        query = quote(role_terms[0])
        target_url = f"{WELLFOUND_JOBS_URL}?query={query}"

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers={
                    **DEFAULT_HEADERS,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://wellfound.com/",
                },
            ) as client:
                response = await client.get(target_url)
                if response.status_code != 200:
                    return []
                soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            return []

        companies: dict[str, dict[str, Any]] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/company/" not in href and "/jobs/" not in href:
                continue

            text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            if not text or len(text) < 2:
                continue

            company_name = self._extract_wellfound_company_name(text)
            if not company_name:
                continue

            company_url = urljoin(WELLFOUND_JOBS_URL, href)
            companies.setdefault(company_name, {
                "name": company_name,
                "domain": _slugify_domain(company_name),
                "description": text[:180],
                "size": "Startup (< 50)",
                "funding_stage": "Startup",
                "hiring_status": "actively_hiring",
                "remote_friendly": "remote" in text.lower(),
                "source_url": company_url,
                "culture_tags": ["startup"],
            })

        return [_normalize_company(c, "Wellfound") for c in companies.values()][:10]

    def _parse_workatastartup_company_line(self, line: str) -> tuple[str, str]:
        match = re.match(r"^(?P<name>.+?)\s*\((?P<batch>[^)]+)\)\s*[•-]\s*(?P<desc>.+)$", line)
        if match:
            return match.group("name").strip(), match.group("desc").strip()
        return line.split("•", 1)[0].strip(), line

    def _extract_wellfound_company_name(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.split(r"\s+[•·|-]\s+", cleaned, maxsplit=1)[0]
        if len(cleaned) < 2 or len(cleaned) > 60:
            return ""
        return cleaned

    async def _ai_enrich_company(self, company: dict, scraped_text: str) -> dict:
        """Use GPT to fill in sparse company profile fields (for CSR/SPA sites)."""
        domain = company.get("domain", "")
        name = company.get("name", domain)
        existing_desc = company.get("description", "")
        text_snippet = scraped_text[:2000] if scraped_text else ""

        prompt = (
            f"Given this website domain and scraped text, infer the company profile.\n"
            f"Domain: {domain}\n"
            f"Company name (guessed): {name}\n"
            f"Scraped text snippet: {text_snippet[:1500]}\n\n"
            f"Return a JSON object with these fields (only fill what you can reasonably infer):\n"
            f'{{"description": "...", "mission": "...", "industry": "...", '
            f'"size": "e.g. 1-50", "tech_stack": [...], "funding_stage": "...", '
            f'"headquarters": "city, country", "culture_tags": [...], '
            f'"remote_friendly": true/false, "hiring_status": "unknown"}}'
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": "You are a company research expert. Return only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = json.loads(response.json()["choices"][0]["message"]["content"])

        # Merge: only overwrite fields that are currently empty/unknown
        for key, val in data.items():
            if not company.get(key) or company.get(key) in ("", "Other", "Unknown", "unknown", []):
                company[key] = val

        return company

    def _infer_company_name(self, title: str, domain: str) -> str:
        if title:
            base = re.split(r"[|\-–—]", title, maxsplit=1)[0].strip()
            if 1 < len(base) <= 60:
                return base
        host = urlparse(_normalize_url(domain)).netloc or domain
        label = host.replace("www.", "").split(".")[0]
        return label.replace("-", " ").title()

    def _extract_description_from_text(self, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            cleaned = sentence.strip()
            if 40 <= len(cleaned) <= 220:
                return cleaned
        return text[:180]

    def _extract_mission_from_text(self, text: str) -> str:
        patterns = [r"(?:mission|purpose)\s*(?:is|:)?\s*([^.!?]{25,200})", r"we build\s+([^.!?]{20,180})"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _infer_industry(self, text: str) -> str:
        lowered = text.lower()
        industry_map = {
            "AI / ML": ["ai", "machine learning", "llm", "foundation model", "agentic"],
            "Fintech": ["fintech", "payments", "banking", "lending", "invoice"],
            "Healthcare / Biotech": ["healthcare", "biotech", "clinical", "medical", "drug"],
            "Developer Tools": ["developer", "api", "sdk", "observability", "devops"],
            "Cybersecurity": ["security", "identity", "compliance", "fraud", "threat"],
            "Enterprise SaaS": ["saas", "workflow", "crm", "sales", "operations"],
            "Robotics": ["robotics", "drone", "autonomous", "hardware"],
        }
        for industry, keywords in industry_map.items():
            if any(keyword in lowered for keyword in keywords):
                return industry
        return ""

    def _infer_company_size(self, text: str) -> str:
        lowered = text.lower()
        patterns = [
            (r"(\d{1,4})\+? employees", None),
            (r"team of (\d{1,4})", None),
        ]
        for pattern, _ in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            count = int(match.group(1))
            if count < 50:
                return "Startup (< 50)"
            if count < 200:
                return "Small (50-200)"
            if count < 1000:
                return "Mid-size (200-1000)"
            if count < 5000:
                return "Large (1000-5000)"
            return "Enterprise (5000+)"

        if any(token in lowered for token in ["seed stage", "early-stage", "founding team", "series a"]):
            return "Startup (< 50)"
        return ""

    def _infer_tech_stack(self, text: str) -> list[str]:
        lowered = text.lower()
        tech_keywords = {
            "Python": ["python"],
            "TypeScript": ["typescript"],
            "JavaScript": ["javascript"],
            "React": ["react"],
            "Next.js": ["next.js", "nextjs"],
            "Node.js": ["node.js", "nodejs"],
            "Go": [" golang", " go ", "go services"],
            "Rust": ["rust"],
            "Java": ["java"],
            "Kubernetes": ["kubernetes", "k8s"],
            "AWS": ["aws"],
            "GCP": ["gcp", "google cloud"],
            "Postgres": ["postgres", "postgresql"],
            "PyTorch": ["pytorch"],
            "TensorFlow": ["tensorflow"],
        }
        found = []
        for tech, patterns in tech_keywords.items():
            if any(pattern in lowered for pattern in patterns):
                found.append(tech)
        return found[:8]

    def _infer_funding_stage(self, text: str) -> str:
        lowered = text.lower()
        for stage in ["pre-seed", "seed", "series a", "series b", "series c", "series d", "public"]:
            if stage in lowered:
                return stage.title()
        if "y combinator" in lowered or re.search(r"\b[wsf]\d{2}\b", lowered):
            return "YC-backed"
        return ""

    def _infer_headquarters(self, text: str) -> str:
        match = re.search(r"(?:based in|headquartered in|located in)\s+([A-Z][A-Za-z .,-]{3,60})", text)
        if match:
            return match.group(1).strip()
        return ""

    def _infer_culture_tags(self, text: str) -> list[str]:
        lowered = text.lower()
        tags = []
        tag_keywords = {
            "remote": ["remote", "distributed"],
            "startup": ["early-stage", "founding", "startup"],
            "fast-paced": ["fast-paced", "move fast"],
            "mission-driven": ["mission-driven", "purpose"],
            "ownership": ["ownership", "high agency"],
            "research": ["research", "experimentation"],
        }
        for tag, keywords in tag_keywords.items():
            if any(keyword in lowered for keyword in keywords):
                tags.append(tag)
        return tags[:6]

    # ─── YC Companies ─────────────────────────────────────────────────────────

    async def _discover_from_yc(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fetch YC companies from their public search API.
        YC exposes a JSON API at https://www.ycombinator.com/companies?batch=...
        """
        roles = preferences.get("preferred_roles", []) or profile.get("preferred_domains", [])
        industries = preferences.get("industries_of_interest", [])
        query_terms = (industries or roles)[:2]

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={
                    **DEFAULT_HEADERS,
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                # YC has a public algolia-backed search
                response = await client.get(
                    "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries",
                    params={"x-algolia-agent": "OfferHunterAI"},
                    headers={
                        "x-algolia-application-id": "45BWZJ1SGC",
                        "x-algolia-api-key": "Zjk5ZmUyZjBhMmIyZDgxODRhOWMxNjZjMzg5MDZlNjFhMWM4YWViZjYxOTA1YWZiNzg2ZTU2ZGQ4ZjkwNjVmZnJlc3RyaWN0SW5kaWNlcz1ZQ0NvbXBhbnlfcHJvZHVjdGlvbiZ2YWxpZFVudGlsPTE3NjQ0NDE0MTE=",
                        "Content-Type": "application/json",
                        "User-Agent": DEFAULT_HEADERS["User-Agent"],
                    },
                    content=json.dumps({
                        "requests": [
                            {
                                "indexName": "YCCompany_production",
                                "query": " ".join(query_terms),
                                "params": "hitsPerPage=20&page=0&facets=%5B%22top_company%22%2C%22isHiring%22%5D&facetFilters=%5B%5B%22isHiring%3Atrue%22%5D%5D",
                            }
                        ]
                    }).encode(),
                )

                if response.status_code != 200:
                    return await self._yc_fallback(profile, preferences)

                data = response.json()
                hits = data.get("results", [{}])[0].get("hits", [])

        except Exception:
            return await self._yc_fallback(profile, preferences)

        companies = []
        for hit in hits:
            company = {
                "name": hit.get("name", ""),
                "domain": _extract_domain_from_url(hit.get("website", "")) or _slugify_domain(hit.get("name", "")),
                "description": hit.get("one_liner", ""),
                "industry": hit.get("tags", [""])[0] if hit.get("tags") else "",
                "size": hit.get("team_size", ""),
                "headquarters": hit.get("location", ""),
                "website_url": hit.get("website", ""),
                "logo_url": hit.get("small_logo_url", ""),
                "funding_stage": "YC-backed",
                "hiring_status": "actively_hiring" if hit.get("isHiring") else "unknown",
                "culture_tags": hit.get("tags", []),
                "source_url": f"https://www.ycombinator.com/companies/{hit.get('slug', '')}",
            }
            if company["name"]:
                companies.append(_normalize_company(company, "YCombinator"))

        return companies[:15]

    async def _yc_fallback(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Fallback: return well-known YC companies relevant to the user's profile.
        """
        known_yc: list[dict[str, Any]] = [
            {"name": "Stripe", "domain": "stripe.com", "industry": "Fintech", "funding_stage": "YC S09", "website_url": "https://stripe.com", "headquarters": "San Francisco, CA"},
            {"name": "Airbnb", "domain": "airbnb.com", "industry": "Travel / Marketplace", "funding_stage": "YC W09", "website_url": "https://airbnb.com", "headquarters": "San Francisco, CA"},
            {"name": "Brex", "domain": "brex.com", "industry": "Fintech", "funding_stage": "YC W17", "website_url": "https://brex.com", "headquarters": "San Francisco, CA"},
            {"name": "Scale AI", "domain": "scale.com", "industry": "AI/ML", "funding_stage": "YC S16", "website_url": "https://scale.com", "headquarters": "San Francisco, CA"},
            {"name": "Gusto", "domain": "gusto.com", "industry": "HR Tech", "funding_stage": "YC W12", "website_url": "https://gusto.com", "headquarters": "San Francisco, CA"},
            {"name": "Rippling", "domain": "rippling.com", "industry": "HR Tech", "funding_stage": "YC W16", "website_url": "https://rippling.com", "headquarters": "San Francisco, CA"},
            {"name": "Deel", "domain": "deel.com", "industry": "HR Tech", "funding_stage": "YC W19", "website_url": "https://deel.com", "headquarters": "San Francisco, CA"},
            {"name": "Retool", "domain": "retool.com", "industry": "Developer Tools", "funding_stage": "YC S17", "website_url": "https://retool.com", "headquarters": "San Francisco, CA"},
            {"name": "Posthog", "domain": "posthog.com", "industry": "Developer Tools", "funding_stage": "YC W20", "website_url": "https://posthog.com", "headquarters": "Remote"},
            {"name": "Supabase", "domain": "supabase.com", "industry": "Developer Tools", "funding_stage": "YC S20", "website_url": "https://supabase.com", "headquarters": "Remote"},
            {"name": "Linear", "domain": "linear.app", "industry": "Productivity", "funding_stage": "Series B", "website_url": "https://linear.app", "headquarters": "San Francisco, CA"},
            {"name": "Vercel", "domain": "vercel.com", "industry": "Developer Tools", "funding_stage": "Series D", "website_url": "https://vercel.com", "headquarters": "Remote"},
        ]
        skills = set(s.lower() for s in profile.get("skills", []) + profile.get("tech_stack", []))
        domains = set(d.lower() for d in profile.get("preferred_domains", []))

        industry_map = {
            "ai": {"AI/ML", "Data Science", "Machine Learning"},
            "ml": {"AI/ML", "Data Science", "Machine Learning"},
            "fintech": {"Fintech", "Finance"},
            "dev": {"Developer Tools"},
            "frontend": {"Developer Tools", "Productivity"},
            "backend": {"Developer Tools", "Cloud"},
            "fullstack": {"Developer Tools"},
        }

        relevant_industries: set[str] = set()
        for skill in skills | domains:
            for k, v in industry_map.items():
                if k in skill:
                    relevant_industries |= v

        result = []
        for c in known_yc:
            c["hiring_status"] = "hiring"
            normalized = _normalize_company(c, "YCombinator")
            normalized["relevance_score"] = 0.7
            result.append(normalized)

        return result

    # ─── AI-Powered Discovery ─────────────────────────────────────────────────

    async def _discover_via_ai(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        count: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Ask the LLM to suggest companies that match the user's profile.
        Returns a list of company dicts.
        """
        if not self._api_key:
            return self._ai_fallback(profile, preferences)

        skills_str = ", ".join(profile.get("tech_stack", [])[:10])
        roles_str = ", ".join(
            preferences.get("preferred_roles", [])
            or profile.get("preferred_domains", [])
        )
        industries_str = ", ".join(preferences.get("industries_of_interest", []))
        work_mode = preferences.get("work_mode", "flexible")
        startup_pref = preferences.get("open_to_startups", True)
        sponsorship = preferences.get("sponsorship_required", False)

        prompt = f"""You are a job market expert. Suggest {min(count, 25)} specific real companies
actively hiring that match this candidate profile:

Skills: {skills_str}
Target Roles: {roles_str}
Industries of Interest: {industries_str or "Open to any"}
Work mode preference: {work_mode}
Open to startups: {startup_pref}
Needs visa sponsorship: {sponsorship}

Return ONLY a JSON array of company objects. Each object must have:
{{
  "name": "exact company name",
  "domain": "company domain (e.g. stripe.com)",
  "description": "1-2 sentence company description",
  "industry": "primary industry",
  "size": "employee count range (e.g. 500-1000)",
  "headquarters": "city, state/country",
  "tech_stack": ["list of technologies they use"],
  "funding_stage": "Seed/Series A/B/C/Public/etc",
  "remote_friendly": true/false,
  "sponsorship_available": true/false/null,
  "hiring_status": "actively_hiring",
  "website_url": "https://...",
  "culture_tags": ["list of culture descriptors"],
  "why_match": "brief explanation of why this company matches"
}}

Only include real companies. Vary between startups, mid-size, and large companies."""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a job market expert. Return only valid JSON arrays.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4096,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                data = json.loads(content)

                # Handle both {"companies": [...]} and [...]
                if isinstance(data, list):
                    raw_companies = data
                elif isinstance(data, dict):
                    raw_companies = data.get("companies", data.get("results", list(data.values())[0] if data else []))
                else:
                    return self._ai_fallback(profile, preferences)

                return [_normalize_company(c, "AI Discovery") for c in raw_companies if isinstance(c, dict) and c.get("name")]

        except Exception:
            return self._ai_fallback(profile, preferences)

    def _ai_fallback(
        self, profile: dict[str, Any], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Static fallback company list when AI is unavailable."""
        fallback = [
            {"name": "OpenAI", "domain": "openai.com", "industry": "AI/ML", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://openai.com", "tech_stack": ["Python", "PyTorch", "Kubernetes", "React"]},
            {"name": "Anthropic", "domain": "anthropic.com", "industry": "AI/ML", "size": "300-500", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://anthropic.com", "tech_stack": ["Python", "PyTorch", "React", "TypeScript"]},
            {"name": "Google DeepMind", "domain": "deepmind.com", "industry": "AI/ML Research", "size": "1000-5000", "headquarters": "London, UK / Mountain View, CA", "remote_friendly": False, "hiring_status": "hiring", "website_url": "https://deepmind.com", "tech_stack": ["Python", "TensorFlow", "JAX", "C++"]},
            {"name": "Cohere", "domain": "cohere.com", "industry": "AI/ML", "size": "200-500", "headquarters": "Toronto, Canada", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cohere.com", "tech_stack": ["Python", "PyTorch", "Go", "React"]},
            {"name": "Mistral AI", "domain": "mistral.ai", "industry": "AI/ML", "size": "50-200", "headquarters": "Paris, France", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://mistral.ai", "tech_stack": ["Python", "PyTorch", "Rust"]},
            {"name": "Databricks", "domain": "databricks.com", "industry": "Data / AI Platform", "size": "5000+", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://databricks.com", "tech_stack": ["Python", "Scala", "Spark", "React"]},
            {"name": "Hugging Face", "domain": "huggingface.co", "industry": "AI/ML", "size": "200-500", "headquarters": "New York, NY", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://huggingface.co", "tech_stack": ["Python", "PyTorch", "JavaScript", "Rust"]},
            {"name": "Figma", "domain": "figma.com", "industry": "Design Tools", "size": "1000-2000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://figma.com", "tech_stack": ["C++", "TypeScript", "React", "WebAssembly"]},
            {"name": "Notion", "domain": "notion.so", "industry": "Productivity", "size": "500-1000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "hiring", "website_url": "https://notion.so", "tech_stack": ["TypeScript", "React", "Electron", "Go"]},
            {"name": "Cloudflare", "domain": "cloudflare.com", "industry": "Cloud / Networking", "size": "3000-5000", "headquarters": "San Francisco, CA", "remote_friendly": True, "hiring_status": "actively_hiring", "website_url": "https://cloudflare.com", "tech_stack": ["Go", "Rust", "JavaScript", "C++"]},
        ]
        return [_normalize_company(c, "AI Discovery") for c in fallback]
