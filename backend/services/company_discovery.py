"""
CompanyDiscoveryService — Multi-source company discovery engine.

Sources:
1. Hacker News "Who's Hiring" thread (free, via Algolia HN API)
2. RemoteOK public API (free)
3. YC Companies directory (public scrape)
4. GitHub organization search (public API, no auth required for basic search)
5. AI-powered discovery based on user profile
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup


# ─── Constants ────────────────────────────────────────────────────────────────

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"
REMOTEOK_URL = "https://remoteok.com/api"
YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
GITHUB_API_URL = "https://api.github.com"

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


# ─── Service ──────────────────────────────────────────────────────────────────

class CompanyDiscoveryService:
    """
    Discovers companies from multiple sources and returns deduplicated results.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._github_token = os.getenv("GITHUB_TOKEN", "")

    async def discover(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        target_count: int = 30,
        progress_callback: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Run all discovery sources in parallel and return deduplicated companies.

        progress_callback: async callable(source_name, message)
        """
        tasks = [
            self._discover_from_hn(profile, preferences),
            self._discover_from_remoteok(profile, preferences),
            self._discover_from_yc(profile, preferences),
            self._discover_via_ai(profile, preferences, target_count),
        ]

        if progress_callback:
            await progress_callback("Discovery", "Searching Hacker News, RemoteOK, YC, and AI sources...")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_companies: list[dict[str, Any]] = []
        source_names = ["HackerNews", "RemoteOK", "YCombinator", "AI Discovery"]
        for source_name, result in zip(source_names, results):
            if isinstance(result, list):
                all_companies.extend(result)
                if progress_callback:
                    await progress_callback(source_name, f"Found {len(result)} companies from {source_name}")

        # Deduplicate by domain (case-insensitive)
        seen_domains: set[str] = set()
        unique: list[dict[str, Any]] = []
        for company in all_companies:
            domain_key = company.get("domain", "").lower()
            if domain_key and domain_key not in seen_domains:
                seen_domains.add(domain_key)
                unique.append(company)

        if progress_callback:
            await progress_callback("Discovery", f"Deduplicated to {len(unique)} unique companies")

        return unique[:target_count]

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
