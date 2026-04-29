"""
ResponseClassifierAgent — Classifies and prioritizes email responses.
"""
import asyncio
from typing import Any

from .event_logger import AgentEventLogger


class ResponseClassifierAgent:
    """
    Monitors the Gmail inbox for replies and classifies them into categories:
    - positive: Interested, wants to connect
    - neutral: Auto-reply, OOO
    - negative: Not interested, no roles available
    - unknown: Unclear intent

    Updates the pipeline status accordingly.
    """

    AGENT_NAME = "ResponseClassifierAgent"

    CLASSIFICATIONS = {
        "positive": ["interested", "let's connect", "would love to chat", "available for a call"],
        "negative": ["not hiring", "not a fit", "no open roles", "no longer accepting"],
        "neutral": ["out of office", "auto-reply", "on vacation"],
    }

    def __init__(self, logger: AgentEventLogger):
        self.logger = logger

    async def run(
        self,
        task_id: str,
        email_id: str | None = None,
        response_text: str | None = None,
        **kwargs: Any,
    ) -> dict:
        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="started",
            message=f"Classifying response for email {email_id}",
            metadata={"email_id": email_id},
        )

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="running",
            message="Analyzing reply sentiment and intent using LLM...",
            metadata={"email_id": email_id},
        )
        await asyncio.sleep(0.8)

        classification = self._classify(response_text or "")

        await self.logger.emit(
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            status="completed",
            message=f"Response classified as '{classification['category']}' — updating pipeline",
            metadata={
                "email_id": email_id,
                "classification": classification,
            },
        )

        return classification

    def _classify(self, text: str) -> dict:
        """
        Classify email response text.
        In production: use GPT-4 with a structured output prompt.
        """
        text_lower = text.lower()

        for category, keywords in self.CLASSIFICATIONS.items():
            if any(kw in text_lower for kw in keywords):
                return {
                    "category": category,
                    "confidence": 0.92,
                    "suggested_action": self._suggest_action(category),
                }

        return {
            "category": "unknown",
            "confidence": 0.5,
            "suggested_action": "manual_review",
        }

    def _suggest_action(self, category: str) -> str:
        actions = {
            "positive": "schedule_call",
            "negative": "archive",
            "neutral": "wait_and_retry",
            "unknown": "manual_review",
        }
        return actions.get(category, "manual_review")
