"""
OfferHunter AI — FastAPI Backend
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .db.supabase import supabase_client
from .agents.event_logger import AgentEventLogger
from .agents.company_finder import CompanyFinderAgent
from .agents.personalization import PersonalizationAgent
from .agents.email_writer import EmailWriterAgent
from .agents.resume_tailor import ResumeTailorAgent
from .agents.email_sender import EmailSenderAgent
from .agents.follow_up import FollowUpAgent
from .agents.response_classifier import ResponseClassifierAgent

# In-memory event queue for SSE streaming
_event_queue: asyncio.Queue = asyncio.Queue()


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

# ─── Models ───────────────────────────────────────────────────────────────────

class RunAgentsRequest(BaseModel):
    skills: list[str]
    job_title: str
    company_count: int = 10
    resume_text: Optional[str] = None


class ExecuteAgentRequest(BaseModel):
    task_id: Optional[str] = None
    payload: dict[str, Any] = {}


class EmailApprovalRequest(BaseModel):
    reason: Optional[str] = None


class EmailUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


# ─── Agent Event Endpoints ────────────────────────────────────────────────────

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

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial heartbeat
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        while True:
            try:
                # Wait for new event (with timeout for keep-alive)
                event = await asyncio.wait_for(_event_queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Send keep-alive comment
                yield ": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Agent Execution Endpoints ────────────────────────────────────────────────

@app.post("/agents/run")
async def run_agents(request: RunAgentsRequest):
    """Trigger the full multi-agent pipeline."""
    task_id = str(uuid.uuid4())
    logger = AgentEventLogger(event_queue=_event_queue)

    async def run_pipeline():
        try:
            # 1. Company Finder
            company_agent = CompanyFinderAgent(logger=logger)
            companies = await company_agent.run(
                task_id=task_id,
                skills=request.skills,
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
                    skills=request.skills,
                    job_title=request.job_title,
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
    logger = AgentEventLogger(event_queue=_event_queue)

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


# ─── Email Endpoints ──────────────────────────────────────────────────────────

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
        logger = AgentEventLogger(event_queue=_event_queue)
        await logger.emit(
            agent_name="EmailSenderAgent",
            task_id=email_id,
            status="started",
            message=f"Email {email_id} approved by user — ready to send",
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
    logger = AgentEventLogger(event_queue=_event_queue)
    sender = EmailSenderAgent(logger=logger)
    task_id = str(uuid.uuid4())
    asyncio.create_task(sender.run(task_id=task_id, email_id=email_id))
    return {"email_id": email_id, "task_id": task_id, "status": "sending"}


# ─── Pipeline Endpoints ───────────────────────────────────────────────────────

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


# ─── Mock data helpers ────────────────────────────────────────────────────────

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
            "subject": "Experienced ML Engineer — Excited About Stripe's Infrastructure",
            "body": "Hi,\n\nI would love to join Stripe...\n\nBest,\n[Your Name]",
            "status": "pending_approval",
            "created_at": datetime.utcnow().isoformat(),
        }
    ]
    if status:
        return [e for e in emails if e["status"] == status]
    return emails
