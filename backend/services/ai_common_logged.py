"""
LLM logging wrapper for OpenAI API calls.
Tracks all prompts, responses, and token usage with full context.
"""
import asyncio
import json
import os
import random
import time
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI

from .logger_service import get_logger


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
    """Small async JSON-mode wrapper with retry, graceful disabled mode, and comprehensive logging."""

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
        self._logger = get_logger()

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
        user_id: Optional[str] = None,
        context_metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Create JSON response with comprehensive logging of the entire LLM interaction."""
        if not self._client:
            raise AIServiceError("OpenAI API key is not configured")

        # Log the LLM call with full prompt and context
        call_id = self._logger.log_llm_call(
            provider="openai",
            model=self.model,
            system_prompt=system,
            user_prompt=user,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            context=context_metadata,
            attempt_count=attempts,
        )

        last_error: Exception | None = None
        attempt_num = 0
        start_time = time.time()

        for attempt_num in range(attempts):
            try:
                attempt_start = time.time()
                
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
                
                attempt_duration = (time.time() - attempt_start) * 1000
                content = response.choices[0].message.content or "{}"
                
                # Extract token usage information
                tokens_used = None
                tokens_prompt = None
                tokens_completion = None
                if hasattr(response, "usage"):
                    tokens_used = response.usage.total_tokens if hasattr(response.usage, "total_tokens") else None
                    tokens_prompt = response.usage.prompt_tokens if hasattr(response.usage, "prompt_tokens") else None
                    tokens_completion = response.usage.completion_tokens if hasattr(response.usage, "completion_tokens") else None
                
                # Log successful LLM response
                self._logger.log_llm_response(
                    call_id=call_id,
                    response=content,
                    response_json=extract_json_object(content),
                    tokens_used=tokens_used,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    duration_ms=attempt_duration,
                    attempt=attempt_num + 1,
                )
                
                # Log performance metric
                total_duration = (time.time() - start_time) * 1000
                self._logger.log_performance(
                    operation="openai_json_call",
                    duration_ms=total_duration,
                    user_id=user_id,
                    metadata={
                        "model": self.model,
                        "attempts": attempt_num + 1,
                        "tokens_used": tokens_used,
                    },
                )
                
                return extract_json_object(content)
            except Exception as exc:  # pragma: no cover - provider/network dependent
                last_error = exc
                error_msg = str(exc)
                
                # Log the error attempt
                self._logger.log_error(
                    error_type="openai_call_failed",
                    message=error_msg,
                    user_id=user_id,
                    context={
                        "call_id": call_id,
                        "attempt": attempt_num + 1,
                        "max_attempts": attempts,
                        "model": self.model,
                    },
                    severity="warning" if attempt_num + 1 < attempts else "error",
                )
                
                if attempt_num + 1 < attempts:
                    await asyncio.sleep((2**attempt_num) * 0.4 + random.random() * 0.2)
        
        # Final error log
        total_duration = (time.time() - start_time) * 1000
        self._logger.log_llm_response(
            call_id=call_id,
            duration_ms=total_duration,
            error=str(last_error) if last_error else "OpenAI request failed",
            attempt=attempts,
        )
        
        raise AIServiceError(str(last_error) if last_error else "OpenAI request failed")


def normalize_score(value: Any, default: int = 70) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))
