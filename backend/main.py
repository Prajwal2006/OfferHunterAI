"""
OfferHunter AI Ã¢â‚¬â€ FastAPI Backend
"""
import asyncio
import json
import os
import re
import sys
import uuid
import time
from threading import Lock
from copy import deepcopy
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Ensure backend root is in Python path for both local and Vercel deployments
_backend_root = str(Path(__file__).resolve().parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from db.supabase import supabase_client
from agents.event_logger import AgentEventLogger
from agents.company_finder import CompanyFinderAgent
from agents.personalization import PersonalizationAgent
from agents.email_writer import EmailWriterAgent
from agents.resume_tailor import ResumeTailorAgent
from agents.email_sender import EmailSenderAgent
from agents.follow_up import FollowUpAgent
from agents.response_classifier import ResponseClassifierAgent
from services.resume_parser import ResumeParserService
from services.filters import apply_hard_constraints, normalize_preference_payload, partition_workspace_companies
from services.contact_discovery_service import ContactDiscoveryService
from services.email_editor_service import EmailEditorService
from services.email_writer_service import EmailWriterService
from services.personalization_service import PersonalizationService
from services.versioning_service import VersioningService
from services.logger_service import get_logger
from models.work_mode import normalize_company_work_mode

# In-memory company results cache (user_id -> companies list)
# Used as fallback when Supabase is not configured or rankings table is empty
_user_companies_cache: dict[str, list] = {}
_outreach_drafts_cache: dict[str, list[dict[str, Any]]] = {}
_workspace_repairs_running: set[str] = set()
_workspace_repair_status: dict[str, dict[str, Any]] = {}
_workspace_repair_lock = Lock()
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "false").strip().lower() in {"1", "true", "yes", "on"}
OUTREACH_DRAFT_USE_AI = os.getenv("OUTREACH_DRAFT_USE_AI", "false").strip().lower() in {"1", "true", "yes", "on"}
try:
    STREAM_EMAIL_GENERATION_TIMEOUT_SECONDS = float(os.getenv("STREAM_EMAIL_GENERATION_TIMEOUT_SECONDS", "18"))
except ValueError:
    STREAM_EMAIL_GENERATION_TIMEOUT_SECONDS = 18.0
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
UNIFIED_LOG_FILE = LOGS_DIR / "app.log"
UNIFIED_LOG_FILE.touch(exist_ok=True)


def _safe_preview(value: Any, max_chars: int = 1000) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        text = str(value)
        return text if len(text) <= max_chars else text[:max_chars] + "...[truncated]"
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
        if len(text) <= max_chars:
            return value
        return text[:max_chars] + "...[truncated]"
    except Exception:
        text = str(value)
        return text if len(text) <= max_chars else text[:max_chars] + "...[truncated]"


def _write_log(file_name: str, payload: dict[str, Any]) -> None:
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "log_channel": file_name,
        **payload,
    }

    def format_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, default=str)
        else:
            text = str(value)
        return text if len(text) <= 4000 else text[:4000] + "...[truncated]"

    parts = [
        str(entry.get("ts") or datetime.utcnow().isoformat()),
        f"channel={entry.get('log_channel', 'legacy')}",
    ]
    for key, value in entry.items():
        if key in {"ts", "log_channel"} or value is None:
            continue
        parts.append(f"{key}={format_value(value)}")

    try:
        with UNIFIED_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(" | ".join(parts) + "\n")
    except Exception:
        pass


def _log_backend_action(action: str, **details: Any) -> None:
    _write_log(
        "backend-actions.jsonl",
        {
            "action": action,
            "details": {k: _safe_preview(v, 4000) for k, v in details.items()},
        },
    )


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _repair_status_for(user_id: str) -> dict[str, Any]:
    with _workspace_repair_lock:
        status = dict(_workspace_repair_status.get(user_id) or {})
        return {
            "status": status.get("status", "idle"),
            "job_id": status.get("job_id"),
            "user_id": user_id,
            "recovered_count": status.get("recovered_count", 0),
            "error": status.get("error"),
            "steps": status.get("steps", []),
            "last_started_at": status.get("last_started_at"),
            "last_finished_at": status.get("last_finished_at"),
        }


def _set_repair_status(user_id: str, **updates: Any) -> dict[str, Any]:
    with _workspace_repair_lock:
        current = dict(_workspace_repair_status.get(user_id) or {})
        current.update(updates)
        current["user_id"] = user_id
        _workspace_repair_status[user_id] = current
        return dict(current)


async def _persist_workspace_repair_status(user_id: str, status: dict[str, Any]) -> None:
    """Best-effort repair status persistence; never block user-facing reads."""
    try:
        existing = await _db_call(
            "repair.status.orchestration_state",
            lambda: supabase_client.get_orchestration_state(user_id),
            timeout=2.0,
            fallback=None,
        )
        progress = dict((existing or {}).get("progress") or {})
        progress["workspace_repair"] = {
            "status": status.get("status"),
            "job_id": status.get("job_id"),
            "recovered_count": status.get("recovered_count", 0),
            "error": status.get("error"),
            "last_started_at": status.get("last_started_at"),
            "last_finished_at": status.get("last_finished_at"),
            "steps": status.get("steps", []),
        }
        await _db_call(
            "repair.status.persist",
            lambda: supabase_client.upsert_orchestration_state(
                {
                    "user_id": user_id,
                    "progress": progress,
                }
            ),
            timeout=2.0,
            fallback={},
        )
    except Exception:
        pass


async def _db_call(
    label: str,
    coro_factory,
    *,
    timeout: float = 3.0,
    fallback: Any = None,
) -> Any:
    """
    Run a Supabase wrapper off the FastAPI event loop.

    Most methods in db.supabase are declared async but use the synchronous
    supabase-py client internally, so awaiting them directly can stall every
    request until network I/O returns.
    """
    started = time.perf_counter()

    def run() -> Any:
        return asyncio.run(coro_factory())

    try:
        result = await asyncio.wait_for(asyncio.to_thread(run), timeout=timeout)
        _log_backend_action(
            "db_call.completed",
            label=label,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return result
    except asyncio.TimeoutError:
        _log_backend_action(
            "db_call.timeout",
            label=label,
            timeout_seconds=timeout,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return fallback
    except Exception as exc:
        _log_backend_action(
            "db_call.failed",
            label=label,
            error=str(exc),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return fallback


def _build_allowed_cors_origins() -> list[str]:
    defaults = {
        "https://offerhunterai.vercel.app",
        "https://www.offerhunterai.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
    configured = {
        value.strip().rstrip("/")
        for value in (os.getenv("CORS_ALLOW_ORIGINS", "") + "," + os.getenv("FRONTEND_URL", "")).split(",")
        if value.strip()
    }
    return sorted(defaults | configured)


ALLOWED_CORS_ORIGINS = _build_allowed_cors_origins()


def _company_memory_key(company: dict[str, Any]) -> str:
    return str(
        company.get("id")
        or (company.get("domain") or "").lower().strip()
        or (company.get("website_url") or "").lower().strip()
        or (company.get("name") or "").lower().strip()
    )


def _merge_user_company_cache(user_id: str, incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Append newly discovered companies to the process-local fallback cache.

    Supabase is the source of truth. This cache only exists for local/dev
    resilience, so it must mimic the same append-only workspace semantics.
    """
    merged: dict[str, dict[str, Any]] = {}
    for company in _user_companies_cache.get(user_id, []) + list(incoming or []):
        key = _company_memory_key(company)
        if key:
            merged[key] = {**merged.get(key, {}), **company}
    _user_companies_cache[user_id] = list(merged.values())
    return _user_companies_cache[user_id]


def _merge_outreach_draft_cache(user_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    drafts = _outreach_drafts_cache.setdefault(user_id, [])
    draft_id = draft.get("id")
    company_id = draft.get("company_id")
    merged = False
    for index, existing in enumerate(drafts):
        if (draft_id and existing.get("id") == draft_id) or (company_id and existing.get("company_id") == company_id):
            drafts[index] = {**existing, **draft}
            merged = True
            break
    if not merged:
        drafts.insert(0, draft)
    return draft


async def _get_email_drafts_fast(user_id: str, status: Optional[str] = None, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Fetch drafts without allowing the synchronous Supabase client to hang the event loop."""
    def fetch_db() -> list[dict[str, Any]]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
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

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        return []


async def _get_email_draft_fast(draft_id: str, timeout: float = 3.0) -> Optional[dict[str, Any]]:
    def fetch_db() -> Optional[dict[str, Any]]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
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

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        return None


async def _get_email_versions_fast(draft_id: str, timeout: float = 2.0) -> list[dict[str, Any]]:
    def fetch_db() -> list[dict[str, Any]]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
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

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        return []


def _find_cached_company(user_id: str, company_id: str) -> Optional[dict[str, Any]]:
    for company in _user_companies_cache.get(user_id, []):
        if str(company.get("id")) == str(company_id):
            return company
    return None


async def _load_outreach_context_fast(user_id: str, company_id: str, timeout: float = 4.0) -> dict[str, Any]:
    """Load only the data needed to write one selected-company email, with cache fallback."""
    cached_company = _find_cached_company(user_id, company_id)

    def fetch_db() -> dict[str, Any]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
        if not client:
            return {}

        def first(table: str, select: str = "*", **filters: str) -> Optional[dict[str, Any]]:
            query = client.table(table).select(select)
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.limit(1).execute()
            rows = result.data or []
            return rows[0] if rows else None

        company_result = (
            client.table("companies")
            .select("*, company_contacts(*), discovered_jobs(*)")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )
        company_rows = company_result.data or []
        return {
            "company": company_rows[0] if company_rows else None,
            "profile": first("parsed_profiles", user_id=user_id) or {},
            "preferences": first("user_preferences", user_id=user_id) or {},
            "resume": first("resume_versions", user_id=user_id, is_active=True) or {},
        }

    try:
        data = await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        data = {}

    company = data.get("company") or cached_company
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {
        "company": company,
        "profile": data.get("profile") or {},
        "preferences": normalize_preference_payload(data.get("preferences") or {}),
        "resume": data.get("resume") or {},
    }


async def _get_personalization_profile_fast(user_id: str, company_id: str, timeout: float = 1.5) -> Optional[dict[str, Any]]:
    def fetch_db() -> Optional[dict[str, Any]]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
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

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        return None


async def _persist_email_draft_fast(user_id: str, draft_payload: dict[str, Any], timeout: float = 2.5) -> dict[str, Any]:
    """Persist the draft when Supabase is responsive, but always return the cached draft."""
    _merge_outreach_draft_cache(user_id, draft_payload)

    def write_db() -> dict[str, Any]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
        if not client:
            return draft_payload
        result = (
            client.table("email_drafts")
            .upsert(draft_payload, on_conflict="user_id,company_id")
            .execute()
        )
        return result.data[0] if result.data else draft_payload

    try:
        stored = await asyncio.wait_for(asyncio.to_thread(write_db), timeout=timeout)
    except Exception:
        stored = draft_payload
    _merge_outreach_draft_cache(user_id, stored)
    return stored


async def _finalize_email_draft_storage(
    *,
    user_id: str,
    company_id: str,
    stored: dict[str, Any],
    personalization: dict[str, Any],
) -> None:
    """Best-effort noncritical storage. Failure here must not break draft generation."""
    def write_db() -> None:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
        if not client:
            return
        try:
            if personalization:
                client.table("personalization_profiles").upsert(
                    personalization,
                    on_conflict="user_id,company_id",
                ).execute()
        except Exception:
            pass
        try:
            version = VersioningService().create_version(
                draft={**stored, "version_number": 0},
                event_type="generated",
                editor="ai",
                changes={"personalization_profile_id": personalization.get("id")},
            )
            client.table("email_versions").insert(version).execute()
        except Exception:
            pass
        try:
            subjects = stored.get("subjects") or []
            if stored.get("id") and subjects:
                rows = [{"draft_id": stored.get("id"), **subject} for subject in subjects]
                client.table("generated_subjects").insert(rows).execute()
        except Exception:
            pass
        try:
            client.table("user_companies").update(
                {"outreach_started": True, "orchestration_stage": "Review"}
            ).eq("user_id", user_id).eq("company_id", company_id).execute()
        except Exception:
            pass

    try:
        await asyncio.wait_for(asyncio.to_thread(write_db), timeout=4.0)
    except Exception:
        pass


async def _get_generated_subjects_fast(draft_id: str, timeout: float = 2.0) -> list[dict[str, Any]]:
    def fetch_db() -> list[dict[str, Any]]:
        client = supabase_client._get_client()  # type: ignore[attr-defined]
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

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_db), timeout=timeout)
    except Exception:
        return []


def _hydrate_company_work_mode(company: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(company)
    metadata = hydrated.get("metadata") or {}
    if "work_mode" not in hydrated and metadata.get("work_mode"):
        hydrated["work_mode"] = metadata.get("work_mode")
    if "remote_confidence" not in hydrated and metadata.get("remote_confidence") is not None:
        hydrated["remote_confidence"] = metadata.get("remote_confidence")
    if "work_mode_reasoning" not in hydrated and metadata.get("work_mode_reasoning"):
        hydrated["work_mode_reasoning"] = metadata.get("work_mode_reasoning")
    if metadata.get("preference_enforcement") and "preference_enforcement" not in hydrated:
        hydrated["preference_enforcement"] = metadata.get("preference_enforcement")
    return normalize_company_work_mode(hydrated, source=str(hydrated.get("source") or ""))

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ SSE Broadcast Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# Each SSE connection gets its own queue so every subscriber receives every event.
_sse_subscribers: list[asyncio.Queue] = []


class _BroadcastQueue:
    """
    Drop-in replacement for asyncio.Queue that broadcasts put_nowait() calls
    to all active SSE subscriber queues instead of a single consumer.
    """
    def put_nowait(self, event: dict) -> None:  # type: ignore[override]
        for q in list(_sse_subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def get(self) -> dict:  # pragma: no cover
        await asyncio.sleep(3600)
        return {}


_broadcast_queue = _BroadcastQueue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("OfferHunter AI backend starting up...")
    yield
    # Shutdown
    print("OfferHunter AI backend shutting down...")


app = FastAPI(
    title="OfferHunter AI API",
    description="Multi-agent job discovery and outreach automation backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "Cache-Control",
        "Pragma",
        "Last-Event-ID",
        "X-Requested-With",
    ],
    expose_headers=[
        "Content-Type",
        "Cache-Control",
        "Connection",
        "X-Accel-Buffering",
    ],
    max_age=600,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    logger = get_logger()
    started = time.perf_counter()
    request_id = str(uuid.uuid4())
    request_payload: Any = None
    request_body_size = 0
    content_type = (request.headers.get("content-type") or "").lower()
    user_id = request.headers.get("x-user-id") or request.headers.get("user-id")
    
    try:
        if content_type.startswith("multipart/") or "application/octet-stream" in content_type:
            request_payload = f"[{content_type or 'binary'} body omitted]"
        else:
            body = await request.body()
            request_body_size = len(body or b"")
            if body and request_body_size <= 20000:
                if "application/json" in content_type:
                    try:
                        request_payload = json.loads(body.decode("utf-8", errors="ignore"))
                    except Exception:
                        request_payload = body.decode("utf-8", errors="ignore")
                else:
                    request_payload = f"[{content_type or 'raw'} body omitted]"
    except Exception:
        request_payload = "[failed to read request body]"
    
    # Log API request using the new logger service
    logger.log_api_request(
        endpoint=request.url.path,
        method=request.method,
        user_id=user_id,
        body=request_payload,
        status="received",
        request_id=request_id,
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        
        # Log API response using the new logger service
        logger.log_api_response(
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
            endpoint=request.url.path,
            method=request.method,
        )
        
        # Also write to legacy format for backward compatibility
        _write_log(
            "api-calls.jsonl",
            {
                "request_id": request_id,
                "kind": "api_call",
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_body_size": request_body_size,
                "request_payload": _safe_preview(request_payload, 4000),
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        
        # Log error using the new logger service
        logger.log_error(
            error_type="api_request_failed",
            message=str(exc),
            user_id=user_id,
            context={
                "request_id": request_id,
                "endpoint": request.url.path,
                "method": request.method,
                "duration_ms": duration_ms,
            },
            severity="error",
        )
        
        # Also write to legacy format
        _write_log(
            "api-calls.jsonl",
            {
                "request_id": request_id,
                "kind": "api_call_error",
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "duration_ms": duration_ms,
                "request_body_size": request_body_size,
                "request_payload": _safe_preview(request_payload, 4000),
                "error": str(exc),
            },
        )
        raise

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Models Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class RunAgentsRequest(BaseModel):
    skills: list[str]
    job_title: str
    company_count: int = 10
    resume_text: Optional[str] = None
    resume_version_id: Optional[str] = None
    user_id: Optional[str] = None


class ExecuteAgentRequest(BaseModel):
    task_id: Optional[str] = None
    payload: dict[str, Any] = {}


class EmailApprovalRequest(BaseModel):
    reason: Optional[str] = None


class EmailUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    resume_version_id: Optional[str] = None


class GeneratePersonalizationRequest(BaseModel):
    user_id: str
    company_id: str
    job_id: Optional[str] = None
    job: Optional[dict[str, Any]] = None


class GenerateEmailDraftRequest(BaseModel):
    user_id: str
    company_id: str
    personalization_profile_id: Optional[str] = None
    job_id: Optional[str] = None
    job: Optional[dict[str, Any]] = None
    recipient: Optional[dict[str, Any]] = None
    outreach_type: Optional[str] = None


class DraftUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    selected_variant: Optional[str] = None
    recipient_email: Optional[str] = None
    status: Optional[str] = None
    user_id: Optional[str] = None


class InlineAIEditRequest(BaseModel):
    user_id: str
    instruction: str
    selected_text: str
    full_body: str
    subject: Optional[str] = ""
    auto_apply: bool = False


class ApplyAIEditRequest(BaseModel):
    user_id: str
    ai_edit_request_id: Optional[str] = None
    replacement_text: str
    original_text: str


class DiscoverContactsRequest(BaseModel):
    user_id: str
    company_id: str
    job: Optional[dict[str, Any]] = None


class FrontendClientLogRequest(BaseModel):
    source: str = "frontend-action"
    event: str
    level: str = "info"
    payload: Optional[dict[str, Any]] = None


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Company Finder Models Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class CompanyFinderRunRequest(BaseModel):
    user_id: str
    resume_text: Optional[str] = None
    resume_version_id: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None
    count: int = 60
    rediscover: bool = False


class PreferenceChatRequest(BaseModel):
    user_id: str
    message: str
    history: list[dict[str, str]] = []
    current_prefs: Optional[dict[str, Any]] = None


class SavePreferencesRequest(BaseModel):
    user_id: str
    preferences: dict[str, Any]


class ParseResumeRequest(BaseModel):
    user_id: str
    resume_version_id: Optional[str] = None


class ManualCompanyRequest(BaseModel):
    user_id: str
    website_url: str


class CompanyWorkspaceUpdateRequest(BaseModel):
    user_id: str
    archived: Optional[bool] = None
    removed: Optional[bool] = None
    liked: Optional[bool] = None
    disliked: Optional[bool] = None
    notes: Optional[str] = None
    orchestration_stage: Optional[str] = None
    personalization_completed: Optional[bool] = None
    outreach_started: Optional[bool] = None
    outreach_sent: Optional[bool] = None


class CompanyFeedbackRequest(BaseModel):
    user_id: str
    feedback_type: str
    feedback_reason: Optional[str] = ""


class ContinueDiscoveryRequest(BaseModel):
    user_id: str
    count: int = 40
    source_mode: Optional[str] = None


class WorkspaceRepairRequest(BaseModel):
    user_id: str


async def _load_company_memory(user_id: str) -> dict[str, set[str]]:
    """
    Load every durable company memory signal used to avoid repeated recommendations.
    Includes hidden rows so archived, removed, disliked, and applied companies are
    still treated as seen unless the caller explicitly requests rediscovery.
    """
    memory = {
        "seen_domains": set(),
        "seen_names": set(),
        "disliked_domains": set(),
        "applied_domains": set(),
    }

    try:
        rows = await supabase_client.get_user_companies(
            user_id=user_id,
            limit=1000,
            include_archived=True,
            include_removed=True,
        )
        for row in rows:
            company = row.get("companies") or {}
            domain = (company.get("domain") or row.get("metadata", {}).get("domain") or "").lower().strip()
            name = (company.get("name") or "").lower().strip()
            if domain:
                memory["seen_domains"].add(domain)
                if row.get("disliked") or row.get("removed"):
                    memory["disliked_domains"].add(domain)
                if row.get("outreach_sent"):
                    memory["applied_domains"].add(domain)
            if name:
                memory["seen_names"].add(name)
    except Exception:
        pass

    for company in _user_companies_cache.get(user_id, []):
        domain = (company.get("domain") or "").lower().strip()
        name = (company.get("name") or "").lower().strip()
        if domain:
            memory["seen_domains"].add(domain)
        if name:
            memory["seen_names"].add(name)

    return memory


class OrchestrationStateUpdateRequest(BaseModel):
    current_stage: Optional[str] = None
    progress: Optional[dict[str, Any]] = None
    active_agents: Optional[list[str]] = None
    paused_state: Optional[bool] = None
    last_task_id: Optional[str] = None


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Agent Event Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/agent-events")
async def get_agent_events(
    limit: int = Query(50, ge=1, le=200),
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
):
    """Poll for recent agent events."""
    try:
        result = await _db_call(
            "agent_events.list",
            lambda: supabase_client.get_agent_events(
                limit=limit, agent_name=agent_name, status=status
            ),
            timeout=3.0,
            fallback=[],
        )
        return {"events": result, "total": len(result)}
    except Exception:
        # Return mock data when DB not configured
        return {"events": _mock_events(), "total": len(_mock_events())}


@app.get("/agent-events/stream")
async def stream_agent_events(request: Request):
    """Server-Sent Events endpoint for real-time agent event streaming."""
    subscriber_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _sse_subscribers.append(subscriber_queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial heartbeat
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        try:
            while True:
                try:
                    # Wait for new event (with timeout for keep-alive)
                    event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield ": keepalive\n\n"
                except Exception:
                    break
        finally:
            # Remove subscriber when client disconnects
            try:
                _sse_subscribers.remove(subscriber_queue)
            except ValueError:
                pass

    request_origin = (request.headers.get("origin") or "").rstrip("/")
    allow_origin = request_origin if request_origin in ALLOWED_CORS_ORIGINS else ALLOWED_CORS_ORIGINS[0]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Vary": "Origin",
        },
    )


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Agent Execution Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/agents/run")
async def run_agents(request: RunAgentsRequest):
    """Trigger the full multi-agent pipeline."""
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)

    async def run_pipeline():
        try:
            resume_text = request.resume_text
            resume_skills = _extract_skills(resume_text) if resume_text else []
            resume_version_id = request.resume_version_id

            if not resume_text and request.resume_version_id:
                resume = await supabase_client.get_resume(request.resume_version_id)
                if resume:
                    resume_text = resume.get("extracted_text")
                    resume_skills = resume.get("extracted_skills") or []

            if not resume_text and request.user_id:
                active_resume = await supabase_client.get_active_resume(request.user_id)
                if active_resume:
                    resume_text = active_resume.get("extracted_text")
                    resume_skills = active_resume.get("extracted_skills") or []
                    resume_version_id = active_resume.get("id")

            effective_skills = request.skills or resume_skills

            # 1. Company Finder — full pipeline with resume + preferences
            company_agent = CompanyFinderAgent(logger=logger)
            preferences: dict = {}
            if request.user_id:
                preferences = await supabase_client.get_user_preferences(request.user_id) or {}
            preferences = normalize_preference_payload(preferences)
            # Inject job_title into preferences if not already set
            if not preferences.get("preferred_roles") and request.job_title:
                preferences["preferred_roles"] = [request.job_title]

            pipeline_result = await company_agent.run_full_pipeline(
                task_id=task_id,
                user_id=request.user_id or "anonymous",
                resume_text=resume_text or " ".join(effective_skills),
                preferences=preferences,
                count=request.company_count,
            )
            companies = pipeline_result.get("companies", [])
            if companies and request.user_id:
                _merge_user_company_cache(request.user_id, companies)

            # 2. Personalization (per company)
            personalization_agent = PersonalizationAgent(logger=logger)
            profile = await supabase_client.get_parsed_profile(request.user_id) if request.user_id else {}
            active_resume_payload = {
                "id": resume_version_id,
                "extracted_text": resume_text or "",
                "extracted_skills": resume_skills,
            }
            for company in companies[:request.company_count]:
                insights = await personalization_agent.run(
                    task_id=str(uuid.uuid4()),
                    company=company,
                    user_id=request.user_id or "anonymous",
                    user_profile=profile or {},
                    preferences=preferences,
                    resume=active_resume_payload,
                    job={"title": request.job_title},
                )

                # 3. Email Writer (per company)
                email_writer = EmailWriterAgent(logger=logger)
                await email_writer.run(
                    task_id=str(uuid.uuid4()),
                    company=company,
                    skills=effective_skills,
                    job_title=request.job_title,
                    personalization=insights,
                    user_id=request.user_id or "anonymous",
                    user_profile=profile or {},
                    preferences=preferences,
                    resume=active_resume_payload,
                    resume_text=resume_text,
                    resume_skills=resume_skills,
                    resume_version_id=resume_version_id,
                )

        except Exception as e:
            await logger.emit(
                agent_name="Orchestrator",
                task_id=task_id,
                status="failed",
                message=f"Pipeline failed: {str(e)}",
            )

    # Run pipeline in background
    asyncio.create_task(run_pipeline())

    return {"task_id": task_id, "status": "started", "message": "Agent pipeline initiated"}


@app.post("/agents/{agent_name}/execute")
async def execute_agent(agent_name: str, request: ExecuteAgentRequest):
    """Execute a specific agent by name."""
    task_id = request.task_id or str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)

    agent_map = {
        "company-finder": CompanyFinderAgent,
        "personalization": PersonalizationAgent,
        "email-writer": EmailWriterAgent,
        "resume-tailor": ResumeTailorAgent,
        "email-sender": EmailSenderAgent,
        "follow-up": FollowUpAgent,
        "response-classifier": ResponseClassifierAgent,
    }

    AgentClass = agent_map.get(agent_name.lower())
    if not AgentClass:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Valid agents: {list(agent_map.keys())}",
        )

    agent = AgentClass(logger=logger)
    asyncio.create_task(agent.run(task_id=task_id, **request.payload))

    return {"task_id": task_id, "agent": agent_name, "status": "started"}


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Email Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/emails")
async def get_emails(status: Optional[str] = None):
    """List emails with optional status filter."""
    try:
        result = await supabase_client.get_emails(status=status)
        return {"emails": result}
    except Exception:
        return {"emails": _mock_emails(status) if USE_MOCK_DATA else []}


@app.patch("/emails/{email_id}")
async def update_email(email_id: str, request: EmailUpdateRequest):
    """Edit an email draft."""
    try:
        result = await supabase_client.update_email(
            email_id=email_id,
            updates={k: v for k, v in request.model_dump().items() if v is not None},
        )
        return {"email": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/{email_id}/approve")
async def approve_email(email_id: str):
    """Approve an email for sending (human-in-the-loop)."""
    try:
        result = await supabase_client.update_email(
            email_id=email_id, updates={"status": "approved"}
        )
        logger = AgentEventLogger(event_queue=_broadcast_queue)
        await logger.emit(
            agent_name="EmailSenderAgent",
            task_id=email_id,
            status="started",
            message=f"Email {email_id} approved by user Ã¢â‚¬â€ ready to send",
            metadata={"email_id": email_id},
        )
        return {"email_id": email_id, "status": "approved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/{email_id}/reject")
async def reject_email(email_id: str, request: EmailApprovalRequest):
    """Reject an email draft."""
    try:
        await supabase_client.update_email(
            email_id=email_id, updates={"status": "rejected"}
        )
        return {"email_id": email_id, "status": "rejected", "reason": request.reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/{email_id}/send")
async def send_email(email_id: str):
    """Send an approved email via Gmail API."""
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    sender = EmailSenderAgent(logger=logger)
    task_id = str(uuid.uuid4())
    asyncio.create_task(sender.run(task_id=task_id, email_id=email_id))
    return {"email_id": email_id, "task_id": task_id, "status": "sending"}


# ─── Production Outreach Workflow Endpoints ────────────────────────────────

async def _load_outreach_context(user_id: str, company_id: str) -> dict[str, Any]:
    company = await supabase_client.get_company_detail(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    profile = await supabase_client.get_parsed_profile(user_id) or {}
    preferences = await supabase_client.get_user_preferences(user_id) or {}
    resume = await supabase_client.get_active_resume(user_id) or {}
    return {
        "company": company,
        "profile": profile,
        "preferences": normalize_preference_payload(preferences),
        "resume": resume,
    }


async def _generate_selected_company_email(request: GenerateEmailDraftRequest) -> dict[str, Any]:
    """
    Fast selected-company draft generation.

    The critical path intentionally avoids live AI and contact discovery. Those are useful
    enrichments, but a user click on "Generate cold email" should always produce a draft.
    """
    started = time.perf_counter()
    _log_backend_action(
        "generate_selected_company_email.started",
        user_id=request.user_id,
        company_id=request.company_id,
        outreach_type=request.outreach_type or "cold_email",
    )
    context = await _load_outreach_context_fast(request.user_id, request.company_id)
    _log_backend_action(
        "generate_selected_company_email.context_loaded",
        user_id=request.user_id,
        company_id=request.company_id,
        company=context.get("company", {}).get("name"),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    personalization = await _get_personalization_profile_fast(request.user_id, request.company_id)
    if not personalization:
        personalization_model = await PersonalizationService().generate_profile(
            user_id=request.user_id,
            company=context["company"],
            user_profile=context["profile"],
            preferences=context["preferences"],
            resume=context["resume"],
            job=request.job,
            use_ai=False,
        )
        personalization = personalization_model.model_dump()
        _log_backend_action(
            "generate_selected_company_email.personalization_generated",
            user_id=request.user_id,
            company_id=request.company_id,
        )
    else:
        _log_backend_action(
            "generate_selected_company_email.personalization_loaded",
            user_id=request.user_id,
            company_id=request.company_id,
            profile_id=personalization.get("id"),
        )

    draft_model = await EmailWriterService().generate_email(
        user_id=request.user_id,
        company=context["company"],
        personalization=personalization,
        user_profile=context["profile"],
        preferences=context["preferences"],
        resume=context["resume"],
        job=request.job,
        recipient=request.recipient,
        outreach_type=request.outreach_type or "cold_email",
        use_ai=OUTREACH_DRAFT_USE_AI,
    )
    _log_backend_action(
        "generate_selected_company_email.draft_generated",
        user_id=request.user_id,
        company_id=request.company_id,
        used_ai=OUTREACH_DRAFT_USE_AI,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    draft_payload = {**draft_model.model_dump(), "version_number": 1}
    stored = await _persist_email_draft_fast(request.user_id, draft_payload)
    asyncio.create_task(
        _finalize_email_draft_storage(
            user_id=request.user_id,
            company_id=request.company_id,
            stored=stored,
            personalization=personalization,
        )
    )
    _log_backend_action(
        "generate_selected_company_email.completed",
        user_id=request.user_id,
        company_id=request.company_id,
        draft_id=stored.get("id"),
        total_duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return {"draft": stored, "personalization": personalization}


@app.post("/outreach/personalization")
async def generate_personalization(request: GeneratePersonalizationRequest):
    """Generate and persist a structured personalization profile for one company."""
    context = await _load_outreach_context(request.user_id, request.company_id)
    service = PersonalizationService()
    profile = await service.generate_profile(
        user_id=request.user_id,
        company=context["company"],
        user_profile=context["profile"],
        preferences=context["preferences"],
        resume=context["resume"],
        job=request.job,
    )
    stored = await supabase_client.upsert_personalization_profile(profile.model_dump())
    await supabase_client.update_user_company(
        request.user_id,
        request.company_id,
        {"personalization_completed": True, "orchestration_stage": "EmailWriter"},
    )
    return {"profile": stored}


@app.get("/outreach/personalization/{company_id}")
async def get_personalization(company_id: str, user_id: str = Query(...)):
    profile = await supabase_client.get_personalization_profile(user_id, company_id)
    return {"profile": profile}


@app.post("/outreach/contacts/discover")
async def discover_outreach_contacts(request: DiscoverContactsRequest):
    """Discover, rank, and persist public outreach contacts for a company."""
    company = await supabase_client.get_company_detail(request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    result = await ContactDiscoveryService().discover(company, request.job)
    rows = [
        {
            "id": str(uuid.uuid4()),
            "user_id": request.user_id,
            "company_id": request.company_id,
            "name": c.get("name") or "",
            "role": c.get("role") or c.get("title") or "",
            "title": c.get("title") or c.get("role") or "",
            "email": c.get("email") or "",
            "confidence": c.get("confidence") or 0,
            "source": c.get("source") or "",
            "priority_score": c.get("priority_score") or 0,
            "verified": c.get("verified") or False,
            "contact_type": c.get("contact_type") or "other",
            "metadata": c,
        }
        for c in result.get("contacts", [])
        if c.get("email")
    ]
    stored = await supabase_client.upsert_outreach_contacts(rows)
    return {"contacts": stored}


@app.get("/outreach/contacts/{company_id}")
async def get_outreach_contacts(company_id: str, user_id: str = Query(...)):
    contacts = await supabase_client.get_outreach_contacts(user_id, company_id)
    return {"contacts": contacts}


@app.post("/outreach/drafts/generate")
async def generate_email_draft(request: GenerateEmailDraftRequest):
    """Generate a selected-company cold email quickly and fail-soft."""
    return await _generate_selected_company_email(request)


@app.get("/outreach/drafts/generate/stream")
async def stream_email_generation(
    request: Request,
    user_id: str = Query(...),
    company_id: str = Query(...),
    outreach_type: str = Query("cold_email"),
):
    """
    SSE endpoint that streams email generation progress in real time.
    Emits status events for each step, then the full draft when ready.
    """
    async def generate_and_stream() -> AsyncGenerator[str, None]:
        def event(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        started = time.perf_counter()
        try:
            _log_backend_action(
                "stream_email_generation.started",
                user_id=user_id,
                company_id=company_id,
                outreach_type=outreach_type,
            )
            yield event({"type": "status", "step": "context", "message": "Loading your profile and company data..."})
            context = await _load_outreach_context_fast(user_id, company_id)
            company_name = (context.get("company") or {}).get("name") or "this company"
            _log_backend_action(
                "stream_email_generation.context_loaded",
                user_id=user_id,
                company_id=company_id,
                company_name=company_name,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

            yield event({"type": "status", "step": "personalization", "message": f"Building personalization profile for {company_name}..."})
            personalization = await _get_personalization_profile_fast(user_id, company_id)
            if not personalization:
                personalization_model = await PersonalizationService().generate_profile(
                    user_id=user_id,
                    company=context["company"],
                    user_profile=context["profile"],
                    preferences=context["preferences"],
                    resume=context["resume"],
                    use_ai=False,
                )
                personalization = personalization_model.model_dump()
                _log_backend_action(
                    "stream_email_generation.personalization_generated",
                    user_id=user_id,
                    company_id=company_id,
                )
            else:
                _log_backend_action(
                    "stream_email_generation.personalization_loaded",
                    user_id=user_id,
                    company_id=company_id,
                    profile_id=personalization.get("id"),
                )

            yield event({"type": "status", "step": "writing", "message": f"Writing your personalized cold email for {company_name}..."})
            draft_model = await asyncio.wait_for(
                EmailWriterService().generate_email(
                    user_id=user_id,
                    company=context["company"],
                    personalization=personalization,
                    user_profile=context["profile"],
                    preferences=context["preferences"],
                    resume=context["resume"],
                    outreach_type=outreach_type,
                    use_ai=OUTREACH_DRAFT_USE_AI,
                ),
                # Keep backend timeout below frontend SSE watchdog thresholds
                # (20s inactivity / 45s total) to avoid indefinite loading.
                timeout=STREAM_EMAIL_GENERATION_TIMEOUT_SECONDS,
            )
            _log_backend_action(
                "stream_email_generation.draft_generated",
                user_id=user_id,
                company_id=company_id,
                used_ai=OUTREACH_DRAFT_USE_AI,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            draft_payload = {**draft_model.model_dump(), "version_number": 1}
            stored = await _persist_email_draft_fast(user_id, draft_payload)
            asyncio.create_task(
                _finalize_email_draft_storage(
                    user_id=user_id,
                    company_id=company_id,
                    stored=stored,
                    personalization=personalization,
                )
            )
            yield event({"type": "draft", "draft": stored, "personalization": personalization})
            yield event({"type": "done"})
            _log_backend_action(
                "stream_email_generation.completed",
                user_id=user_id,
                company_id=company_id,
                draft_id=stored.get("id"),
                total_duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except asyncio.TimeoutError:
            _log_backend_action(
                "stream_email_generation.timeout",
                user_id=user_id,
                company_id=company_id,
                timeout_seconds=STREAM_EMAIL_GENERATION_TIMEOUT_SECONDS,
            )
            yield event({"type": "error", "message": "Draft generation timed out. Please try again."})
        except HTTPException as exc:
            _log_backend_action(
                "stream_email_generation.http_error",
                user_id=user_id,
                company_id=company_id,
                error=exc.detail,
            )
            yield event({"type": "error", "message": exc.detail})
        except Exception as exc:
            _log_backend_action(
                "stream_email_generation.error",
                user_id=user_id,
                company_id=company_id,
                error=str(exc),
            )
            # Do not expose internal exception details to the client
            yield event({"type": "error", "message": "Failed to generate email draft. Please try again."})

    request_origin = (request.headers.get("origin") or "").rstrip("/")
    allow_origin = request_origin if request_origin in ALLOWED_CORS_ORIGINS else ALLOWED_CORS_ORIGINS[0]

    return StreamingResponse(
        generate_and_stream(),
        media_type="text/event-stream",
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Vary": "Origin",
        },
    )


@app.post("/debug/logs/frontend")
async def ingest_frontend_logs(request: Request):
    """
    Receive and persist comprehensive frontend logs.
    Supports both legacy format and new structured format.
    """
    logger = get_logger()
    
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    
    # Handle new structured format from client-logger
    if "logs" in body:
        logs = body.get("logs", [])
        user_id = body.get("user_id")
        session_id = body.get("session_id")
        
        for log_entry in logs:
            event_type = log_entry.get("event_type", "unknown")
            component = log_entry.get("component", "unknown")
            
            if event_type == "button_click":
                logger.log_business_logic(
                    action=log_entry.get("action", "unknown_click"),
                    user_id=user_id,
                    details={
                        "component": component,
                        "session_id": session_id,
                        **log_entry.get("details", {}),
                    },
                )
            elif event_type == "api_call":
                logger.log_api_request(
                    endpoint=log_entry.get("endpoint", "unknown"),
                    method=log_entry.get("method", "GET"),
                    user_id=user_id,
                    body=log_entry.get("details"),
                )
            elif event_type == "api_response":
                logger.log_api_response(
                    request_id=log_entry.get("endpoint", "unknown"),
                    status_code=log_entry.get("status_code", 0),
                    duration_ms=log_entry.get("duration_ms"),
                )
            elif event_type == "error":
                logger.log_error(
                    error_type=log_entry.get("error_type", "unknown"),
                    message=log_entry.get("error_message", "Unknown error"),
                    user_id=user_id,
                    context=log_entry.get("details"),
                    severity="error",
                )
            elif event_type == "performance":
                logger.log_performance(
                    operation=log_entry.get("action", "unknown"),
                    duration_ms=log_entry.get("duration_ms", 0),
                    user_id=user_id,
                    metadata=log_entry.get("details"),
                )
            else:
                logger.log_frontend_event(
                    event_type=event_type,
                    component=component,
                    user_id=user_id,
                    details=log_entry.get("details"),
                    level=log_entry.get("level", "info"),
                )
    else:
        # Handle legacy format
        file_name = "frontend-api.jsonl" if body.get("source") == "frontend-api" else "frontend-actions.jsonl"
        _write_log(
            file_name,
            {
                "kind": body.get("source", "unknown"),
                "event": body.get("event", "unknown"),
                "level": body.get("level", "info"),
                "payload": _safe_preview(body.get("payload", {}), 8000),
            },
        )
    
    return {"ok": True}


@app.get("/outreach/drafts")
async def get_email_drafts(user_id: str = Query(...), status: Optional[str] = None):
    cached = _outreach_drafts_cache.get(user_id, [])
    if status:
        cached = [draft for draft in cached if draft.get("status") == status]
    drafts = await _get_email_drafts_fast(user_id=user_id, status=status)
    seen = {draft.get("id") for draft in drafts}
    for draft in cached:
        if draft.get("id") not in seen:
            drafts.append(draft)
    return {"drafts": drafts}


@app.get("/outreach/drafts/{draft_id}")
async def get_email_draft(draft_id: str):
    draft = await _get_email_draft_fast(draft_id)
    if not draft:
        for drafts in _outreach_drafts_cache.values():
            draft = next((item for item in drafts if item.get("id") == draft_id), None)
            if draft:
                break
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    versions = await _get_email_versions_fast(draft_id)
    subjects = await _get_generated_subjects_fast(draft_id)
    return {"draft": draft, "versions": versions, "subjects": subjects}


@app.patch("/outreach/drafts/{draft_id}")
async def update_email_draft(draft_id: str, request: DraftUpdateRequest):
    """Autosave/manual edit. Every content edit creates an immutable version."""
    current = await supabase_client.get_email_draft(draft_id)
    if not current:
        raise HTTPException(status_code=404, detail="Draft not found")
    updates = {k: v for k, v in request.model_dump().items() if k != "user_id" and v is not None}
    if not updates:
        return {"draft": current}
    updates["version_number"] = int(current.get("version_number") or 1) + 1
    updates["last_edited_at"] = datetime.utcnow().isoformat()
    updated = await supabase_client.update_email_draft(draft_id, updates)
    snapshot = {**current, **updates, **updated}
    version = VersioningService().create_version(
        draft={**snapshot, "version_number": int(current.get("version_number") or 1)},
        event_type="manual_edit",
        editor="user",
        changes=updates,
    )
    await supabase_client.insert_email_version(version)
    await supabase_client.insert_edit_history(
        {
            "id": str(uuid.uuid4()),
            "draft_id": draft_id,
            "user_id": request.user_id or current.get("user_id"),
            "edit_type": "manual",
            "before": current,
            "after": snapshot,
            "metadata": {"changed_fields": list(updates.keys())},
        }
    )
    return {"draft": snapshot, "version": version}


@app.post("/outreach/drafts/{draft_id}/ai-edit")
async def create_inline_ai_edit(draft_id: str, request: InlineAIEditRequest):
    """Create an inline AI edit preview. Optionally apply immediately."""
    draft = await supabase_client.get_email_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    company_id = draft.get("company_id")
    context: dict[str, Any] = {"draft": draft}
    if company_id:
        context["personalization"] = await supabase_client.get_personalization_profile(request.user_id, company_id)

    edit_request = {
        "id": str(uuid.uuid4()),
        "draft_id": draft_id,
        "user_id": request.user_id,
        "instruction": request.instruction,
        "selected_text": request.selected_text,
        "status": "previewed",
        "metadata": {"subject": request.subject},
    }
    stored_request = await supabase_client.insert_ai_edit_request(edit_request)
    preview = await EmailEditorService().edit_selection(
        instruction=request.instruction,
        selected_text=request.selected_text,
        full_body=request.full_body,
        subject=request.subject or draft.get("subject") or "",
        context=context,
    )
    await supabase_client.update_ai_edit_request(
        stored_request.get("id"),
        {"proposed_text": preview["replacement_text"], "diff": preview["diff"], "status": "previewed"},
    )

    if request.auto_apply:
        apply_request = DraftUpdateRequest(
            user_id=request.user_id,
            body=preview["updated_body"],
        )
        update = await update_email_draft(draft_id, apply_request)
        await supabase_client.update_ai_edit_request(stored_request.get("id"), {"status": "accepted"})
        preview["applied"] = True
        preview["draft"] = update["draft"]
    else:
        preview["applied"] = False
    preview["ai_edit_request_id"] = stored_request.get("id")
    return preview


@app.post("/outreach/drafts/{draft_id}/ai-edit/apply")
async def apply_inline_ai_edit(draft_id: str, request: ApplyAIEditRequest):
    draft = await supabase_client.get_email_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    body = draft.get("body") or ""
    if request.original_text and request.original_text in body:
        body = body.replace(request.original_text, request.replacement_text, 1)
    else:
        body = request.replacement_text
    update = await update_email_draft(draft_id, DraftUpdateRequest(user_id=request.user_id, body=body))
    if request.ai_edit_request_id:
        await supabase_client.update_ai_edit_request(request.ai_edit_request_id, {"status": "accepted"})
    return update


@app.post("/outreach/drafts/{draft_id}/versions/{version_id}/restore")
async def restore_email_version(draft_id: str, version_id: str, user_id: str = Query(...)):
    version = await supabase_client.get_email_version(version_id)
    if not version or version.get("draft_id") != draft_id:
        raise HTTPException(status_code=404, detail="Version not found")
    update = await update_email_draft(
        draft_id,
        DraftUpdateRequest(
            user_id=user_id,
            subject=version.get("subject"),
            body=version.get("body"),
            selected_variant=version.get("selected_variant"),
            recipient_email=version.get("recipient_email"),
        ),
    )
    return {"draft": update["draft"], "restored_from": version}


@app.get("/outreach/drafts/{draft_id}/versions/compare")
async def compare_email_versions(draft_id: str, left_version_id: str, right_version_id: str):
    left = await supabase_client.get_email_version(left_version_id)
    right = await supabase_client.get_email_version(right_version_id)
    if not left or not right or left.get("draft_id") != draft_id or right.get("draft_id") != draft_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return VersioningService().compare(left, right)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Resume Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    """Upload a resume version and extract text/skills for agent knowledge base."""
    try:
        content = await file.read()
        extracted_text = _extract_resume_text(file.filename or "resume", content)
        extracted_skills = _extract_skills(extracted_text)

        resume = await supabase_client.insert_resume(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "file_name": file.filename,
                "version_label": f"{file.filename} ({datetime.utcnow().strftime('%Y-%m-%d %H:%M')})",
                "extracted_text": extracted_text,
                "extracted_skills": extracted_skills,
                "is_active": False,
            }
        )

        # First upload for this user becomes active.
        if resume.get("id"):
            existing = await supabase_client.get_resumes(user_id)
            if len(existing) == 1:
                await supabase_client.set_active_resume(user_id, resume["id"])

        return {"resume": resume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resumes")
async def get_resumes(user_id: str):
    try:
        resumes = await supabase_client.get_resumes(user_id)
        return {"resumes": resumes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resumes/{resume_id}/activate")
async def activate_resume(resume_id: str, user_id: str):
    try:
        result = await supabase_client.set_active_resume(user_id=user_id, resume_id=resume_id)
        return {"resume": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user_id: str):
    try:
        result = await supabase_client.delete_resume(user_id=user_id, resume_id=resume_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Pipeline Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/pipeline")
async def get_pipeline():
    """Get the full outreach pipeline."""
    try:
        result = await supabase_client.get_pipeline()
        return {"pipeline": result}
    except Exception:
        return {"pipeline": []}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "OfferHunter AI API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "source_file": str(Path(__file__).resolve()),
        "has_debug_logs_route": any(getattr(route, "path", "") == "/debug/logs/frontend" for route in app.routes),
    }


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Company Finder Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.post("/company-finder/run")
async def run_company_finder(request: CompanyFinderRunRequest):
    """
    Run the full Company Finder pipeline for a user.
    Parses resume, collects preferences, discovers companies, ranks them, finds contacts.
    Returns a task_id for SSE tracking.
    """
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    agent = CompanyFinderAgent(logger=logger)

    # Resolve resume text
    resume_text = request.resume_text
    if not resume_text and request.resume_version_id:
        resume = await supabase_client.get_resume(request.resume_version_id)
        if resume:
            resume_text = resume.get("extracted_text", "")
    if not resume_text:
        active = await supabase_client.get_active_resume(request.user_id)
        if active:
            resume_text = active.get("extracted_text", "")

    if not resume_text:
        raise HTTPException(status_code=400, detail="No resume found. Please upload a resume first.")

    async def run_pipeline():
        try:
            preferences = normalize_preference_payload(request.preferences)
            excluded_domains: set[str] | None = None
            if not request.rediscover:
                memory = await _load_company_memory(request.user_id)
                excluded_domains = memory["seen_domains"] | memory["disliked_domains"] | memory["applied_domains"]
                preferences["_excluded_names"] = sorted(memory["seen_names"])
                preferences["_seen_domains"] = sorted(memory["seen_domains"])
                preferences["_disliked_domains"] = sorted(memory["disliked_domains"])
                preferences["_applied_domains"] = sorted(memory["applied_domains"])

            result = await agent.run_full_pipeline(
                task_id=task_id,
                user_id=request.user_id,
                resume_text=resume_text,
                preferences=preferences,
                count=request.count,
                excluded_domains=excluded_domains,
            )
            # Cache companies in memory so the GET endpoint can serve them
            # even when Supabase is not configured
            if result and result.get("companies"):
                _merge_user_company_cache(request.user_id, result["companies"])
        except Exception as e:
            await logger.emit(
                agent_name="CompanyFinderAgent",
                task_id=task_id,
                status="failed",
                message=f"Pipeline failed: {str(e)}",
            )

    asyncio.create_task(run_pipeline())
    return {"task_id": task_id, "status": "started"}


@app.post("/company-finder/discover")
async def discover_companies(request: CompanyFinderRunRequest):
    """
    Run discovery only (no resume parse) using an existing profile + preferences.
    """
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    agent = CompanyFinderAgent(logger=logger)

    profile = await supabase_client.get_parsed_profile(request.user_id) or {}
    preferences = (
        request.preferences
        or await supabase_client.get_user_preferences(request.user_id)
        or {}
    )
    preferences = normalize_preference_payload(preferences)

    excluded_domains: set[str] | None = None
    if not request.rediscover:
        memory = await _load_company_memory(request.user_id)
        excluded_domains = memory["seen_domains"] | memory["disliked_domains"] | memory["applied_domains"]
        preferences["_excluded_names"] = sorted(memory["seen_names"])
        preferences["_seen_domains"] = sorted(memory["seen_domains"])
        preferences["_disliked_domains"] = sorted(memory["disliked_domains"])
        preferences["_applied_domains"] = sorted(memory["applied_domains"])

    async def run_discovery():
        try:
            companies = await agent.run_discovery_only(
                task_id=task_id,
                profile=profile,
                preferences=preferences,
                count=request.count,
                user_id=request.user_id,
                excluded_domains=excluded_domains,
            )
            if companies:
                _merge_user_company_cache(request.user_id, companies)
        except Exception as e:
            await logger.emit(
                agent_name="CompanyFinderAgent",
                task_id=task_id,
                status="failed",
                message=f"Discovery failed: {str(e)}",
            )

    asyncio.create_task(run_discovery())
    return {"task_id": task_id, "status": "started"}


@app.post("/company-finder/preferences/chat")
async def preference_chat(request: PreferenceChatRequest):
    """
    Single turn of the preference collection conversation.
    """
    profile = await supabase_client.get_parsed_profile(request.user_id) or {}
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    agent = CompanyFinderAgent(logger=logger)

    task_id = str(uuid.uuid4())
    result = await agent.run_preference_chat(
        task_id=task_id,
        user_id=request.user_id,
        user_message=request.message,
        history=request.history,
        profile=profile,
        current_prefs=request.current_prefs,
    )

    # Save conversation messages
    await supabase_client.insert_conversation_message(
        request.user_id, "user", request.message
    )
    await supabase_client.insert_conversation_message(
        request.user_id, "assistant", result["reply"]
    )

    return result


@app.get("/company-finder/preferences/opener")
async def preference_opener(user_id: str):
    """
    Get the initial message to start the preference collection conversation.
    """
    profile = await supabase_client.get_parsed_profile(user_id) or {}
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    agent = CompanyFinderAgent(logger=logger)
    opener = agent.get_preference_opener(profile)
    return {"message": opener}


@app.post("/company-finder/preferences")
async def save_preferences(request: SavePreferencesRequest):
    """Save user preferences directly (for bulk updates)."""
    try:
        normalized_preferences = normalize_preference_payload(request.preferences)
        result = await supabase_client.upsert_user_preferences({
            "user_id": request.user_id,
            **normalized_preferences,
        })
        return {"preferences": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/company-finder/preferences/{user_id}")
async def get_preferences(user_id: str):
    """Get user preferences."""
    try:
        result = await supabase_client.get_user_preferences(user_id)
        return {"preferences": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/company-finder/conversation/{user_id}")
async def get_conversation_history(user_id: str, context: str = "preferences"):
    """Get the conversation history for a user."""
    try:
        history = await supabase_client.get_conversation_history(user_id, context)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/parse-resume")
async def parse_resume_profile(request: ParseResumeRequest):
    """
    Parse (or re-parse) the active resume for a user and store the structured profile.
    """
    resume_text = ""
    if request.resume_version_id:
        resume = await supabase_client.get_resume(request.resume_version_id)
        resume_text = (resume or {}).get("extracted_text", "")
    if not resume_text:
        active = await supabase_client.get_active_resume(request.user_id)
        resume_text = (active or {}).get("extracted_text", "")

    if not resume_text:
        raise HTTPException(status_code=400, detail="No resume found for this user.")

    parser = ResumeParserService()
    profile = await parser.parse(resume_text)

    saved = await supabase_client.upsert_parsed_profile({
        "user_id": request.user_id,
        **{k: v for k, v in profile.items() if k != "raw_text"},
        "raw_text": resume_text,
    })
    return {"profile": saved}


@app.get("/company-finder/profile/{user_id}")
async def get_parsed_profile(user_id: str):
    """Get the AI-parsed resume profile for a user."""
    try:
        result = await supabase_client.get_parsed_profile(user_id)
        return {"profile": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _workspace_row_to_company(row: dict[str, Any]) -> dict[str, Any]:
    company = _hydrate_company_work_mode(dict(row.get("companies") or {}))
    metadata = row.get("metadata") or {}

    if not company:
        company = {
            "id": row.get("company_id"),
            "domain": metadata.get("domain", ""),
            "source": row.get("source", "unknown"),
            "relevance_score": row.get("ranking_score") or 0,
            "work_mode": metadata.get("work_mode", "unknown"),
            "remote_confidence": metadata.get("remote_confidence", 0.0),
            "work_mode_reasoning": metadata.get("work_mode_reasoning", []),
        }
        company = _hydrate_company_work_mode(company)

    # Prefer ranking data stored directly on the user_companies row
    # (avoids a fragile cross-table join that doesn't work reliably with supabase-py)
    ranking_metadata: dict[str, Any] = row.get("ranking_metadata") or {}
    if ranking_metadata:
        company["ranking"] = {
            k: v
            for k, v in ranking_metadata.items()
            if k not in {"id", "company_id", "user_id", "created_at", "updated_at"}
        }
    company["match_score"] = (
        ranking_metadata.get("match_score")
        or row.get("ranking_score")
        or company.get("relevance_score")
        or 0
    )

    company["workspace"] = {
        "id": row.get("id"),
        "source": row.get("source"),
        "discovered_at": row.get("discovered_at"),
        "status": row.get("status"),
        "orchestration_stage": row.get("orchestration_stage"),
        "liked": row.get("liked"),
        "disliked": row.get("disliked"),
        "archived": row.get("archived", False),
        "removed": row.get("removed", False),
        "manually_added": row.get("manually_added", False),
        "personalization_completed": row.get("personalization_completed", False),
        "outreach_started": row.get("outreach_started", False),
        "outreach_sent": row.get("outreach_sent", False),
        "notes": row.get("notes") or "",
        "application_strategy": row.get("application_strategy") or "",
        "ranking_score": row.get("ranking_score"),
        "ranking_explanation": row.get("ranking_explanation") or "",
        "hidden_by_preferences": bool((metadata.get("preference_enforcement") or {}).get("hidden_by_preferences")),
    }
    if metadata.get("preference_enforcement"):
        company["preference_enforcement"] = metadata.get("preference_enforcement")
    return company


def _normalize_company_domain(company: dict[str, Any]) -> str:
    domain = (company.get("domain") or company.get("website_url") or "").strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    return domain.removeprefix("www.")


async def _persist_recovered_workspace_companies(
    user_id: str,
    companies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist company snapshots recovered from old completed agent events."""
    recovered: list[dict[str, Any]] = []
    for raw in companies:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        snapshot = deepcopy(raw)
        ranking = deepcopy(snapshot.get("ranking") or {})
        contacts = deepcopy(snapshot.get("contacts") or [])
        company = {
            k: v
            for k, v in snapshot.items()
            if k not in {"ranking", "contacts", "workspace", "company_contacts", "_persistence_error"}
        }
        company["domain"] = _normalize_company_domain(company) or re.sub(
            r"[^a-zA-Z0-9]",
            "",
            str(company.get("name", "company")).lower(),
        ) + ".com"

        try:
            saved = await supabase_client.upsert_company({**company, "user_id": user_id})
            company_id = saved.get("id") or company.get("id")
            if not company_id:
                continue
            company["id"] = company_id
            company["ranking"] = ranking
            company["contacts"] = contacts

            if ranking:
                await supabase_client.upsert_company_ranking({
                    "user_id": user_id,
                    "company_id": company_id,
                    **ranking,
                })

            await supabase_client.upsert_user_company({
                "user_id": user_id,
                "company_id": company_id,
                "source": company.get("source", "recovered"),
                "status": "active",
                "orchestration_stage": "Personalization",
                "ranking_score": ranking.get("match_score", company.get("relevance_score", 0)),
                "ranking_explanation": ranking.get("match_explanation", ""),
                "ranking_metadata": ranking,
                "application_strategy": company.get("application_strategy", ""),
                "metadata": {
                    "domain": company.get("domain"),
                    "recovered_from": "agent_events",
                },
            })
            recovered.append(company)
        except Exception:
            # Keep the recovered snapshot for UI fallback even if the DB schema
            # is still missing the persistent workspace migration.
            company["ranking"] = ranking
            company["contacts"] = contacts
            recovered.append(company)
    return recovered


async def _recover_workspace_from_agent_events(user_id: str, sweep_limit: int = 50) -> list[dict[str, Any]]:
    """
    Repair old runs that emitted completed companies but failed before
    user_companies was durable.
    """
    try:
        state = await supabase_client.get_orchestration_state(user_id)
        task_ids = []
        if state and state.get("last_task_id"):
            task_ids.append(state["last_task_id"])

        runs = await supabase_client.get_agent_runs(user_id, agent_name="CompanyFinderAgent", limit=10)
        for run in runs:
            task_id = run.get("task_id")
            if task_id and task_id not in task_ids:
                task_ids.append(task_id)

        recovered_by_key: dict[str, dict[str, Any]] = {}

        for task_id in task_ids[:25]:
            events = await supabase_client.get_agent_events_for_task(
                task_id,
                agent_name="CompanyFinderAgent",
                status="completed",
                limit=5,
            )
            for event in events:
                metadata = event.get("metadata") or {}
                if metadata.get("user_id") and metadata.get("user_id") != user_id:
                    continue
                companies = metadata.get("companies") or []
                if companies:
                    recovered = await _persist_recovered_workspace_companies(user_id, companies)
                    for company in recovered:
                        key = _company_memory_key(company)
                        if key:
                            recovered_by_key[key] = company

        # Older discovery-only runs did not always create ai_agent_runs, and
        # orchestration_state.last_task_id is overwritten by newer runs. Sweep
        # completed CompanyFinder artifacts too. Newer events include user_id;
        # legacy events do not, so they are treated as repair candidates.
        events = await supabase_client.get_completed_company_finder_events(limit=sweep_limit)
        for event in events:
            metadata = event.get("metadata") or {}
            if metadata.get("user_id") and metadata.get("user_id") != user_id:
                continue
            companies = metadata.get("companies") or []
            if not companies:
                continue
            recovered = await _persist_recovered_workspace_companies(user_id, companies)
            for company in recovered:
                key = _company_memory_key(company)
                if key:
                    recovered_by_key[key] = company

        return list(recovered_by_key.values())
    except Exception:
        return []
    return []


async def _recover_workspace_from_legacy_companies(user_id: str) -> list[dict[str, Any]]:
    """
    Repair older rows that were inserted into companies.user_id before the
    user_companies workspace table became the source of truth.
    """
    try:
        legacy = await supabase_client.get_companies_by_user_id(user_id, limit=500)
    except Exception:
        return []

    recovered: list[dict[str, Any]] = []
    for company in legacy:
        company_id = company.get("id")
        if not company_id:
            continue
        try:
            await supabase_client.upsert_user_company({
                "user_id": user_id,
                "company_id": company_id,
                "source": company.get("source", "legacy"),
                "status": "active",
                "orchestration_stage": "Personalization",
                "ranking_score": company.get("relevance_score", 0),
                "ranking_metadata": {
                    "match_score": company.get("relevance_score", 0),
                    "signal_source": "legacy_companies_user_id",
                },
                "metadata": {
                    "domain": company.get("domain"),
                    "recovered_from": "companies.user_id",
                },
            })
            recovered.append(company)
        except Exception:
            recovered.append(company)
    return recovered


async def _repair_workspace_memory(user_id: str) -> dict[str, Any]:
    """
    Reconcile historical discovery artifacts into user_companies.

    This is intentionally not called from the normal read path. It performs
    write-heavy recovery and can touch many rows, so it runs in the background.
    """
    recovered_by_key: dict[str, dict[str, Any]] = {}

    async def run_step(step: str, coro_factory, timeout: float) -> Any:
        started = time.perf_counter()
        current = _repair_status_for(user_id)
        steps = list(current.get("steps") or [])
        steps.append({"step": step, "status": "running", "started_at": _utc_iso()})
        _set_repair_status(user_id, steps=steps)
        _log_backend_action("workspace_repair.step_started", user_id=user_id, step=step)

        result = await _db_call(
            f"workspace_repair.{step}",
            coro_factory,
            timeout=timeout,
            fallback=[],
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        result_count = len(result) if isinstance(result, list) else 0
        current = _repair_status_for(user_id)
        steps = list(current.get("steps") or [])
        for item in reversed(steps):
            if item.get("step") == step and item.get("status") == "running":
                item.update(
                    {
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "result_count": result_count,
                        "finished_at": _utc_iso(),
                    }
                )
                break
        _set_repair_status(user_id, steps=steps)
        _log_backend_action(
            "workspace_repair.step_completed",
            user_id=user_id,
            step=step,
            duration_ms=duration_ms,
            result_count=result_count,
        )
        return result

    ranking_rows = await run_step(
        "ranking_backfill",
        lambda: supabase_client.backfill_user_companies_from_rankings(user_id),
        timeout=20.0,
    )
    legacy_companies = await run_step(
        "legacy_companies",
        lambda: _recover_workspace_from_legacy_companies(user_id),
        timeout=20.0,
    )

    # Agent-event sweeps are expensive and only needed when lighter repair
    # sources did not recover anything useful.
    event_companies: list[dict[str, Any]] = []
    if not ranking_rows and not legacy_companies:
        event_companies = await run_step(
            "agent_event_sweep",
            lambda: _recover_workspace_from_agent_events(user_id, sweep_limit=50),
            timeout=45.0,
        )

    for row in ranking_rows:
        company = _workspace_row_to_company(row) if row.get("companies") else row
        key = _company_memory_key(company)
        if key:
            recovered_by_key[key] = company
    for company in legacy_companies + event_companies:
        key = _company_memory_key(company)
        if key:
            recovered_by_key[key] = company

    recovered = list(recovered_by_key.values())
    if recovered:
        _merge_user_company_cache(user_id, recovered)

    return {"status": "completed", "recovered_count": len(recovered)}


@app.get("/company-finder/companies")
async def get_discovered_companies(
    user_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    include_archived: bool = Query(False),
    include_removed: bool = Query(False),
    stage: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    """
    Get discovered and ranked companies for a user.
    Includes rankings and contacts.
    """
    preferences: dict[str, Any] = {}
    try:
        preferences = normalize_preference_payload(
            await _db_call(
                "companies.preferences",
                lambda: supabase_client.get_user_preferences(user_id),
                timeout=1.5,
                fallback={},
            )
            or {}
        )
        rows = await _db_call(
            "companies.user_companies",
            lambda: supabase_client.get_user_companies(
                user_id=user_id,
                limit=limit,
                offset=offset,
                include_archived=include_archived,
                include_removed=include_removed,
                stage=stage,
                source=source,
            ),
            timeout=4.0,
            fallback=[],
        )

        companies = []
        for row in rows:
            company = _workspace_row_to_company(row)
            score = (
                (company.get("ranking") or {}).get("match_score")
                or company.get("match_score")
                or row.get("ranking_score")
                or company.get("relevance_score")
                or 0
            )
            if score >= min_score:
                companies.append(company)

        visible_companies, hidden_by_preferences, archived_companies = partition_workspace_companies(companies, preferences)
        if visible_companies or hidden_by_preferences or archived_companies:
            return {
                "companies": visible_companies,
                "visible_companies": visible_companies,
                "hidden_by_preferences": hidden_by_preferences,
                "archived_companies": archived_companies,
                "total": len(visible_companies),
                "offset": offset,
                "limit": limit,
            }

        # ── Fallback 1: legacy company_rankings table ──────────────────────────
        # user_companies might be empty if migration 005 hasn't been run or
        # companies were stored before the new persistence layer was added.
        ranking_rows = await _db_call(
            "companies.legacy_rankings",
            lambda: supabase_client.get_company_rankings(user_id, limit=limit),
            timeout=3.0,
            fallback=[],
        )
        if ranking_rows:
            legacy = []
            for row in ranking_rows:
                c = dict(row.get("companies") or {})
                if not c:
                    continue
                c["ranking"] = {
                    k: v for k, v in row.items()
                    if k not in {"id", "company_id", "user_id", "created_at", "updated_at", "companies"}
                }
                c["match_score"] = row.get("match_score", 0)
                legacy.append(_hydrate_company_work_mode(c))
            if legacy:
                visible_companies, hidden_by_preferences, archived_companies = partition_workspace_companies(legacy, preferences)
                return {
                    "companies": visible_companies[:limit],
                    "visible_companies": visible_companies[:limit],
                    "hidden_by_preferences": hidden_by_preferences,
                    "archived_companies": archived_companies,
                    "total": len(visible_companies),
                    "offset": 0,
                    "limit": limit,
                }

        # ── Fallback 2: in-memory cache (cleared on server restart) ───────────
        cached = _user_companies_cache.get(user_id, [])
        if cached:
            hydrated_cached = [_hydrate_company_work_mode(c) for c in cached]
            filtered = [c for c in hydrated_cached if c.get("ranking", {}).get("match_score", c.get("match_score", 1.0)) >= min_score]
            visible_companies, hidden_by_preferences, archived_companies = partition_workspace_companies(filtered, preferences)
            return {
                "companies": visible_companies[:limit],
                "visible_companies": visible_companies[:limit],
                "hidden_by_preferences": hidden_by_preferences,
                "archived_companies": archived_companies,
                "total": len(visible_companies),
                "offset": 0,
                "limit": limit,
            }

        return {"companies": [], "total": 0, "offset": offset, "limit": limit}
    except Exception as e:
        import traceback
        print(f"[companies endpoint] ERROR for user {user_id}: {e}\n{traceback.format_exc()}")
        # Fall back to in-memory cache on any DB error
        cached = _user_companies_cache.get(user_id, [])
        if cached:
            hydrated_cached = [_hydrate_company_work_mode(c) for c in cached]
            filtered = [c for c in hydrated_cached if c.get("ranking", {}).get("match_score", c.get("match_score", 1.0)) >= min_score]
            visible_companies, hidden_by_preferences, archived_companies = partition_workspace_companies(filtered, preferences)
            return {
                "companies": visible_companies[:limit],
                "visible_companies": visible_companies[:limit],
                "hidden_by_preferences": hidden_by_preferences,
                "archived_companies": archived_companies,
                "total": len(visible_companies),
            }
        return {"companies": [], "total": 0, "error": str(e)}


@app.get("/company-finder/companies/repair/status")
async def get_company_workspace_repair_status(user_id: str = Query(...)):
    return _repair_status_for(user_id)


@app.post("/company-finder/companies/repair", status_code=202)
async def repair_company_workspace(request: WorkspaceRepairRequest):
    """
    Start non-blocking repair of historical discovery artifacts.

    Normal company reads must stay fast. This endpoint reconciles legacy rows
    and old agent-event company payloads into user_companies in the background.
    """
    user_id = request.user_id

    if user_id in _workspace_repairs_running:
        current = _repair_status_for(user_id)
        return {
            "status": current.get("status") or "running",
            "job_id": current.get("job_id"),
            "user_id": user_id,
        }

    job_id = str(uuid.uuid4())
    _workspace_repairs_running.add(user_id)
    queued = _set_repair_status(
        user_id,
        status="queued",
        job_id=job_id,
        recovered_count=0,
        error=None,
        steps=[],
        last_started_at=None,
        last_finished_at=None,
    )

    async def run_repair():
        status_payload = _set_repair_status(
            user_id,
            status="running",
            job_id=job_id,
            last_started_at=_utc_iso(),
            last_finished_at=None,
            error=None,
        )
        await _persist_workspace_repair_status(user_id, status_payload)
        try:
            result = await _repair_workspace_memory(user_id)
            status_payload = _set_repair_status(
                user_id,
                status="completed",
                job_id=job_id,
                recovered_count=result.get("recovered_count", 0),
                last_finished_at=_utc_iso(),
                error=None,
            )
            await _persist_workspace_repair_status(user_id, status_payload)
        except Exception as exc:
            status_payload = _set_repair_status(
                user_id,
                status="failed",
                job_id=job_id,
                error=str(exc),
                last_finished_at=_utc_iso(),
            )
            await _persist_workspace_repair_status(user_id, status_payload)
            _log_backend_action("workspace_repair.failed", user_id=user_id, job_id=job_id, error=str(exc))
        finally:
            _workspace_repairs_running.discard(user_id)

    asyncio.create_task(run_repair())
    _log_backend_action("workspace_repair.queued", user_id=user_id, job_id=job_id)

    return {
        "status": queued.get("status", "queued"),
        "job_id": job_id,
        "user_id": user_id,
    }



@app.post("/company-finder/companies/manual")
async def add_manual_company(request: ManualCompanyRequest):
    """Scrape a user-supplied company website, rank it, persist it, and return it."""
    try:
        logger = AgentEventLogger(event_queue=_broadcast_queue)
        agent = CompanyFinderAgent(logger=logger)
        task_id = str(uuid.uuid4())

        profile = await supabase_client.get_parsed_profile(request.user_id) or {}
        preferences = await supabase_client.get_user_preferences(request.user_id) or {}

        company = await agent.add_manual_company(
            task_id=task_id,
            user_id=request.user_id,
            website_url=request.website_url,
            profile=profile,
            preferences=preferences,
        )

        cached = _user_companies_cache.get(request.user_id, [])
        new_id = company.get("id")
        new_domain = (company.get("domain") or "").lower()

        deduped = []
        for existing in cached:
            existing_id = existing.get("id")
            existing_domain = (existing.get("domain") or "").lower()

            same_id = bool(new_id) and bool(existing_id) and existing_id == new_id
            same_domain = bool(new_domain) and bool(existing_domain) and existing_domain == new_domain

            if not same_id and not same_domain:
                deduped.append(existing)

        _merge_user_company_cache(request.user_id, [company, *deduped])

        return {"company": company, "task_id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/company-finder/companies/{company_id}")
async def get_company_detail(company_id: str, user_id: Optional[str] = Query(None)):
    """Get full company detail including contacts, jobs, and ranking."""
    try:
        company = await supabase_client.get_company_detail(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        hydrated = _hydrate_company_work_mode(company)
        if user_id:
            preferences = normalize_preference_payload(await supabase_client.get_user_preferences(user_id) or {})
            visible = apply_hard_constraints([hydrated], preferences)
            if not visible:
                raise HTTPException(status_code=404, detail="Company hidden by current preferences")
            hydrated = visible[0]
        return {"company": hydrated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/company-finder/companies/{company_id}")
async def update_workspace_company(company_id: str, request: CompanyWorkspaceUpdateRequest):
    """Update persistent user-company workspace state (archive/remove/notes/stage)."""
    try:
        updates = {
            k: v
            for k, v in request.model_dump().items()
            if k != "user_id" and v is not None
        }
        if not updates:
            return {"updated": False, "reason": "No fields provided"}

        row = await supabase_client.update_user_company(request.user_id, company_id, updates)
        return {"updated": True, "workspace": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/companies/{company_id}/feedback")
async def save_company_feedback(company_id: str, request: CompanyFeedbackRequest):
    """Persist like/dislike feedback and immediately reflect it in workspace state."""
    if request.feedback_type not in {"like", "dislike"}:
        raise HTTPException(status_code=400, detail="feedback_type must be 'like' or 'dislike'")

    try:
        feedback = await supabase_client.record_company_feedback(
            user_id=request.user_id,
            company_id=company_id,
            feedback_type=request.feedback_type,
            feedback_reason=request.feedback_reason or "",
        )

        await supabase_client.update_user_company(
            request.user_id,
            company_id,
            {
                "liked": request.feedback_type == "like",
                "disliked": request.feedback_type == "dislike",
            },
        )

        return {"feedback": feedback}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/continue")
async def continue_company_discovery(request: ContinueDiscoveryRequest):
    """
    Continue discovery without replacing workspace.
    Supports optional source_mode to bias source selection through preferences.
    """
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    agent = CompanyFinderAgent(logger=logger)

    profile = await supabase_client.get_parsed_profile(request.user_id) or {}
    preferences = await supabase_client.get_user_preferences(request.user_id) or {}
    if request.source_mode:
        preferences["source_mode"] = request.source_mode

    # ── Build exclusion set from every company already in the workspace ───────
    excluded_domains: set[str] = set()
    excluded_names: set[str] = set()

    # Pull from DB first (most reliable)
    try:
        existing_rows = await supabase_client.get_user_companies(
            user_id=request.user_id, limit=500, include_archived=True, include_removed=True
        )
        for row in existing_rows:
            c = row.get("companies") or {}
            domain = (c.get("domain") or row.get("metadata", {}).get("domain") or "").lower().strip()
            name = (c.get("name") or "").lower().strip()
            if domain:
                excluded_domains.add(domain)
            if name:
                excluded_names.add(name)
    except Exception:
        pass

    # Also pull from in-memory cache as a safety net
    for c in _user_companies_cache.get(request.user_id, []):
        domain = (c.get("domain") or "").lower().strip()
        name = (c.get("name") or "").lower().strip()
        if domain:
            excluded_domains.add(domain)
        if name:
            excluded_names.add(name)

    # Determine discovery round from existing session count to vary AI framing
    try:
        sessions = await supabase_client.get_discovery_sessions(request.user_id, limit=100)
        discovery_round = len(sessions) + 1
    except Exception:
        discovery_round = 2

    preferences["_excluded_names"] = list(excluded_names)
    preferences["_discovery_round"] = discovery_round

    async def run_discovery():
        try:
            companies = await agent.run_discovery_only(
                task_id=task_id,
                profile=profile,
                preferences=preferences,
                count=request.count,
                user_id=request.user_id,
                excluded_domains=excluded_domains,
            )

            _merge_user_company_cache(request.user_id, companies)
        except Exception as e:
            await logger.emit(
                agent_name="CompanyFinderAgent",
                task_id=task_id,
                status="failed",
                message=f"Continue discovery failed: {str(e)}",
            )

    asyncio.create_task(run_discovery())
    return {"task_id": task_id, "status": "started", "excluded_count": len(excluded_domains)}


@app.get("/company-finder/discovery-sessions/{user_id}")
async def get_discovery_session_history(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        sessions = await supabase_client.get_discovery_sessions(user_id, limit=limit, offset=offset)
        return {"sessions": sessions, "total": len(sessions), "offset": offset, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/company-finder/source-logs/{user_id}")
async def get_discovery_source_logs(
    user_id: str,
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=300),
):
    try:
        logs = await supabase_client.get_discovery_source_logs(
            user_id=user_id,
            session_id=session_id,
            limit=limit,
        )
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/company-finder/orchestration/{user_id}")
async def get_orchestration_state(user_id: str):
    try:
        state = await _db_call(
            "orchestration_state.get",
            lambda: supabase_client.get_orchestration_state(user_id),
            timeout=2.5,
            fallback=None,
        )
        return {"state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/orchestration/{user_id}")
async def update_orchestration_state(user_id: str, request: OrchestrationStateUpdateRequest):
    try:
        payload = {"user_id": user_id}
        payload.update({
            k: v for k, v in request.model_dump().items() if v is not None
        })
        state = await supabase_client.upsert_orchestration_state(payload)
        return {"state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/companies/{company_id}/handoff")
async def handoff_to_agent(
    company_id: str,
    target_agent: str = Query(..., description="Agent to hand off to: email-writer or resume-tailor"),
    user_id: str = Query(...),
):
    """
    Hand off a company to the next user-selected workflow.

    email-writer runs the full cold-email pipeline:
    Personalization -> Contact Discovery -> Email Writer -> Human Review.
    """
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)
    target = target_agent.lower()

    if target not in {"email-writer", "resume-tailor"}:
        raise HTTPException(
            status_code=400,
            detail="Company actions are limited to 'email-writer' and 'resume-tailor'",
        )

    async def load_context() -> tuple[dict[str, Any], dict[str, Any]]:
        company = await supabase_client.get_company_detail(company_id)
        if not company:
            raise ValueError("Company not found")

        profile = await supabase_client.get_parsed_profile(user_id) or {}
        preferences = normalize_preference_payload(await supabase_client.get_user_preferences(user_id) or {})
        resume = await supabase_client.get_active_resume(user_id) or {}
        ranking = (await supabase_client.get_company_rankings(user_id, limit=1)) or [{}]
        handoff_context = {
            "company": company,
            "user_id": user_id,
            "user_profile": profile,
            "preferences": preferences,
            "resume": resume,
            "ranking": ranking[0] if ranking else {},
            "contacts": company.get("company_contacts", []),
            "matched_skills": profile.get("skills", []),
            "relevant_projects": profile.get("projects", []),
        }
        return company, handoff_context

    async def run_cold_email_pipeline() -> None:
        try:
            await logger.emit(
                agent_name="EmailWriterAgent",
                task_id=task_id,
                status="started",
                message="Generating selected-company cold email draft",
                metadata={"company_id": company_id},
            )
            result = await _generate_selected_company_email(
                GenerateEmailDraftRequest(
                    user_id=user_id,
                    company_id=company_id,
                    outreach_type="cold_email",
                )
            )
            draft = result["draft"]
            await logger.emit(
                agent_name="EmailWriterAgent",
                task_id=task_id,
                status="completed",
                message=f"Cold email draft ready for {draft.get('company_name', 'company')}",
                metadata={"company_id": company_id, "draft_id": draft.get("id")},
            )
            await logger.emit(
                agent_name="HumanReviewAgent",
                task_id=task_id,
                status="started",
                message=f"Draft for {draft.get('company_name', 'company')} is ready for human review",
                metadata={"company_id": company_id, "draft_id": draft.get("id")},
            )
            return

            company, handoff_context = await load_context()
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "Personalization",
                "active_agents": ["PersonalizationAgent"],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {"step": "personalization", "company_id": company_id},
            })
            personalizer = PersonalizationAgent(logger=logger)
            personalization = await personalizer.run(task_id=task_id, **handoff_context)

            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "EmailWriter",
                "active_agents": ["ContactDiscoveryAgent"],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {"step": "contact_discovery", "company_id": company_id},
            })
            await logger.emit(
                agent_name="ContactDiscoveryAgent",
                task_id=task_id,
                status="started",
                message=f"Finding best people to contact at {company.get('name', 'this company')}",
                metadata={"company_id": company_id, "company": company.get("name")},
            )
            contact_result = await ContactDiscoveryService().discover(company)
            contacts = [
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "company_id": company_id,
                    "name": c.get("name") or "",
                    "role": c.get("role") or c.get("title") or "",
                    "title": c.get("title") or c.get("role") or "",
                    "email": c.get("email") or "",
                    "confidence": c.get("confidence") or 0,
                    "source": c.get("source") or "",
                    "priority_score": c.get("priority_score") or 0,
                    "verified": c.get("verified") or False,
                    "contact_type": c.get("contact_type") or "other",
                    "metadata": c,
                }
                for c in contact_result.get("contacts", [])
                if c.get("email")
            ]
            stored_contacts = await supabase_client.upsert_outreach_contacts(contacts)
            best_contact = stored_contacts[0] if stored_contacts else None
            await logger.emit(
                agent_name="ContactDiscoveryAgent",
                task_id=task_id,
                status="completed",
                message=f"Ranked {len(stored_contacts)} outreach contacts for {company.get('name', 'company')}",
                metadata={"company_id": company_id, "contacts": stored_contacts[:5]},
            )

            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "EmailWriter",
                "active_agents": ["EmailWriterAgent"],
                "paused_state": False,
                "last_task_id": task_id,
                "progress": {"step": "email_writer", "company_id": company_id},
            })
            writer = EmailWriterAgent(logger=logger)
            draft = await writer.run(
                task_id=task_id,
                **handoff_context,
                personalization=personalization,
                recipient=best_contact,
                outreach_type="cold_email",
            )
            _merge_outreach_draft_cache(user_id, draft)
            await supabase_client.update_user_company(
                user_id=user_id,
                company_id=company_id,
                updates={
                    "orchestration_stage": "Review",
                    "personalization_completed": True,
                    "outreach_started": True,
                },
            )
            await supabase_client.upsert_orchestration_state({
                "user_id": user_id,
                "current_stage": "Review",
                "active_agents": ["HumanReviewAgent"],
                "paused_state": True,
                "last_task_id": task_id,
                "progress": {
                    "step": "human_review",
                    "company_id": company_id,
                    "draft_id": draft.get("id"),
                },
            })
            await logger.emit(
                agent_name="HumanReviewAgent",
                task_id=task_id,
                status="started",
                message=f"Draft for {company.get('name', 'company')} is ready for human review",
                metadata={"company_id": company_id, "draft_id": draft.get("id")},
            )
        except Exception as exc:
            await logger.emit(
                agent_name="EmailWriterAgent",
                task_id=task_id,
                status="failed",
                message=f"Cold email pipeline failed: {str(exc)}",
                metadata={"company_id": company_id},
            )

    if target == "email-writer":
        asyncio.create_task(run_cold_email_pipeline())
    else:
        async def run_resume_tailor() -> None:
            try:
                company, handoff_context = await load_context()
                await supabase_client.upsert_orchestration_state({
                    "user_id": user_id,
                    "current_stage": "Review",
                    "active_agents": ["ResumeTailorAgent"],
                    "paused_state": False,
                    "last_task_id": task_id,
                    "progress": {"step": "resume_tailor", "company_id": company_id},
                })
                await supabase_client.update_user_company(
                    user_id=user_id,
                    company_id=company_id,
                    updates={"orchestration_stage": "Review"},
                )
                agent = ResumeTailorAgent(logger=logger)
                await agent.run(task_id=task_id, **handoff_context)
                await logger.emit(
                    agent_name="HumanReviewAgent",
                    task_id=task_id,
                    status="started",
                    message=f"Tailored resume for {company.get('name', 'company')} is ready for review",
                    metadata={"company_id": company_id},
                )
            except Exception as exc:
                await logger.emit(
                    agent_name="ResumeTailorAgent",
                    task_id=task_id,
                    status="failed",
                    message=f"Resume tailoring failed: {str(exc)}",
                    metadata={"company_id": company_id},
                )

        asyncio.create_task(run_resume_tailor())

    return {
        "task_id": task_id,
        "status": "started",
        "target_agent": target_agent,
        "company": company_id,
    }


@app.get("/company-finder/agent-runs/{user_id}")
async def get_agent_runs(user_id: str, agent_name: Optional[str] = None):
    """Get AI agent run history for a user."""
    try:
        runs = await supabase_client.get_agent_runs(user_id, agent_name=agent_name)
        return {"runs": runs}
    except Exception as e:
        return {"runs": [], "error": str(e)}


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Mock data helpers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _extract_resume_text(file_name: str, content: bytes) -> str:
    lower_name = file_name.lower()

    if lower_name.endswith(".txt") or lower_name.endswith(".md"):
        return content.decode("utf-8", errors="ignore").strip()

    if lower_name.endswith(".pdf"):
        try:
            from io import BytesIO
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        except Exception:
            return content.decode("utf-8", errors="ignore").strip()

    if lower_name.endswith(".docx"):
        try:
            from io import BytesIO
            import docx

            doc = docx.Document(BytesIO(content))
            return "\n".join([p.text for p in doc.paragraphs]).strip()
        except Exception:
            return content.decode("utf-8", errors="ignore").strip()

    return content.decode("utf-8", errors="ignore").strip()


def _extract_skills(text: str | None) -> list[str]:
    if not text:
        return []

    skill_keywords = [
        "python",
        "fastapi",
        "django",
        "flask",
        "javascript",
        "typescript",
        "react",
        "next.js",
        "node.js",
        "sql",
        "postgres",
        "supabase",
        "aws",
        "gcp",
        "docker",
        "kubernetes",
        "machine learning",
        "deep learning",
        "pytorch",
        "tensorflow",
        "langchain",
        "openai",
    ]

    normalized = re.sub(r"\s+", " ", text.lower())
    found = [skill for skill in skill_keywords if skill in normalized]
    return list(dict.fromkeys(found))


def _mock_events() -> list[dict]:
    now = datetime.utcnow()
    return [
        {
            "id": str(uuid.uuid4()),
            "agent_name": "CompanyFinderAgent",
            "task_id": "task-001",
            "status": "completed",
            "message": "Found 12 companies matching Python/ML skills",
            "metadata": {"count": 12},
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "agent_name": "PersonalizationAgent",
            "task_id": "task-002",
            "status": "completed",
            "message": "Extracted insights for Stripe",
            "metadata": {"company": "Stripe"},
            "created_at": now.isoformat(),
        },
    ]


def _mock_emails(status: Optional[str] = None) -> list[dict]:
    emails = [
        {
            "id": "email-001",
            "company_id": "c-001",
            "company_name": "Stripe",
            "subject": "Experienced ML Engineer Ã¢â‚¬â€ Excited About Stripe's Infrastructure",
            "body": "Hi,\n\nI would love to join Stripe...\n\nBest,\n[Your Name]",
            "status": "pending_approval",
            "created_at": datetime.utcnow().isoformat(),
        }
    ]
    if status:
        return [e for e in emails if e["status"] == status]
    return emails
