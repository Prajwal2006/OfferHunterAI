"""
OfferHunter AI Ã¢â‚¬â€ FastAPI Backend
"""
import asyncio
import json
import re
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from .db.supabase import supabase_client
    from .agents.event_logger import AgentEventLogger
    from .agents.company_finder import CompanyFinderAgent
    from .agents.personalization import PersonalizationAgent
    from .agents.email_writer import EmailWriterAgent
    from .agents.resume_tailor import ResumeTailorAgent
    from .agents.email_sender import EmailSenderAgent
    from .agents.follow_up import FollowUpAgent
    from .agents.response_classifier import ResponseClassifierAgent
    from .services.resume_parser import ResumeParserService
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from backend.db.supabase import supabase_client
    from backend.agents.event_logger import AgentEventLogger
    from backend.agents.company_finder import CompanyFinderAgent
    from backend.agents.personalization import PersonalizationAgent
    from backend.agents.email_writer import EmailWriterAgent
    from backend.agents.resume_tailor import ResumeTailorAgent
    from backend.agents.email_sender import EmailSenderAgent
    from backend.agents.follow_up import FollowUpAgent
    from backend.agents.response_classifier import ResponseClassifierAgent
    from backend.services.resume_parser import ResumeParserService

# In-memory company results cache (user_id -> companies list)
# Used as fallback when Supabase is not configured or rankings table is empty
_user_companies_cache: dict[str, list] = {}

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Company Finder Models Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class CompanyFinderRunRequest(BaseModel):
    user_id: str
    resume_text: Optional[str] = None
    resume_version_id: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None
    count: int = 25


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


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Agent Event Endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@app.get("/agent-events")
async def get_agent_events(
    limit: int = Query(50, ge=1, le=200),
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
):
    """Poll for recent agent events."""
    try:
        result = await supabase_client.get_agent_events(
            limit=limit, agent_name=agent_name, status=status
        )
        return {"events": result, "total": len(result)}
    except Exception:
        # Return mock data when DB not configured
        return {"events": _mock_events(), "total": len(_mock_events())}


@app.get("/agent-events/stream")
async def stream_agent_events():
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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
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

            # 1. Company Finder
            company_agent = CompanyFinderAgent(logger=logger)
            companies = await company_agent.run(
                task_id=task_id,
                skills=effective_skills,
                job_title=request.job_title,
                count=request.company_count,
            )

            # 2. Personalization (per company)
            personalization_agent = PersonalizationAgent(logger=logger)
            for company in companies[:request.company_count]:
                await personalization_agent.run(
                    task_id=str(uuid.uuid4()),
                    company=company,
                )

            # 3. Email Writer (per company)
            email_writer = EmailWriterAgent(logger=logger)
            for company in companies[:request.company_count]:
                await email_writer.run(
                    task_id=str(uuid.uuid4()),
                    company=company,
                    skills=effective_skills,
                    job_title=request.job_title,
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
        return {"emails": _mock_emails(status)}


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
            result = await agent.run_full_pipeline(
                task_id=task_id,
                user_id=request.user_id,
                resume_text=resume_text,
                preferences=request.preferences,
                count=request.count,
            )
            # Cache companies in memory so the GET endpoint can serve them
            # even when Supabase is not configured
            if result and result.get("companies"):
                _user_companies_cache[request.user_id] = result["companies"]
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

    async def run_discovery():
        try:
            companies = await agent.run_discovery_only(
                task_id=task_id,
                profile=profile,
                preferences=preferences,
                count=request.count,
                user_id=request.user_id,
            )
            if companies:
                _user_companies_cache[request.user_id] = companies
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
        result = await supabase_client.upsert_user_preferences({
            "user_id": request.user_id,
            **request.preferences,
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


@app.get("/company-finder/companies")
async def get_discovered_companies(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    """
    Get discovered and ranked companies for a user.
    Includes rankings and contacts.
    """
    try:
        # Try Supabase first
        rankings = await supabase_client.get_company_rankings(user_id, limit=limit)

        if rankings:
            # Flatten: merge company data with ranking data
            companies = []
            for row in rankings:
                company = row.get("companies") or {}
                company["ranking"] = {
                    k: v for k, v in row.items()
                    if k not in ("id", "companies", "company_id", "user_id", "created_at", "updated_at")
                }
                company["match_score"] = row.get("match_score", 0)
                if company.get("id") and min_score <= row.get("match_score", 0):
                    companies.append(company)
            if companies:
                return {"companies": companies, "total": len(companies)}

        # Fall back to in-memory cache (populated by the most recent agent run)
        cached = _user_companies_cache.get(user_id, [])
        if cached:
            filtered = [c for c in cached if c.get("ranking", {}).get("match_score", c.get("match_score", 1.0)) >= min_score]
            return {"companies": filtered[:limit], "total": len(filtered)}

        return {"companies": [], "total": 0}
    except Exception as e:
        # Fall back to in-memory cache on any DB error
        cached = _user_companies_cache.get(user_id, [])
        if cached:
            filtered = [c for c in cached if c.get("ranking", {}).get("match_score", c.get("match_score", 1.0)) >= min_score]
            return {"companies": filtered[:limit], "total": len(filtered)}
        return {"companies": [], "total": 0, "error": str(e)}



@app.post("/company-finder/companies/manual")
async def add_manual_company(request: ManualCompanyRequest):
    """Scrape a user-supplied company website, rank it, persist it, and return it."""
    try:
        logger = AgentEventLogger(event_queue=_event_queue)
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
        deduped = [
            existing for existing in cached
            if existing.get("id") != company.get("id")
            and existing.get("domain", "").lower() != company.get("domain", "").lower()
        ]
        _user_companies_cache[request.user_id] = [company, *deduped]

        return {"company": company, "task_id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/company-finder/companies/{company_id}")
async def get_company_detail(company_id: str):
    """Get full company detail including contacts, jobs, and ranking."""
    try:
        company = await supabase_client.get_company_detail(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"company": company}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/company-finder/companies/{company_id}/handoff")
async def handoff_to_agent(
    company_id: str,
    target_agent: str = Query(..., description="Agent to hand off to: personalizer, email-writer, resume-tailor"),
    user_id: str = Query(...),
):
    """
    Hand off a company to another agent (Personalizer, Email Writer, etc).
    Packages and sends complete context to the target agent.
    """
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_broadcast_queue)

    company = await supabase_client.get_company_detail(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    profile = await supabase_client.get_parsed_profile(user_id) or {}
    ranking = (await supabase_client.get_company_rankings(user_id, limit=1)) or [{}]

    # Structured handoff context
    handoff_context = {
        "company": company,
        "user_profile": profile,
        "ranking": ranking[0] if ranking else {},
        "contacts": company.get("company_contacts", []),
        "matched_skills": profile.get("skills", []),
        "relevant_projects": profile.get("projects", []),
    }

    agent_map = {
        "personalizer": PersonalizationAgent,
        "email-writer": EmailWriterAgent,
        "resume-tailor": ResumeTailorAgent,
    }

    AgentClass = agent_map.get(target_agent.lower())
    if not AgentClass:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{target_agent}'. Valid: {list(agent_map.keys())}",
        )

    agent = AgentClass(logger=logger)
    asyncio.create_task(agent.run(task_id=task_id, **handoff_context))

    return {
        "task_id": task_id,
        "status": "started",
        "target_agent": target_agent,
        "company": company.get("name"),
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

