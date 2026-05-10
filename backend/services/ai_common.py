"""Shared AI helpers for outreach generation services."""
from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

import httpx
from openai import AsyncOpenAI


class AIServiceError(RuntimeError):
    """Raised when an AI provider call fails after retries."""


def compact_json(data: Any, max_chars: int = 14000) -> str:
    """Serialize context for prompts without letting huge resumes dominate tokens."""
    text = json.dumps(data or {}, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort extraction for providers that return fenced or prefixed JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


class OpenAIJsonClient:
    """Small async JSON-mode wrapper with retry and graceful disabled mode."""

    def __init__(self, model_env: str = "OPENAI_MODEL", default_model: str = "gpt-4o-mini") -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv(model_env, os.getenv("OPENAI_MODEL", default_model)).strip() or default_model
        self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8"))
        timeout = httpx.Timeout(self.timeout_seconds, connect=6.0)
        self._client: AsyncOpenAI | None = (
            AsyncOpenAI(api_key=self.api_key, timeout=timeout, max_retries=0)
            if self.api_key
            else None
        )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def create_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.35,
        max_tokens: int = 2200,
        attempts: int = 2,
    ) -> dict[str, Any]:
        if not self._client:
            raise AIServiceError("OpenAI API key is not configured")

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=self.model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    ),
                    timeout=self.timeout_seconds + 2,
                )
                content = response.choices[0].message.content or "{}"
                return extract_json_object(content)
            except Exception as exc:  # pragma: no cover - provider/network dependent
                last_error = exc
                await asyncio.sleep((2**attempt) * 0.4 + random.random() * 0.2)
        raise AIServiceError(str(last_error) if last_error else "OpenAI request failed")


def normalize_score(value: Any, default: int = 70) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))
