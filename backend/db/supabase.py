"""
Supabase database client for OfferHunter AI.
"""
import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


class SupabaseClient:
    """
    Async Supabase client wrapper.
    Falls back gracefully when SUPABASE_URL is not configured.
    """

    def __init__(self):
        self._url = os.getenv("SUPABASE_URL", "")
        self._key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None and self._url and self._key:
            try:
                from supabase import create_client
                self._client = create_client(self._url, self._key)
            except Exception:
                pass
        return self._client

    # ─── Agent Events ─────────────────────────────────────────────────────────

    async def insert_agent_event(self, event: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return event
        result = client.table("agent_events").insert(event).execute()
        return result.data[0] if result.data else event

    async def get_agent_events(
        self,
        limit: int = 50,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []

        query = (
            client.table("agent_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if agent_name:
            query = query.eq("agent_name", agent_name)
        if status:
            query = query.eq("status", status)

        result = query.execute()
        return result.data or []

    # ─── Emails ───────────────────────────────────────────────────────────────

    async def insert_email(self, email: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return email
        result = client.table("emails").insert(email).execute()
        return result.data[0] if result.data else email

    async def get_email(self, email_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("emails").select("*").eq("id", email_id).single().execute()
        )
        return result.data

    async def get_emails(self, status: Optional[str] = None) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        query = client.table("emails").select("*").order("created_at", desc=True)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return result.data or []

    async def update_email(self, email_id: str, updates: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return {"id": email_id, **updates}
        result = (
            client.table("emails").update(updates).eq("id", email_id).execute()
        )
        return result.data[0] if result.data else {}

    # ─── Outreach Drafts / Personalization Profiles ─────────────────────────

    async def upsert_personalization_profile(self, profile: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return profile
        result = (
            client.table("personalization_profiles")
            .upsert(profile, on_conflict="user_id,company_id")
            .execute()
        )
        return result.data[0] if result.data else profile

    async def get_personalization_profile(self, user_id: str, company_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("personalization_profiles")
            .select("*")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None

    async def upsert_email_draft(self, draft: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            draft.setdefault("version_number", 1)
            return draft
        result = (
            client.table("email_drafts")
            .upsert(draft, on_conflict="user_id,company_id")
            .execute()
        )
        return result.data[0] if result.data else draft

    async def insert_email_draft(self, draft: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            draft.setdefault("version_number", 1)
            return draft
        result = client.table("email_drafts").insert(draft).execute()
        return result.data[0] if result.data else draft

    async def get_email_draft(self, draft_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("email_drafts")
            .select("*")
            .eq("id", draft_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None

    async def get_email_draft_for_company(self, user_id: str, company_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("email_drafts")
            .select("*")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None

    async def get_email_drafts(self, user_id: str, status: Optional[str] = None) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        query = (
            client.table("email_drafts")
            .select("*, companies(name, domain, industry, logo_url)")
            .eq("user_id", user_id)
            .order("last_edited_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return result.data or []

    async def update_email_draft(self, draft_id: str, updates: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return {"id": draft_id, **updates}
        result = (
            client.table("email_drafts")
            .update(updates)
            .eq("id", draft_id)
            .execute()
        )
        return result.data[0] if result.data else {"id": draft_id, **updates}

    async def insert_email_version(self, version: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return version
        result = client.table("email_versions").insert(version).execute()
        return result.data[0] if result.data else version

    async def get_email_versions(self, draft_id: str) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("email_versions")
            .select("*")
            .eq("draft_id", draft_id)
            .order("version_number", desc=True)
            .execute()
        )
        return result.data or []

    async def get_email_version(self, version_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("email_versions")
            .select("*")
            .eq("id", version_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None

    async def insert_generated_subjects(self, draft_id: str, subjects: list[dict[str, Any]]) -> list[dict]:
        rows = [{"draft_id": draft_id, **subject} for subject in subjects]
        client = self._get_client()
        if not client:
            return rows
        result = client.table("generated_subjects").insert(rows).execute()
        return result.data or rows

    async def get_generated_subjects(self, draft_id: str) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("generated_subjects")
            .select("*")
            .eq("draft_id", draft_id)
            .order("created_at")
            .execute()
        )
        return result.data or []

    async def insert_ai_edit_request(self, request: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return request
        result = client.table("ai_edit_requests").insert(request).execute()
        return result.data[0] if result.data else request

    async def update_ai_edit_request(self, request_id: str, updates: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return {"id": request_id, **updates}
        result = (
            client.table("ai_edit_requests")
            .update(updates)
            .eq("id", request_id)
            .execute()
        )
        return result.data[0] if result.data else {"id": request_id, **updates}

    async def insert_edit_history(self, row: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return row
        result = client.table("edit_history").insert(row).execute()
        return result.data[0] if result.data else row

    async def upsert_outreach_contacts(self, contacts: list[dict[str, Any]]) -> list[dict]:
        client = self._get_client()
        if not client:
            return contacts
        if not contacts:
            return []
        result = (
            client.table("outreach_contacts")
            .upsert(contacts, on_conflict="user_id,company_id,email")
            .execute()
        )
        return result.data or contacts

    async def get_outreach_contacts(self, user_id: str, company_id: str) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("outreach_contacts")
            .select("*")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .order("priority_score", desc=True)
            .execute()
        )
        return result.data or []

    # ─── Resume Versions ─────────────────────────────────────────────────────

    async def insert_resume(self, resume: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return resume
        result = client.table("resume_versions").insert(resume).execute()
        return result.data[0] if result.data else resume

    async def get_resumes(self, user_id: str) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("resume_versions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    async def get_resume(self, resume_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("resume_versions")
            .select("*")
            .eq("id", resume_id)
            .single()
            .execute()
        )
        return result.data

    async def set_active_resume(self, user_id: str, resume_id: str) -> dict:
        client = self._get_client()
        if not client:
            return {"id": resume_id, "is_active": True}

        client.table("resume_versions").update({"is_active": False}).eq(
            "user_id", user_id
        ).execute()
        result = (
            client.table("resume_versions")
            .update({"is_active": True})
            .eq("id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    async def get_active_resume(self, user_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("resume_versions")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None

    async def delete_resume(self, user_id: str, resume_id: str) -> dict:
        client = self._get_client()
        if not client:
            return {"id": resume_id, "deleted": True}
        result = (
            client.table("resume_versions")
            .delete()
            .eq("id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )
        return {"deleted": True, "data": result.data or []}

    # ─── Companies ────────────────────────────────────────────────────────────

    async def insert_company(self, company: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return company
        result = client.table("companies").insert(company).execute()
        return result.data[0] if result.data else company

    async def get_companies(self) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("companies")
            .select("*")
            .order("relevance_score", desc=True)
            .execute()
        )
        return result.data or []

    # ─── Pipeline ─────────────────────────────────────────────────────────────

    async def get_pipeline(self) -> list[dict]:
        """Get companies with their associated emails for pipeline view."""
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("companies")
            .select("*, emails(*)")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    # ─── Parsed Profiles ──────────────────────────────────────────────────────

    async def upsert_parsed_profile(self, profile: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return profile
        result = (
            client.table("parsed_profiles")
            .upsert(profile, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else profile

    async def get_parsed_profile(self, user_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("parsed_profiles")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None

    # ─── User Preferences ─────────────────────────────────────────────────────

    async def upsert_user_preferences(self, prefs: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return prefs
        result = (
            client.table("user_preferences")
            .upsert(prefs, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else prefs

    async def get_user_preferences(self, user_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("user_preferences")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None

    # ─── Enhanced Companies ───────────────────────────────────────────────────

    async def upsert_company(self, company: dict[str, Any]) -> dict:
        """Upsert a company by domain (shared company catalog)."""
        client = self._get_client()
        if not client:
            import uuid as _uuid
            company.setdefault("id", str(_uuid.uuid4()))
            return company

        # Strip keys that are not columns to avoid 400 errors
        safe_keys = {
            "id", "name", "domain", "industry", "size",
            "relevance_score", "status", "metadata", "logo_url", "description",
            "mission", "tech_stack", "funding_stage", "founded_year",
            "hiring_status", "sponsorship_available", "remote_friendly",
            "open_positions", "recent_news", "culture_tags", "headquarters",
            "website_url", "linkedin_url", "glassdoor_url", "crunchbase_url",
            "source", "source_url", "last_scraped_at",
        }
        clean = {k: v for k, v in company.items() if k in safe_keys}
        clean.setdefault("status", "discovered")
        clean.setdefault("relevance_score", 0.5)

        # Try upsert with UNIQUE(domain) constraint first (requires migration 005).
        # If the constraint doesn't exist yet, fall back to insert-or-select.
        try:
            result = (
                client.table("companies")
                .upsert(clean, on_conflict="domain")
                .execute()
            )
            return result.data[0] if result.data else clean
        except Exception:
            pass

        # Fallback: check if a company with this domain already exists
        domain = clean.get("domain")
        if domain:
            try:
                existing = (
                    client.table("companies")
                    .select("*")
                    .eq("domain", domain)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    return existing.data[0]
            except Exception:
                pass

        # Last resort: plain insert (no dedup)
        try:
            result = client.table("companies").insert(clean).execute()
            return result.data[0] if result.data else clean
        except Exception:
            import uuid as _uuid
            clean.setdefault("id", str(_uuid.uuid4()))
            return clean

    async def get_companies_for_user(
        self,
        user_id: str,
        limit: int = 50,
        min_score: float = 0.0,
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("companies")
            .select("*, company_rankings!inner(*), company_contacts(*)")
            .eq("company_rankings.user_id", user_id)
            .gte("company_rankings.match_score", min_score)
            .order("company_rankings.match_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def get_company_detail(self, company_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("companies")
            .select("*, company_contacts(*), discovered_jobs(*)")
            .eq("id", company_id)
            .single()
            .execute()
        )
        return result.data

    # ─── Company Rankings ─────────────────────────────────────────────────────

    async def upsert_company_ranking(self, ranking: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return ranking
        result = (
            client.table("company_rankings")
            .upsert(ranking, on_conflict="user_id,company_id")
            .execute()
        )
        return result.data[0] if result.data else ranking

    async def get_company_rankings(
        self, user_id: str, limit: int = 50
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("company_rankings")
            .select("*, companies(*)")
            .eq("user_id", user_id)
            .order("match_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    # ─── Company Contacts ─────────────────────────────────────────────────────

    async def insert_company_contacts(
        self, company_id: str, contacts: list[dict[str, Any]]
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return contacts

        rows = [{"company_id": company_id, **c} for c in contacts]
        result = client.table("company_contacts").insert(rows).execute()
        return result.data or rows

    async def get_company_contacts(self, company_id: str) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("company_contacts")
            .select("*")
            .eq("company_id", company_id)
            .order("confidence", desc=True)
            .execute()
        )
        return result.data or []

    # ─── Discovered Jobs ──────────────────────────────────────────────────────

    async def insert_discovered_jobs(
        self, company_id: str, jobs: list[dict[str, Any]]
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return jobs
        rows = [{"company_id": company_id, **j} for j in jobs]
        result = client.table("discovered_jobs").insert(rows).execute()
        return result.data or rows

    # ─── AI Agent Runs ────────────────────────────────────────────────────────

    async def insert_agent_run(self, run: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return run
        result = client.table("ai_agent_runs").insert(run).execute()
        return result.data[0] if result.data else run

    async def get_agent_runs(
        self, user_id: str, agent_name: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        query = (
            client.table("ai_agent_runs")
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(limit)
        )
        if agent_name:
            query = query.eq("agent_name", agent_name)
        result = query.execute()
        return result.data or []

    # ─── Conversation History ──────────────────────────────────────────────────

    async def insert_conversation_message(
        self, user_id: str, role: str, content: str, context: str = "preferences"
    ) -> dict:
        client = self._get_client()
        if not client:
            return {"user_id": user_id, "role": role, "content": content}
        result = (
            client.table("conversation_history")
            .insert({"user_id": user_id, "context": context, "role": role, "content": content})
            .execute()
        )
        return result.data[0] if result.data else {}

    async def get_conversation_history(
        self, user_id: str, context: str = "preferences", limit: int = 50
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("conversation_history")
            .select("role, content, created_at")
            .eq("user_id", user_id)
            .eq("context", context)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return result.data or []

    # ─── Persistent Company Workspace ───────────────────────────────────────

    async def create_discovery_session(self, session: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return session
        result = client.table("discovery_sessions").insert(session).execute()
        return result.data[0] if result.data else session

    async def update_discovery_session(self, session_id: str, updates: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return {"id": session_id, **updates}
        result = (
            client.table("discovery_sessions")
            .update(updates)
            .eq("id", session_id)
            .execute()
        )
        return result.data[0] if result.data else {"id": session_id, **updates}

    async def get_discovery_sessions(self, user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("discovery_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + max(limit - 1, 0))
            .execute()
        )
        return result.data or []

    async def upsert_orchestration_state(self, state: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return state
        result = (
            client.table("orchestration_state")
            .upsert(state, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else state

    async def get_orchestration_state(self, user_id: str) -> Optional[dict]:
        client = self._get_client()
        if not client:
            return None
        result = (
            client.table("orchestration_state")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        data = result.data or []
        return data[0] if data else None

    async def upsert_user_company(self, row: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return row

        user_id = row.get("user_id")
        company_id = row.get("company_id")
        if not user_id or not company_id:
            return row

        try:
            existing_result = (
                client.table("user_companies")
                .select("*")
                .eq("user_id", user_id)
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
            existing = (existing_result.data or [None])[0]
        except Exception:
            existing = None

        if not existing:
            result = client.table("user_companies").insert(row).execute()
            return result.data[0] if result.data else row

        # Existing workspace rows are durable user state. A new discovery run may
        # refresh ranking/source metadata, but must not reset archive/remove,
        # feedback, personalization, outreach, notes, or orchestration progress.
        existing_metadata = existing.get("metadata") or {}
        incoming_metadata = row.get("metadata") or {}
        session_history = list(existing_metadata.get("discovery_session_history") or [])
        incoming_session = row.get("discovery_session_id")
        if incoming_session and incoming_session not in session_history:
            session_history.append(incoming_session)

        refreshable_keys = {
            "source",
            "ranking_score",
            "ranking_explanation",
            "ranking_metadata",
            "application_strategy",
        }
        updates = {
            key: row[key]
            for key in refreshable_keys
            if key in row and row[key] is not None
        }
        updates["metadata"] = {
            **existing_metadata,
            **incoming_metadata,
            "last_discovery_session_id": incoming_session or existing_metadata.get("last_discovery_session_id"),
            "discovery_session_history": session_history,
        }

        result = (
            client.table("user_companies")
            .update(updates)
            .eq("id", existing["id"])
            .execute()
        )
        return result.data[0] if result.data else {**existing, **updates}

    async def get_user_companies(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False,
        include_removed: bool = False,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []

        # Select user_companies joined with the shared companies record.
        # ranking data lives in user_companies.ranking_metadata / ranking_score directly,
        # so we don't join company_rankings (the cross-table filter is not supported by
        # supabase-py and would silently return wrong results).
        query = client.table("user_companies").select("*, companies(*)").eq("user_id", user_id)
        if not include_archived:
            query = query.eq("archived", False)
        if not include_removed:
            query = query.eq("removed", False)
        if stage:
            query = query.eq("orchestration_stage", stage)
        if source:
            query = query.eq("source", source)

        try:
            result = query.order("updated_at", desc=True).range(offset, offset + max(limit - 1, 0)).execute()
            return result.data or []
        except Exception:
            fallback = client.table("user_companies").select("*").eq("user_id", user_id)
            if not include_archived:
                fallback = fallback.eq("archived", False)
            if not include_removed:
                fallback = fallback.eq("removed", False)
            if stage:
                fallback = fallback.eq("orchestration_stage", stage)
            if source:
                fallback = fallback.eq("source", source)
            result = fallback.order("updated_at", desc=True).range(offset, offset + max(limit - 1, 0)).execute()
            rows = result.data or []
            company_ids = [row.get("company_id") for row in rows if row.get("company_id")]
            if not company_ids:
                return rows
            companies_result = (
                client.table("companies")
                .select("*")
                .in_("id", company_ids)
                .execute()
            )
            companies_by_id = {c.get("id"): c for c in (companies_result.data or [])}
            for row in rows:
                row["companies"] = companies_by_id.get(row.get("company_id")) or {}
            return rows

    async def backfill_user_companies_from_rankings(self, user_id: str) -> list[dict]:
        """
        Reattach legacy ranked companies to the persistent workspace.

        Older runs wrote company_rankings but not user_companies. This converts
        those rows into durable workspace entries without touching any existing
        workspace state.
        """
        client = self._get_client()
        if not client:
            return []

        ranking_result = (
            client.table("company_rankings")
            .select("*, companies(*)")
            .eq("user_id", user_id)
            .order("match_score", desc=True)
            .limit(500)
            .execute()
        )
        rows = ranking_result.data or []
        backfilled: list[dict] = []
        for row in rows:
            company = row.get("companies") or {}
            company_id = row.get("company_id") or company.get("id")
            if not company_id:
                continue
            ranking_metadata = {
                k: v
                for k, v in row.items()
                if k not in {"id", "company_id", "user_id", "created_at", "updated_at", "companies"}
            }
            backfilled.append(await self.upsert_user_company({
                "user_id": user_id,
                "company_id": company_id,
                "source": company.get("source") or "legacy",
                "status": "active",
                "orchestration_stage": "Personalization",
                "ranking_score": row.get("match_score", company.get("relevance_score", 0)),
                "ranking_explanation": row.get("match_explanation", ""),
                "ranking_metadata": ranking_metadata,
                "metadata": {
                    "backfilled_from": "company_rankings",
                    "domain": company.get("domain"),
                },
            }))
        return backfilled

    async def update_user_company(self, user_id: str, company_id: str, updates: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return {"user_id": user_id, "company_id": company_id, **updates}
        result = (
            client.table("user_companies")
            .update(updates)
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        return result.data[0] if result.data else {"user_id": user_id, "company_id": company_id, **updates}

    async def record_company_feedback(
        self,
        user_id: str,
        company_id: str,
        feedback_type: str,
        feedback_reason: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        client = self._get_client()
        row = {
            "user_id": user_id,
            "company_id": company_id,
            "feedback_type": feedback_type,
            "feedback_reason": feedback_reason,
            "metadata": metadata or {},
        }
        if not client:
            return row

        result = (
            client.table("company_feedback")
            .upsert(row, on_conflict="user_id,company_id,feedback_type")
            .execute()
        )
        return result.data[0] if result.data else row

    async def get_company_feedback(self, user_id: str, limit: int = 200) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("company_feedback")
            .select("*, companies(industry,tech_stack,funding_stage,source,domain,name)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def summarize_feedback_learning(self, user_id: str) -> dict[str, Any]:
        """
        Convert explicit like/dislike feedback into lightweight preference priors
        that can be merged into query expansion and ranking signals.
        """
        feedback = await self.get_company_feedback(user_id)
        if not feedback:
            return {
                "liked_industries": [],
                "disliked_industries": [],
                "liked_tech": [],
                "disliked_tech": [],
                "source_boost": {},
            }

        liked_industry_counts: dict[str, int] = {}
        disliked_industry_counts: dict[str, int] = {}
        liked_tech_counts: dict[str, int] = {}
        disliked_tech_counts: dict[str, int] = {}
        source_delta: dict[str, int] = {}

        for row in feedback:
            feedback_type = row.get("feedback_type", "")
            company = row.get("companies") or {}
            industry = (company.get("industry") or "").strip().lower()
            source = (company.get("source") or row.get("metadata", {}).get("source") or "").strip()
            tech_stack = [str(t).strip().lower() for t in (company.get("tech_stack") or []) if t]

            if feedback_type == "like":
                if industry:
                    liked_industry_counts[industry] = liked_industry_counts.get(industry, 0) + 1
                for tech in tech_stack:
                    liked_tech_counts[tech] = liked_tech_counts.get(tech, 0) + 1
                if source:
                    source_delta[source] = source_delta.get(source, 0) + 1
            elif feedback_type == "dislike":
                if industry:
                    disliked_industry_counts[industry] = disliked_industry_counts.get(industry, 0) + 1
                for tech in tech_stack:
                    disliked_tech_counts[tech] = disliked_tech_counts.get(tech, 0) + 1
                if source:
                    source_delta[source] = source_delta.get(source, 0) - 1

        def _top_counts(values: dict[str, int], n: int = 5) -> list[str]:
            return [k for k, _ in sorted(values.items(), key=lambda x: x[1], reverse=True)[:n]]

        return {
            "liked_industries": _top_counts(liked_industry_counts),
            "disliked_industries": _top_counts(disliked_industry_counts),
            "liked_tech": _top_counts(liked_tech_counts, n=8),
            "disliked_tech": _top_counts(disliked_tech_counts, n=8),
            "source_boost": source_delta,
        }

    async def insert_discovery_source_log(self, log: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return log
        result = client.table("discovery_source_logs").insert(log).execute()
        return result.data[0] if result.data else log

    async def get_discovery_source_logs(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 100
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        query = (
            client.table("discovery_source_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(limit)
        )
        if session_id:
            query = query.eq("discovery_session_id", session_id)
        result = query.execute()
        return result.data or []

    async def update_discovery_source_log_counts(
        self,
        *,
        user_id: str,
        discovery_session_id: Optional[str],
        source: str,
        counts: dict[str, Any],
    ) -> list[dict]:
        """Update per-source pipeline counters for the active discovery session."""
        client = self._get_client()
        if not client:
            return []

        query = (
            client.table("discovery_source_logs")
            .select("id, metadata")
            .eq("user_id", user_id)
            .eq("source", source)
            .order("started_at", desc=True)
            .limit(1)
        )
        if discovery_session_id:
            query = query.eq("discovery_session_id", discovery_session_id)

        result = query.execute()
        rows = result.data or []
        if not rows:
            return []

        row = rows[0]
        merged_metadata = {
            **(row.get("metadata") or {}),
            **counts,
        }

        update_payload = {
            "metadata": merged_metadata,
            "duplicate_count": counts.get("duplicates_removed"),
            "filtered_count": (
                counts.get("already_seen_filtered", 0)
                + counts.get("ranking_filtered", 0)
                + counts.get("industry_filtered", 0)
                + counts.get("hard_constraints_filtered", 0)
            ),
            "result_count": counts.get("persisted", counts.get("raw_discovered", 0)),
        }
        updated = (
            client.table("discovery_source_logs")
            .update(update_payload)
            .eq("id", row["id"])
            .execute()
        )
        return updated.data or []

    async def get_agent_events_for_task(
        self,
        task_id: str,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        client = self._get_client()
        if not client:
            return []

        query = (
            client.table("agent_events")
            .select("*")
            .eq("task_id", task_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if agent_name:
            query = query.eq("agent_name", agent_name)
        if status:
            query = query.eq("status", status)

        result = query.execute()
        return result.data or []

    async def get_completed_company_finder_events(self, limit: int = 200) -> list[dict]:
        client = self._get_client()
        if not client:
            return []

        result = (
            client.table("agent_events")
            .select("*")
            .eq("agent_name", "CompanyFinderAgent")
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def get_companies_by_user_id(self, user_id: str, limit: int = 500) -> list[dict]:
        client = self._get_client()
        if not client:
            return []
        result = (
            client.table("companies")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    async def upsert_company_embedding(self, embedding: dict[str, Any]) -> dict:
        client = self._get_client()
        if not client:
            return embedding
        result = (
            client.table("company_embeddings")
            .upsert(embedding, on_conflict="domain")
            .execute()
        )
        return result.data[0] if result.data else embedding


# Singleton instance
supabase_client = SupabaseClient()
