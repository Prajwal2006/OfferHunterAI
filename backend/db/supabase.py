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
        """Upsert a company by domain + user_id."""
        client = self._get_client()
        if not client:
            import uuid as _uuid
            company.setdefault("id", str(_uuid.uuid4()))
            return company

        # Strip keys that are not columns to avoid 400 errors
        safe_keys = {
            "id", "user_id", "name", "domain", "industry", "size",
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

        result = (
            client.table("companies")
            .upsert(clean, on_conflict="domain")
            .execute()
        )
        return result.data[0] if result.data else clean

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


# Singleton instance
supabase_client = SupabaseClient()
