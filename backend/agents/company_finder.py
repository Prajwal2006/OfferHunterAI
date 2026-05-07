"""
CompanyFinderAgent — Full production orchestrator for company discovery.

Orchestrates:
1. Resume parsing (if not already done)
2. Preference collection (conversational)
3. AI query expansion
4. Multi-source company discovery (HN, RemoteOK, YC, Wellfound, WorkAtAStartup, AI)
5. Company enrichment (GitHub signals, hiring velocity, tech stack)
6. Intelligent ranking with semantic embeddings
7. Contact discovery per company
8. Persistence to Supabase

All steps emit real-time events via AgentEventLogger.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Support both direct and relative imports
try:
    from .event_logger import AgentEventLogger
    from ..services.resume_parser import ResumeParserService
    from ..services.preference_collector import PreferenceCollectorService
    from ..services.company_discovery import CompanyDiscoveryService
    from ..services.company_ranker import CompanyRankerService
    from ..services.company_enrichment import CompanyEnrichmentService
    from ..services.company_scoring import CompanyScoringService
    from ..services.contact_finder import ContactFinderService
    from ..db.supabase import supabase_client
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from backend.agents.event_logger import AgentEventLogger
    from backend.services.resume_parser import ResumeParserService
    from backend.services.preference_collector import PreferenceCollectorService
    from backend.services.company_discovery import CompanyDiscoveryService
    from backend.services.company_ranker import CompanyRankerService
    from backend.services.company_enrichment import CompanyEnrichmentService
    from backend.services.company_scoring import CompanyScoringService
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
        self._enricher = CompanyEnrichmentService()
        self._scorer = CompanyScoringService()
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

        await supabase_client.upsert_orchestration_state({
            "user_id": user_id,
            "current_stage": "CompanyFinder",
            "active_agents": [self.AGENT_NAME],
            "paused_state": False,
            "last_task_id": task_id,
            "progress": {
                "step": "resume_parse",
                "completed_steps": [],
                "percent": 0.1,
            },
        })

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

        # Learn from explicit like/dislike feedback and nudge future ranking/search.
        feedback_learning = await supabase_client.summarize_feedback_learning(user_id)
        prefs = self._merge_feedback_learning_into_preferences(prefs, feedback_learning)

        await supabase_client.upsert_orchestration_state({
            "user_id": user_id,
            "current_stage": "CompanyFinder",
            "active_agents": [self.AGENT_NAME],
            "paused_state": False,
            "last_task_id": task_id,
            "progress": {
                "step": "company_discovery",
                "completed_steps": ["resume_parse"],
                "percent": 0.35,
                "feedback_learning": feedback_learning,
            },
        })

        # ── Step 3: Discover companies ────────────────────────────────────────
        companies = await self._run_discovery(task_id, profile, prefs, count)

        prefs_snapshot = {k: v for k, v in prefs.items() if not k.startswith("_")}
        discovery_session = await supabase_client.create_discovery_session({
            "user_id": user_id,
            "queries_used": profile.get("keywords", [])[:20],
            "preferences_snapshot": prefs_snapshot,
            "companies_found": len(companies),
            "total_companies_found": len(companies),
            "sources_searched": [c.get("source") for c in companies if c.get("source")],
            "sources_used": list({c.get("source") for c in companies if c.get("source")}),
            "embedding_version": "text-embedding-3-small",
            "status": "running",
        })
        discovery_session_id = discovery_session.get("id")

        await supabase_client.upsert_orchestration_state({
            "user_id": user_id,
            "current_stage": "Personalization" if companies else "CompanyFinder",
            "active_agents": [self.AGENT_NAME],
            "paused_state": False,
            "last_task_id": task_id,
            "progress": {
                "step": "contact_discovery",
                "completed_steps": ["resume_parse", "company_discovery"],
                "percent": 0.65,
                "companies_found": len(companies),
            },
        })

        # ── Step 4: Find contacts ─────────────────────────────────────────────
        companies = await self._run_contact_discovery(task_id, companies)

        # ── Step 5: Persist companies + rankings ──────────────────────────────
        companies = await self._persist_companies(
            task_id,
            user_id,
            companies,
            discovery_session_id=discovery_session_id,
            manually_added=False,
        )

        if discovery_session_id:
            await supabase_client.update_discovery_session(discovery_session_id, {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "companies_found": len(companies),
                "total_companies_found": len(companies),
                "sources_used": list({c.get("source") for c in companies if c.get("source")}),
            })

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

        await supabase_client.upsert_orchestration_state({
            "user_id": user_id,
            "current_stage": "Personalization" if companies else "CompanyFinder",
            "active_agents": [],
            "paused_state": False,
            "last_task_id": task_id,
            "progress": {
                "step": "company_discovery_complete",
                "completed_steps": ["resume_parse", "company_discovery", "contact_discovery"],
                "percent": 1.0,
                "companies_found": len(companies),
            },
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
        excluded_domains: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run discovery + ranking without the resume parse step.
        Used when a profile is already available.
        """
        await self._emit("started", task_id,
            f"Starting company discovery — {len(profile.get('skills', []))} skills, "
            f"{len(preferences.get('preferred_roles', []))} target roles"
            + (f", excluding {len(excluded_domains)} already-known domains" if excluded_domains else ""))

        if user_id:
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "CompanyFinder",
                "active_agents": [self.AGENT_NAME],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {"step": "company_discovery", "percent": 0.25},
            })

        companies = await self._run_discovery(task_id, profile, preferences, count, excluded_domains=excluded_domains)
        companies = await self._run_contact_discovery(task_id, companies)

        if user_id:
            # Strip internal _ prefixed keys before persisting (they contain large sets/lists)
            prefs_snapshot = {k: v for k, v in preferences.items() if not k.startswith("_")}
            discovery_session = await supabase_client.create_discovery_session({
                "user_id": user_id,
                "queries_used": profile.get("keywords", [])[:20],
                "preferences_snapshot": prefs_snapshot,
                "companies_found": len(companies),
                "total_companies_found": len(companies),
                "sources_searched": [c.get("source") for c in companies if c.get("source")],
                "sources_used": list({c.get("source") for c in companies if c.get("source")}),
                "embedding_version": "text-embedding-3-small",
                "status": "completed",
            })
            companies = await self._persist_companies(
                task_id,
                user_id,
                companies,
                discovery_session_id=discovery_session.get("id"),
                manually_added=False,
            )
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "Personalization" if companies else "CompanyFinder",
                "active_agents": [],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {
                    "step": "company_discovery_complete",
                    "percent": 1.0,
                    "companies_found": len(companies),
                },
            })

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
        ranked = await self._persist_companies(
            task_id,
            user_id,
            ranked,
            discovery_session_id=None,
            manually_added=True,
        )

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
        excluded_domains: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Full discovery pipeline:
          1. Query expansion
          2. Multi-source parallel discovery
          3. Company enrichment (top N, non-blocking)
          4. Semantic + weighted ranking
          5. Extended scoring (growth, funding recency, AI adoption)
        """
        async def progress_cb(source: str, message: str) -> None:
            await self._emit("running", task_id, message, {"source": source})

        await self._emit(
            "running", task_id,
            "Expanding search queries with AI and searching across all sources...",
        )

        # ── Multi-source discovery with query expansion + feedback loop ────────
        companies = await self._discovery.discover(
            profile=profile,
            preferences=preferences,
            target_count=count,
            progress_callback=progress_cb,
            excluded_domains=excluded_domains,
        )

        await self._emit(
            "running", task_id,
            f"Discovered {len(companies)} unique companies — starting enrichment...",
            {"discovered_count": len(companies)},
        )

        # ── Enrich top companies with hiring signals + GitHub stats ────────────
        enriched_count = min(len(companies), 20)
        try:
            companies = await self._enricher.batch_enrich(
                companies, profile=profile, max_concurrent=5, top_n=enriched_count
            )
            await self._emit(
                "running", task_id,
                f"Enriched top {enriched_count} companies with hiring signals and tech data",
                {"enriched_count": enriched_count},
            )
        except Exception as exc:
            await self._emit("running", task_id, f"Enrichment partial: {exc}")

        # ── Semantic + weighted ranking ────────────────────────────────────────
        await self._emit(
            "running", task_id,
            f"Ranking {len(companies)} companies using semantic embeddings + {len(profile.get('skills', []))} skill signals...",
        )

        companies = await self._ranker.rank(
            companies=companies,
            profile=profile,
            preferences=preferences,
        )

        # ── Extended scoring (growth velocity, funding recency) ────────────────
        # Build map of base signal scores for the extended scorer
        base_rankings = {
            (c.get("domain") or "").lower(): c.get("ranking", {})
            for c in companies
        }
        semantic_scores = {
            (c.get("domain") or "").lower(): c.get("ranking", {}).get("semantic_similarity", 0.5)
            for c in companies
        }

        companies = self._scorer.score_companies(
            companies=companies,
            profile=profile,
            preferences=preferences,
            semantic_scores=semantic_scores,
            base_rankings=base_rankings,
        )

        # Emit ranking transparency for top 3
        top3 = companies[:3]
        for company in top3:
            ext = company.get("extended_ranking", {})
            strengths = ext.get("strengths", [])
            score = ext.get("weighted_total", company.get("relevance_score", 0))
            await self._emit(
                "running", task_id,
                f"Ranked: {company.get('name', '?')} — score {score:.2f} "
                f"({', '.join(strengths[:2]) if strengths else 'no strong signals'})",
                {
                    "source": "Ranking",
                    "company": company.get("name"),
                    "score": score,
                    "strengths": strengths[:3],
                    "semantic_similarity": ext.get("semantic_similarity", 0),
                    "growth_velocity": ext.get("growth_velocity", 0),
                },
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
        self,
        task_id: str,
        user_id: str,
        companies: list[dict[str, Any]],
        discovery_session_id: Optional[str],
        manually_added: bool,
    ) -> list[dict[str, Any]]:
        """Upsert companies and rankings into Supabase."""
        await self._emit("running", task_id, "Saving companies and rankings to database...")

        persisted = []
        for company in companies:
            ranking: dict[str, Any] = {}
            contacts: list = []
            try:
                ranking = company.pop("ranking", {})
                contacts = company.pop("contacts", [])

                # domain is required for the companies table unique constraint
                if not company.get("domain"):
                    company["domain"] = (
                        (company.get("website_url") or "")
                        .replace("https://", "")
                        .replace("http://", "")
                        .split("/")[0]
                        .strip()
                        or f"unknown-{company.get('name', 'co').lower().replace(' ', '-')}"
                    )

                # Upsert company (shared company record, keyed by domain)
                saved = await supabase_client.upsert_company({
                    **company,
                    "user_id": user_id,
                })
                company_id = saved.get("id") or company.get("id")
                if not company_id:
                    raise ValueError(f"No company_id returned for {company.get('name')!r}")

                company["id"] = company_id
                company["ranking"] = ranking
                company["contacts"] = contacts

                # Upsert ranking
                if ranking:
                    await supabase_client.upsert_company_ranking({
                        "user_id": user_id,
                        "company_id": company_id,
                        **ranking,
                    })

                # Insert contacts
                if contacts:
                    await supabase_client.insert_company_contacts(
                        company_id=company_id, contacts=contacts
                    )

                application_strategy = self._derive_application_strategy(company, contacts)
                await supabase_client.upsert_user_company({
                    "user_id": user_id,
                    "company_id": company_id,
                    "discovery_session_id": discovery_session_id,
                    "source": company.get("source", "unknown"),
                    "status": "active",
                    "orchestration_stage": "Personalization",
                    "manually_added": manually_added,
                    "personalization_completed": False,
                    "outreach_started": False,
                    "outreach_sent": False,
                    "ranking_score": ranking.get("match_score", company.get("relevance_score", 0)),
                    "ranking_explanation": ranking.get("match_explanation", ""),
                    "ranking_metadata": ranking,
                    "application_strategy": application_strategy,
                    "metadata": {
                        "extended_ranking": company.get("extended_ranking", {}),
                        "domain": company.get("domain"),
                    },
                })

                persisted.append(company)
            except Exception as exc:
                # Log the failure so it's visible in the SSE stream for debugging
                await self._emit(
                    "running", task_id,
                    f"Warning: could not persist '{company.get('name', '?')}' — {exc}",
                )
                company["ranking"] = ranking
                company["contacts"] = contacts
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

    @staticmethod
    def _merge_feedback_learning_into_preferences(
        preferences: dict[str, Any],
        learning: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(preferences)

        preferred_industries = list(merged.get("industries_of_interest", []) or [])
        for industry in learning.get("liked_industries", []):
            if industry not in preferred_industries:
                preferred_industries.append(industry)
        merged["industries_of_interest"] = preferred_industries

        avoided_industries = list(merged.get("avoided_industries", []) or [])
        for industry in learning.get("disliked_industries", []):
            if industry not in avoided_industries:
                avoided_industries.append(industry)
        merged["avoided_industries"] = avoided_industries

        preferred_stack = list(merged.get("preferred_tech_stack", []) or [])
        for tech in learning.get("liked_tech", []):
            if tech not in preferred_stack:
                preferred_stack.append(tech)
        merged["preferred_tech_stack"] = preferred_stack

        return merged

    @staticmethod
    def _derive_application_strategy(
        company: dict[str, Any],
        contacts: list[dict[str, Any]],
    ) -> str:
        titles = " ".join((c.get("title") or "").lower() for c in contacts)
        has_founder = any((c.get("contact_type") or "") == "founder" for c in contacts)
        has_recruiter = any((c.get("contact_type") or "") in {"recruiter", "hr"} for c in contacts)
        has_hiring_manager = "engineering manager" in titles or any(
            (c.get("contact_type") or "") == "hiring_manager" for c in contacts
        )
        stage = (company.get("funding_stage") or "").lower()

        if has_founder and any(x in stage for x in ["seed", "series a", "yc"]):
            return "Cold email founder with product + execution proof, then apply through careers page"
        if has_hiring_manager:
            return "Reach out directly to the hiring manager with a tailored project case study"
        if has_recruiter:
            return "Apply through careers page first, then send a concise recruiter follow-up"
        if company.get("source") == "YCombinator":
            return "Apply via YC jobs and follow up with a founder-focused intro email"
        if company.get("source") == "RemoteOK":
            return "Apply through remote role listing and include async collaboration examples"
        return "Apply on careers page, then send a personalized outreach email to engineering leadership"
