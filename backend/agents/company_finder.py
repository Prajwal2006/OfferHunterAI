"""
CompanyFinderAgent — Full production orchestrator for company discovery.

Orchestrates:
1. Resume parsing (if not already done)
2. Preference collection (conversational)
3. Multi-source company discovery (HN, RemoteOK, YC, AI)
4. Company ranking + scoring
5. Contact discovery per company
6. Persistence to Supabase

All steps emit real-time events via AgentEventLogger.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

# Support both direct and relative imports
try:
    from .event_logger import AgentEventLogger
    from ..services.resume_parser import ResumeParserService
    from ..services.preference_collector import PreferenceCollectorService
    from ..services.company_discovery import CompanyDiscoveryService
    from ..services.company_ranker import CompanyRankerService
    from ..services.contact_finder import ContactFinderService
    from ..db.supabase import supabase_client
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from backend.agents.event_logger import AgentEventLogger
    from backend.services.resume_parser import ResumeParserService
    from backend.services.preference_collector import PreferenceCollectorService
    from backend.services.company_discovery import CompanyDiscoveryService
    from backend.services.company_ranker import CompanyRankerService
    from backend.services.contact_finder import ContactFinderService
    from backend.db.supabase import supabase_client


class CompanyFinderAgent:
    """
    Full Company Finder Agent.

    Entry points:
    - run_full_pipeline(): resume parse → prefs → discover → rank → contacts
    - run_discovery_only(): skip resume/prefs, use provided profile + prefs
    - run_preference_chat(): single chat turn for preference collection
    """

    AGENT_NAME = "CompanyFinderAgent"

    def __init__(self, logger: AgentEventLogger) -> None:
        self.logger = logger
        self._resume_parser = ResumeParserService()
        self._preference_collector = PreferenceCollectorService()
        self._discovery = CompanyDiscoveryService()
        self._ranker = CompanyRankerService()
        self._contact_finder = ContactFinderService()

    # ─── Public Entry Points ──────────────────────────────────────────────────

    async def run(
        self,
        task_id: str,
        skills: list[str] | None = None,
        job_title: str = "",
        count: int = 10,
        user_id: str | None = None,
        resume_text: str | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Legacy compatibility entry point — runs discovery with minimal profile.
        """
        profile: dict[str, Any] = {
            "skills": skills or [],
            "tech_stack": skills or [],
            "preferred_domains": [job_title] if job_title else [],
            "keywords": skills or [],
        }
        preferences: dict[str, Any] = {
            "preferred_roles": [job_title] if job_title else [],
        }
        return await self.run_discovery_only(
            task_id=task_id,
            profile=profile,
            preferences=preferences,
            count=count,
            user_id=user_id,
        )

    async def run_full_pipeline(
        self,
        task_id: str,
        user_id: str,
        resume_text: str,
        preferences: dict[str, Any] | None = None,
        count: int = 25,
    ) -> dict[str, Any]:
        """
        Full pipeline: parse resume → (optionally use provided prefs) → discover → rank → contacts.
        Returns { profile, preferences, companies, run_id }
        """
        run_id = str(uuid.uuid4())

        await self._emit("started", task_id,
            f"Starting Company Finder Agent for user {user_id}",
            {"run_id": run_id})

        # ── Step 1: Parse Resume ──────────────────────────────────────────────
        await self._emit("running", task_id, "Parsing resume with AI...")
        profile = await self._resume_parser.parse(resume_text)
        profile["raw_text"] = resume_text

        # Persist parsed profile
        saved_profile = await supabase_client.upsert_parsed_profile({
            "user_id": user_id,
            **{k: v for k, v in profile.items() if k != "raw_text"},
            "raw_text": resume_text,
        })

        await self._emit("running", task_id,
            f"Resume parsed: {profile.get('full_name', 'User')} — {len(profile.get('skills', []))} skills extracted",
            {"skills_count": len(profile.get("skills", [])), "domains": profile.get("preferred_domains", [])})

        # ── Step 2: Use provided preferences or empty dict ────────────────────
        prefs = preferences or {}

        # ── Step 3: Discover companies ────────────────────────────────────────
        companies = await self._run_discovery(task_id, profile, prefs, count)

        # ── Step 4: Find contacts ─────────────────────────────────────────────
        companies = await self._run_contact_discovery(task_id, companies)

        # ── Step 5: Persist companies + rankings ──────────────────────────────
        companies = await self._persist_companies(task_id, user_id, companies)

        # Persist agent run
        await supabase_client.insert_agent_run({
            "id": run_id,
            "user_id": user_id,
            "agent_name": self.AGENT_NAME,
            "task_id": task_id,
            "status": "completed",
            "input": {"resume_length": len(resume_text), "count": count},
            "output": {"companies_found": len(companies)},
        })

        await self._emit("completed", task_id,
            f"Company Finder complete — {len(companies)} companies discovered and ranked",
            {
                "companies": companies,
                "company_names": [c["name"] for c in companies[:5]],
                "total": len(companies),
            })

        return {
            "run_id": run_id,
            "profile": saved_profile,
            "preferences": prefs,
            "companies": companies,
        }

    async def run_discovery_only(
        self,
        task_id: str,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        count: int = 25,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run discovery + ranking without the resume parse step.
        Used when a profile is already available.
        """
        await self._emit("started", task_id,
            f"Starting company discovery — {len(profile.get('skills', []))} skills, "
            f"{len(preferences.get('preferred_roles', []))} target roles")

        companies = await self._run_discovery(task_id, profile, preferences, count)
        companies = await self._run_contact_discovery(task_id, companies)

        if user_id:
            companies = await self._persist_companies(task_id, user_id, companies)

        await self._emit("completed", task_id,
            f"Discovery complete — {len(companies)} companies found",
            {
                "companies": companies,
                "company_names": [c["name"] for c in companies[:5]],
                "total": len(companies),
            })

        return companies

    async def run_preference_chat(
        self,
        task_id: str,
        user_id: str,
        user_message: str,
        history: list[dict[str, str]],
        profile: dict[str, Any],
        current_prefs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Single turn of the preference collection conversation.
        Returns { reply, preferences, is_complete }.
        """
        result = await self._preference_collector.chat(
            user_message=user_message,
            history=history,
            profile=profile,
            current_prefs=current_prefs,
        )

        if result.get("is_complete") and result.get("preferences") and user_id:
            await supabase_client.upsert_user_preferences({
                "user_id": user_id,
                "conversation_complete": True,
                **result["preferences"],
            })
            # Save conversation turn
            await supabase_client.insert_conversation_message(user_id, "user", user_message)
            await supabase_client.insert_conversation_message(user_id, "assistant", result["reply"])

        return result

    async def add_manual_company(
        self,
        task_id: str,
        user_id: str,
        website_url: str,
        profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build a company profile from a user-supplied website, rank it for the user,
        discover contacts, and persist it so the normal handoff flow can use it.
        """
        await self._emit("started", task_id, f"Profiling company website {website_url}")
        await self._emit("running", task_id, "Scraping company website and extracting profile...")

        company = await self._discovery.profile_company_website(website_url)

        await self._emit("running", task_id, f"Ranking {company.get('name', 'company')} against your profile...")
        ranked = await self._ranker.rank([company], profile=profile, preferences=preferences)
        ranked = await self._run_contact_discovery(task_id, ranked)
        ranked = await self._persist_companies(task_id, user_id, ranked)

        result = ranked[0]
        await self._emit(
            "completed",
            task_id,
            f"Added {result.get('name', 'company')} to your company list",
            {"companies": [result], "total": 1},
        )
        return result

    def get_preference_opener(self, profile: dict[str, Any]) -> str:
        """Return the initial preference collection message for a user."""
        return self._preference_collector.get_initial_message(profile)

    # ─── Internal Pipeline Steps ──────────────────────────────────────────────

    async def _run_discovery(
        self,
        task_id: str,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        count: int,
    ) -> list[dict[str, Any]]:
        async def progress_cb(source: str, message: str) -> None:
            await self._emit("running", task_id, message, {"source": source})

        await self._emit("running", task_id,
            "Searching across HackerNews, RemoteOK, Work at a Startup, Wellfound, YCombinator, and AI-powered discovery...")

        companies = await self._discovery.discover(
            profile=profile,
            preferences=preferences,
            target_count=count,
            progress_callback=progress_cb,
        )

        await self._emit("running", task_id,
            f"Ranking {len(companies)} companies by match score...")

        companies = await self._ranker.rank(
            companies=companies,
            profile=profile,
            preferences=preferences,
        )

        return companies

    async def _run_contact_discovery(
        self, task_id: str, companies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Find contacts for top companies (limit to top 10 to keep latency low)."""
        await self._emit("running", task_id,
            "Discovering recruiter and founder contacts for top companies...")

        top = companies[:10]
        contact_tasks = [self._contact_finder.find_contacts(c) for c in top]
        contact_results = await asyncio.gather(*contact_tasks, return_exceptions=True)

        for company, result in zip(top, contact_results):
            if isinstance(result, list):
                company["contacts"] = result
            else:
                company["contacts"] = []

        # Rest get empty contacts for now
        for company in companies[10:]:
            company.setdefault("contacts", [])

        return companies

    async def _persist_companies(
        self, task_id: str, user_id: str, companies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Upsert companies and rankings into Supabase."""
        await self._emit("running", task_id, "Saving companies and rankings to database...")

        persisted = []
        for company in companies:
            try:
                ranking = company.pop("ranking", {})
                contacts = company.pop("contacts", [])

                # Upsert company
                saved = await supabase_client.upsert_company({
                    **company,
                    "user_id": user_id,
                })
                company_id = saved.get("id") or company.get("id")
                company["id"] = company_id
                company["ranking"] = ranking
                company["contacts"] = contacts

                # Upsert ranking
                if company_id and ranking:
                    await supabase_client.upsert_company_ranking({
                        "user_id": user_id,
                        "company_id": company_id,
                        **ranking,
                    })

                # Insert contacts
                if company_id and contacts:
                    await supabase_client.insert_company_contacts(
                        company_id=company_id, contacts=contacts
                    )

                persisted.append(company)
            except Exception:
                company.setdefault("ranking", ranking if "ranking" in dir() else {})
                company.setdefault("contacts", contacts if "contacts" in dir() else [])
                persisted.append(company)

        return persisted

    # ─── Logging Helper ───────────────────────────────────────────────────────

    async def _emit(
        self,
        status: str,
        task_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status=status,
            message=message,
            metadata=metadata or {},
        )
