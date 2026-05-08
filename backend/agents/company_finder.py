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
from copy import deepcopy
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
    from ..services.background_jobs import (
        run_contact_worker,
        run_embedding_worker,
        run_enrichment_worker,
        run_ranking_worker,
    )
    from ..services.filters import apply_hard_constraints, normalize_preference_payload
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
    from backend.services.background_jobs import (
        run_contact_worker,
        run_embedding_worker,
        run_enrichment_worker,
        run_ranking_worker,
    )
    from backend.services.filters import apply_hard_constraints, normalize_preference_payload
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
        excluded_domains: set[str] | None = None,
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
        await self._emit(
            "running",
            task_id,
            "Parsing resume with AI...",
            {"stage": "resume_parse"},
        )
        profile = await asyncio.wait_for(self._resume_parser.parse(resume_text), timeout=90.0)
        profile["raw_text"] = resume_text

        # Persist parsed profile
        saved_profile = await supabase_client.upsert_parsed_profile({
            "user_id": user_id,
            **{k: v for k, v in profile.items() if k != "raw_text"},
            "raw_text": resume_text,
        })

        await self._emit(
            "running",
            task_id,
            f"Resume parsed: {profile.get('full_name', 'User')} — {len(profile.get('skills', []))} skills extracted",
            {
                "stage": "resume_parse",
                "skills_count": len(profile.get("skills", [])),
                "domains": profile.get("preferred_domains", []),
            },
        )

        # ── Step 2: Use provided preferences or empty dict ────────────────────
        prefs = preferences or {}

        # Learn from explicit like/dislike feedback and nudge future ranking/search.
        feedback_learning = await supabase_client.summarize_feedback_learning(user_id)
        prefs = self._merge_feedback_learning_into_preferences(prefs, feedback_learning)
        prefs["_feedback_learning"] = feedback_learning

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
        prefs_snapshot = {k: v for k, v in prefs.items() if not k.startswith("_")}
        discovery_session = await supabase_client.create_discovery_session({
            "user_id": user_id,
            "queries_used": profile.get("keywords", [])[:20],
            "preferences_snapshot": prefs_snapshot,
            "companies_found": 0,
            "total_companies_found": 0,
            "sources_searched": [],
            "sources_used": [],
            "embedding_version": "text-embedding-3-small",
            "status": "running",
        })
        discovery_session_id = discovery_session.get("id")
        prefs["_user_id"] = user_id
        prefs["_discovery_session_id"] = discovery_session_id

        companies, persistence_stats = await asyncio.wait_for(
            self._run_discovery_incrementally(
                task_id=task_id,
                user_id=user_id,
                profile=profile,
                preferences=prefs,
                count=count,
                discovery_session_id=discovery_session_id,
                manually_added=False,
                excluded_domains=excluded_domains,
            ),
            timeout=180.0,
        )

        await self._emit(
            "running",
            task_id,
            f"Discovery complete — {len(companies)} companies available now. Hydrating rankings and contacts in background...",
            {
                "stage": "persistence",
                "refresh_companies": True,
                "visible_companies": len(companies),
                "persistence": persistence_stats,
            },
        )

        if discovery_session_id:
            await supabase_client.update_discovery_session(discovery_session_id, {
                "status": "running",
                "companies_found": len(companies),
                "total_companies_found": len(companies),
                "sources_used": list({c.get("source") for c in companies if c.get("source")}),
            })

        asyncio.create_task(
            self._run_background_hydration(
                task_id=task_id,
                user_id=user_id,
                companies=companies,
                profile=profile,
                preferences=prefs,
                discovery_session_id=discovery_session_id,
                run_id=run_id,
                resume_text=resume_text,
                persistence_stats=persistence_stats,
            )
        )

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
        Run discovery-first without the resume parse step.
        Used when a profile is already available.
        """
        await self._emit("started", task_id,
            f"Starting company discovery — {len(profile.get('skills', []))} skills, "
            f"{len(preferences.get('preferred_roles', []))} target roles"
            + (f", excluding {len(excluded_domains)} already-known domains" if excluded_domains else ""))

        if user_id:
            feedback_learning = await supabase_client.summarize_feedback_learning(user_id)
            preferences = self._merge_feedback_learning_into_preferences(preferences, feedback_learning)
            preferences["_feedback_learning"] = feedback_learning
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "CompanyFinder",
                "active_agents": [self.AGENT_NAME],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {"step": "company_discovery", "percent": 0.25},
            })

        discovery_session_id = None
        if user_id:
            # Strip internal _ prefixed keys before persisting (they contain large sets/lists)
            prefs_snapshot = {k: v for k, v in preferences.items() if not k.startswith("_")}
            discovery_session = await supabase_client.create_discovery_session({
                "user_id": user_id,
                "queries_used": profile.get("keywords", [])[:20],
                "preferences_snapshot": prefs_snapshot,
                "companies_found": 0,
                "total_companies_found": 0,
                "sources_searched": [],
                "sources_used": [],
                "embedding_version": "text-embedding-3-small",
                "status": "running",
            })
            discovery_session_id = discovery_session.get("id")
            preferences["_user_id"] = user_id
            preferences["_discovery_session_id"] = discovery_session_id

        companies: list[dict[str, Any]] = []
        persistence_stats: dict[str, Any] = {"per_source": {}, "persisted": 0, "failed": 0}

        if user_id:
            companies, persistence_stats = await asyncio.wait_for(
                self._run_discovery_incrementally(
                    task_id=task_id,
                    user_id=user_id,
                    profile=profile,
                    preferences=preferences,
                    count=count,
                    discovery_session_id=discovery_session_id,
                    manually_added=False,
                    excluded_domains=excluded_domains,
                ),
                timeout=180.0,
            )

            await self._emit(
                "running",
                task_id,
                f"Discovered {len(companies)} companies and saved minimal records. Continuing hydration in background...",
                {
                    "stage": "persistence",
                    "refresh_companies": True,
                    "visible_companies": len(companies),
                    "persistence": persistence_stats,
                },
            )

            if discovery_session_id:
                await supabase_client.update_discovery_session(discovery_session_id, {
                    "status": "running",
                    "companies_found": len(companies),
                    "total_companies_found": len(companies),
                    "sources_used": list({c.get("source") for c in companies if c.get("source")}),
                })
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "CompanyFinder",
                "active_agents": [self.AGENT_NAME],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {
                    "step": "company_discovery_complete",
                    "percent": 0.55,
                    "companies_found": len(companies),
                },
            })

            asyncio.create_task(
                self._run_background_hydration(
                    task_id=task_id,
                    user_id=user_id,
                    companies=companies,
                    profile=profile,
                    preferences=preferences,
                    discovery_session_id=discovery_session_id,
                    run_id=None,
                    resume_text=None,
                    persistence_stats=persistence_stats,
                )
            )

        await self._emit("running", task_id,
            f"Discovery phase complete — {len(companies)} companies ready in workspace",
            {
                "user_id": user_id,
                "companies": companies,
                "company_names": [c["name"] for c in companies[:5]],
                "total": len(companies),
                "stage": "company_discovery",
                "refresh_companies": True,
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
        filtered = apply_hard_constraints([company], normalize_preference_payload(preferences))
        if not filtered:
            raise ValueError("This company does not satisfy the current hard preference constraints.")
        company = filtered[0]

        await self._emit("running", task_id, f"Ranking {company.get('name', 'company')} against your profile...")
        ranked = await self._ranker.rank([company], profile=profile, preferences=preferences)
        ranked = await self._run_contact_discovery(task_id, ranked)
        ranked, _ = await self._persist_companies(
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
                Discovery-first pipeline:
                    1. Query expansion
                    2. Multi-source parallel discovery
                    3. Dedup/filter + source telemetry

                Heavy hydration (enrichment, ranking, contacts, embeddings) is deferred
                to background workers so the request can return quickly.
        """
        async def progress_cb(source: str, message: str) -> None:
            stage = "query_expansion" if source == "QueryExpansion" else "company_discovery"
            await self._emit("running", task_id, message, {"source": source, "stage": stage})

        await self._emit(
            "running", task_id,
            "Expanding search queries with AI and searching across all sources...",
            {"stage": "query_expansion"},
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
            f"Discovered {len(companies)} unique companies — persisting minimal workspace records now",
            {"stage": "persistence", "discovered_count": len(companies)},
        )

        return companies

    async def _run_discovery_incrementally(
        self,
        *,
        task_id: str,
        user_id: str,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        count: int,
        discovery_session_id: Optional[str],
        manually_added: bool,
        excluded_domains: set[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Persist source batches as they complete so the UI can hydrate immediately."""
        visible_by_key: dict[str, dict[str, Any]] = {}
        aggregate_per_source: dict[str, dict[str, int]] = {}
        total_failed = 0

        async for batch in self._discovery.discover_stream(
            profile=profile,
            preferences=preferences,
            target_count=count,
            progress_callback=lambda source, message: self._emit(
                "running",
                task_id,
                message,
                {
                    "source": source,
                    "stage": "query_expansion" if source == "QueryExpansion" else "company_discovery",
                },
            ),
            excluded_domains=excluded_domains,
        ):
            source = str(batch.get("source") or "Unknown")
            source_companies = list(batch.get("companies") or [])
            source_counts = deepcopy(batch.get("counts") or {})

            persisted_batch, batch_stats = await self._persist_companies(
                task_id,
                user_id,
                source_companies,
                discovery_session_id=discovery_session_id,
                manually_added=manually_added,
                pipeline_metrics={source: source_counts},
            )

            aggregate_per_source[source] = deepcopy(batch_stats.get("per_source", {}).get(source) or source_counts)
            total_failed += int(batch_stats.get("failed") or 0)

            for company in persisted_batch:
                key = (
                    company.get("id")
                    or (company.get("domain") or "").lower().strip()
                    or (company.get("name") or "").lower().strip()
                )
                if key:
                    visible_by_key[str(key)] = company

            await self._emit(
                "running",
                task_id,
                f"{source}: {source_counts.get('raw_discovered', 0)} raw, {len(persisted_batch)} visible in workspace",
                {
                    "stage": "company_discovery",
                    "source": source,
                    "refresh_companies": True,
                    "source_counts": aggregate_per_source[source],
                    "visible_companies": len(visible_by_key),
                },
            )

            if discovery_session_id:
                await supabase_client.update_discovery_session(
                    discovery_session_id,
                    {
                        "status": "running",
                        "companies_found": len(visible_by_key),
                        "total_companies_found": len(visible_by_key),
                        "sources_used": sorted(aggregate_per_source.keys()),
                    },
                )

        return list(visible_by_key.values()), {
            "per_source": aggregate_per_source,
            "persisted": len(visible_by_key),
            "failed": total_failed,
        }

    async def _run_contact_discovery(
        self, task_id: str, companies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Find contacts for top companies (limit to top 10 to keep latency low)."""
        await self._emit(
            "running", task_id,
            "Discovering recruiter and founder contacts for top companies...",
            {"stage": "contact_discovery"},
        )

        top = companies[:10]
        contact_tasks = [
            asyncio.wait_for(self._contact_finder.find_contacts(c), timeout=20.0)
            for c in top
        ]
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
        pipeline_metrics: Optional[dict[str, dict[str, int]]] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Persist minimal company records quickly; defer heavy hydration to background workers."""
        await self._emit(
            "running",
            task_id,
            "Saving minimal company records to your workspace...",
            {"stage": "persistence"},
        )

        per_source = deepcopy(pipeline_metrics if pipeline_metrics is not None else self._discovery.last_pipeline_metrics)
        for counts in per_source.values():
            counts["persisted"] = 0
            counts["persistence_failed"] = 0
        persisted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for raw_company in companies:
            source = str(raw_company.get("source") or "Unknown")
            if source not in per_source:
                per_source[source] = {
                    "raw_discovered": 0,
                    "duplicates_removed": 0,
                    "already_seen_filtered": 0,
                    "ranking_filtered": 0,
                    "persistence_failed": 0,
                    "persisted": 0,
                    "industry_filtered": 0,
                }

            company = deepcopy(raw_company)
            ranking = deepcopy(company.get("ranking") or {})
            contacts = deepcopy(company.get("contacts") or [])

            if not company.get("domain"):
                company["domain"] = (
                    (company.get("website_url") or "")
                    .replace("https://", "")
                    .replace("http://", "")
                    .split("/")[0]
                    .strip()
                    or f"unknown-{company.get('name', 'co').lower().replace(' ', '-')}"
                )

            last_error: Exception | None = None
            max_retries = 2
            for attempt in range(1, max_retries + 1):
                try:
                    saved = await asyncio.wait_for(
                        supabase_client.upsert_company({
                            "name": company.get("name"),
                            "domain": company.get("domain"),
                            "source": company.get("source", "unknown"),
                            "website_url": company.get("website_url"),
                            "description": company.get("description", ""),
                            "industry": company.get("industry", ""),
                            "hiring_status": company.get("hiring_status", "unknown"),
                            "remote_friendly": company.get("remote_friendly"),
                            "open_positions": company.get("open_positions", []),
                            "metadata": {
                                "discovery_signals": company.get("discovery_signals", {}),
                                "source_url": company.get("source_url", ""),
                                "work_mode": company.get("work_mode", "unknown"),
                                "remote_confidence": company.get("remote_confidence", 0.0),
                                "work_mode_reasoning": company.get("work_mode_reasoning", []),
                                "preference_enforcement": company.get("preference_enforcement", {}),
                            },
                            "user_id": user_id,
                        }),
                        timeout=8.0,
                    )

                    company_id = saved.get("id") or company.get("id")
                    if not company_id:
                        raise ValueError(f"No company_id returned for {company.get('name')!r}")

                    company["id"] = company_id
                    company["ranking"] = ranking
                    company["contacts"] = contacts

                    await asyncio.wait_for(
                        supabase_client.upsert_user_company({
                            "user_id": user_id,
                            "company_id": company_id,
                            "discovery_session_id": discovery_session_id,
                            "source": source,
                            "status": "active",
                            "orchestration_stage": "CompanyFinder",
                            "manually_added": manually_added,
                            "personalization_completed": False,
                            "outreach_started": False,
                            "outreach_sent": False,
                            "ranking_score": 0,
                            "ranking_explanation": "Hydration in progress",
                            "ranking_metadata": {},
                            "application_strategy": "Hydration in progress",
                            "metadata": {
                                "domain": company.get("domain"),
                                "discovery_signals": company.get("discovery_signals", {}),
                                "work_mode": company.get("work_mode", "unknown"),
                                "remote_confidence": company.get("remote_confidence", 0.0),
                                "work_mode_reasoning": company.get("work_mode_reasoning", []),
                                "preference_enforcement": company.get("preference_enforcement", {}),
                                "minimal_persisted_at": datetime.utcnow().isoformat(),
                            },
                        }),
                        timeout=8.0,
                    )

                    per_source[source]["persisted"] = per_source[source].get("persisted", 0) + 1
                    persisted.append(company)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if last_error is not None:
                reason = self._classify_persistence_failure(last_error)
                per_source[source]["persistence_failed"] = per_source[source].get("persistence_failed", 0) + 1
                company["_persistence_error"] = f"{type(last_error).__name__}: {last_error}"
                company["_persistence_failure_reason"] = reason
                failed.append(company)

        for source, counts in per_source.items():
            try:
                await supabase_client.update_discovery_source_log_counts(
                    user_id=user_id,
                    discovery_session_id=discovery_session_id,
                    source=source,
                    counts=counts,
                )
            except Exception:
                continue

        if failed:
            await self._emit(
                "running",
                task_id,
                f"Persistence diagnostics: {len(failed)} failures, {len(persisted)} saved",
                {
                    "stage": "persistence",
                    "failed_count": len(failed),
                    "persisted_count": len(persisted),
                    "failures": [
                        {
                            "company": c.get("name"),
                            "reason": c.get("_persistence_failure_reason"),
                            "error": c.get("_persistence_error"),
                        }
                        for c in failed[:12]
                    ],
                },
            )

            if not persisted and companies:
                raise RuntimeError("No discovered companies could be saved to the persistent workspace")

        return persisted, {
            "per_source": per_source,
            "persisted": len(persisted),
            "failed": len(failed),
        }

    async def _run_background_hydration(
        self,
        *,
        task_id: str,
        user_id: str,
        companies: list[dict[str, Any]],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        discovery_session_id: Optional[str],
        run_id: Optional[str],
        resume_text: Optional[str],
        persistence_stats: dict[str, Any],
    ) -> None:
        """Hydrate companies asynchronously after discovery-first persistence."""
        hydrated = list(companies)
        per_source = deepcopy(persistence_stats.get("per_source") or {})
        stage_failures: list[str] = []

        await self._emit(
            "running",
            task_id,
            "Background hydration started: enrichment, ranking, contacts, and embeddings",
            {"stage": "background_hydration", "refresh_companies": True},
        )

        try:
            await self._emit("running", task_id, "Enrichment worker running...", {"stage": "enrichment"})
            hydrated = await run_enrichment_worker(companies=hydrated, profile=profile)
            await self._emit(
                "running",
                task_id,
                f"Enrichment completed for {len(hydrated)} companies",
                {"stage": "enrichment", "refresh_companies": True},
            )
        except Exception as exc:
            stage_failures.append(f"enrichment:{type(exc).__name__}")
            await self._emit("running", task_id, f"Enrichment worker degraded: {exc}", {"stage": "enrichment"})

        try:
            await self._emit("running", task_id, "Ranking worker running...", {"stage": "ranking"})
            hydrated = await run_ranking_worker(
                companies=hydrated,
                profile=profile,
                preferences=preferences,
            )
            for company in hydrated:
                company_id = company.get("id")
                ranking = company.get("ranking") or {}
                if not company_id:
                    continue
                await supabase_client.upsert_user_company({
                    "user_id": user_id,
                    "company_id": company_id,
                    "discovery_session_id": discovery_session_id,
                    "source": company.get("source", "unknown"),
                    "status": "active",
                    "orchestration_stage": "Personalization",
                    "ranking_score": ranking.get("match_score", company.get("relevance_score", 0)),
                    "ranking_explanation": ranking.get("match_explanation", ""),
                    "ranking_metadata": ranking,
                    "metadata": {
                        "domain": company.get("domain"),
                        "extended_ranking": company.get("extended_ranking", {}),
                        "discovery_signals": company.get("discovery_signals", {}),
                    },
                })
                if ranking:
                    await supabase_client.upsert_company_ranking({
                        "user_id": user_id,
                        "company_id": company_id,
                        **ranking,
                    })
            await self._emit(
                "running",
                task_id,
                f"Ranking completed for {len(hydrated)} companies",
                {"stage": "ranking", "refresh_companies": True},
            )
        except Exception as exc:
            stage_failures.append(f"ranking:{type(exc).__name__}")
            await self._emit("running", task_id, f"Ranking worker degraded: {exc}", {"stage": "ranking"})

        try:
            await self._emit("running", task_id, "Contact worker running...", {"stage": "contact_discovery"})
            hydrated = await run_contact_worker(companies=hydrated, top_n=min(15, len(hydrated)))
            for company in hydrated:
                company_id = company.get("id")
                contacts = company.get("contacts") or []
                if company_id and contacts:
                    await supabase_client.insert_company_contacts(company_id=company_id, contacts=contacts)
                    await supabase_client.upsert_user_company({
                        "user_id": user_id,
                        "company_id": company_id,
                        "source": company.get("source", "unknown"),
                        "status": "active",
                        "orchestration_stage": "Personalization",
                        "application_strategy": self._derive_application_strategy(company, contacts),
                    })
            await self._emit(
                "running",
                task_id,
                "Contact discovery completed",
                {"stage": "contact_discovery", "refresh_companies": True},
            )
        except Exception as exc:
            stage_failures.append(f"contacts:{type(exc).__name__}")
            await self._emit("running", task_id, f"Contact worker degraded: {exc}", {"stage": "contact_discovery"})

        try:
            await self._emit("running", task_id, "Embedding worker running...", {"stage": "embeddings"})
            embeddings = await run_embedding_worker(companies=hydrated)
            for company in hydrated:
                key = (company.get("domain") or company.get("id") or company.get("name") or "").lower().strip()
                embedding = embeddings.get(key)
                if not embedding:
                    continue
                await supabase_client.upsert_company_embedding({
                    "company_id": company.get("id"),
                    "domain": company.get("domain"),
                    "embedding": embedding,
                    "model": "text-embedding-3-small",
                })
            await self._emit("running", task_id, "Embedding generation completed", {"stage": "embeddings"})
        except Exception as exc:
            stage_failures.append(f"embeddings:{type(exc).__name__}")
            await self._emit("running", task_id, f"Embedding worker degraded: {exc}", {"stage": "embeddings"})

        if discovery_session_id:
            await supabase_client.update_discovery_session(discovery_session_id, {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "companies_found": len(hydrated),
                "total_companies_found": len(hydrated),
                "sources_used": list({c.get("source") for c in hydrated if c.get("source")}),
            })

        for source, counts in per_source.items():
            counts["ranking_filtered"] = counts.get("ranking_filtered", 0)
            counts["persisted"] = max(0, counts.get("persisted", 0))
            try:
                await supabase_client.update_discovery_source_log_counts(
                    user_id=user_id,
                    discovery_session_id=discovery_session_id,
                    source=source,
                    counts=counts,
                )
            except Exception:
                continue

        await supabase_client.upsert_orchestration_state({
            "user_id": user_id,
            "current_stage": "Personalization" if hydrated else "CompanyFinder",
            "active_agents": [],
            "paused_state": False,
            "last_task_id": task_id,
            "progress": {
                "step": "company_discovery_complete",
                "percent": 1.0,
                "companies_found": len(hydrated),
                "background_failures": stage_failures,
            },
        })

        if run_id:
            await supabase_client.insert_agent_run({
                "id": run_id,
                "user_id": user_id,
                "agent_name": self.AGENT_NAME,
                "task_id": task_id,
                "status": "completed" if not stage_failures else "partial",
                "input": {"resume_length": len(resume_text or ""), "count": len(companies)},
                "output": {
                    "companies_found": len(hydrated),
                    "background_failures": stage_failures,
                },
            })

        await self._emit(
            "completed",
            task_id,
            f"Company Finder complete — {len(hydrated)} companies hydrated",
            {
                "user_id": user_id,
                "companies": hydrated,
                "company_names": [c["name"] for c in hydrated[:5] if c.get("name")],
                "total": len(hydrated),
                "refresh_companies": True,
                "source_metrics": per_source,
                "background_failures": stage_failures,
            },
        )

    @staticmethod
    def _classify_persistence_failure(exc: Exception) -> str:
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message or "conflict" in message:
            return "duplicate constraint"
        if "domain" in message and ("invalid" in message or "unknown" in message):
            return "invalid domain"
        if "timeout" in message:
            return "timeout"
        if "metadata" in message or "json" in message:
            return "malformed metadata"
        if "embedding" in message:
            return "embedding timeout"
        return "unknown persistence error"

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
