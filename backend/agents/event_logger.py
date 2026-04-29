"""
OfferHunter AI — Agent Event Logger

Every agent emits structured events via this logger.
Events are stored in Supabase and pushed to the SSE stream.
"""
import asyncio
import uuid
from datetime import datetime
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
    ) -> dict:
        event = {
            "id": str(uuid.uuid4()),
            "agent_name": agent_name,
            "task_id": task_id,
            "status": status,
            "message": message,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }

        # Push to SSE stream
        if self._queue is not None:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Persist to Supabase (best-effort)
        try:
            from ..db.supabase import supabase_client
            await supabase_client.insert_agent_event(event)
        except Exception:
            pass

        return event
