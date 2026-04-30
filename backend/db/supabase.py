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


# Singleton instance
supabase_client = SupabaseClient()
