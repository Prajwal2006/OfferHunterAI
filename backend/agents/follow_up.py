"""
FollowUpAgent — Sends automated follow-up emails after no response.
"""
import asyncio
from typing import Any

from .event_logger import AgentEventLogger


class FollowUpAgent:
    """
    Monitors sent emails and triggers follow-up messages after a configured
    delay if no response has been received.

    Default follow-up schedule: 3 days, then 7 days, then stop.
    """

    AGENT_NAME = "FollowUpAgent"
    DEFAULT_FOLLOW_UP_DAYS = [3, 7]

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        email_id: str | None = None,
        follow_up_number: int = 1,
        **kwargs: Any,
    ) -> dict:
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Checking follow-up status for email {email_id} (follow-up #{follow_up_number})",
            metadata={"email_id": email_id, "follow_up_number": follow_up_number},
        )

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message="Checking inbox for replies...",
            metadata={"email_id": email_id},
        )
        await asyncio.sleep(0.5)

        # Check for response
        has_response = False  # In production: check Gmail inbox

        if has_response:
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="completed",
                message=f"Response detected for email {email_id} — follow-up not needed",
                metadata={"email_id": email_id, "has_response": True},
            )
            return {"status": "response_received", "follow_up_sent": False}

        if follow_up_number > len(self.DEFAULT_FOLLOW_UP_DAYS):
            await self.logger.emit(
                agent_name=self.AGENT_NAME,
                task_id=task_id,
                status="completed",
                message=f"Max follow-ups reached for email {email_id} — stopping",
                metadata={"email_id": email_id, "follow_up_number": follow_up_number},
            )
            return {"status": "max_follow_ups_reached", "follow_up_sent": False}

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message=f"No response detected — drafting follow-up #{follow_up_number}",
            metadata={"email_id": email_id},
        )
        await asyncio.sleep(0.5)

        follow_up_body = self._generate_follow_up(follow_up_number)

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Follow-up #{follow_up_number} drafted and queued for approval",
            metadata={
                "email_id": email_id,
                "follow_up_number": follow_up_number,
                "follow_up_status": "pending_approval",
            },
        )

        return {
            "status": "follow_up_queued",
            "follow_up_number": follow_up_number,
            "body": follow_up_body,
        }

    def _generate_follow_up(self, number: int) -> str:
        templates = {
            1: "Hi,\n\nJust circling back on my previous message. I'd love to connect if you have a few minutes.\n\nBest,\n[Your Name]",
            2: "Hi,\n\nI wanted to reach out one more time. I remain very interested in opportunities at your company.\n\nBest,\n[Your Name]",
        }
        return templates.get(number, "")
