"""Thin async OpenAI chat-completions helper shared across agents.

Centralizes the one network call so agents (email writer, resume tailor, cover
letter, etc.) generate grounded, resume-specific content instead of returning
hardcoded placeholder text. Uses raw httpx to match the rest of the codebase and
avoid SDK client lifecycle issues in serverless environments.

Every call degrades gracefully: when no OPENAI_API_KEY is configured (or the API
errors), helpers return ``None`` so callers can fall back to deterministic,
honest templates rather than crashing the pipeline.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def llm_available() -> bool:
    """True when an OpenAI key is configured and live generation is possible."""
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


async def chat(
    messages: list[dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1200,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> Optional[str]:
    """Return the assistant message content, or None if generation is unavailable."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    payload: dict[str, Any] = {
        "model": model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENAI_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


async def chat_json(
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> Optional[dict[str, Any]]:
    """Call :func:`chat` in JSON mode and parse the result, or None on failure."""
    kwargs.setdefault("json_mode", True)
    content = await chat(messages, **kwargs)
    if not content:
        return None
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
