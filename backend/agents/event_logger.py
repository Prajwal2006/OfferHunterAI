"""
OfferHunter AI — Agent Event Logger

Every agent emits structured events via this logger.
Events are stored in Supabase and pushed to the SSE stream.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional


class AgentEventLogger:
    """
    Centralized event logger for all CrewAI agents.

    Usage:
        logger = AgentEventLogger(event_queue=queue)
        await logger.emit(
            agent_name="CompanyFinderAgent",
            task_id="task-001",
            status="completed",
            message="Found 12 companies",
        )
    """

    def __init__(self, event_queue: Optional[asyncio.Queue] = None):
        self._queue = event_queue

    async def emit(
        self,
        agent_name: str,
        task_id: str,
        status: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        metadata = metadata or {}
        resolved_user_id = user_id or metadata.get("user_id") or "anonymous"
        expires_at = None
        if status in {"started", "running"}:
            expires_at = (datetime.utcnow() + timedelta(minutes=2)).isoformat()
        event = {
            "id": str(uuid.uuid4()),
            "user_id": resolved_user_id,
            "agent_name": agent_name,
            "task_id": task_id,
            "status": status,
            "message": message,
            "metadata": {**metadata, "user_id": resolved_user_id},
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Push to SSE stream (supports both asyncio.Queue and broadcast queue)
        if self._queue is not None:
            try:
                self._queue.put_nowait(event)
            except (asyncio.QueueFull, AttributeError):
                pass

        # Persist to Supabase (best-effort)
        try:
            from db.supabase import supabase_client
            await supabase_client.insert_agent_event(event)
        except Exception:
            pass

        return event
