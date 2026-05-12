"""Shared AI helpers for outreach generation services."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

from .logger_service import get_logger


load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


class AIServiceError(RuntimeError):
    """Raised when an AI provider call fails after retries."""


_OPENAI_CONFIG_LOGGED = False


def _masked_secret(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 14:
        return f"{value[:4]}...{value[-2:]}"
    return f"{value[:7]}...{value[-4:]}"


def _openai_config_snapshot(api_key: str, model: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "openai_api_key_present": bool(api_key),
        "openai_api_key_masked": _masked_secret(api_key),
        "openai_api_key_length": len(api_key),
        "openai_api_key_sha256_12": hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12] if api_key else None,
        "openai_model": model,
        "openai_timeout_seconds": timeout_seconds,
    }


@dataclass
class AIJsonResult:
    data: dict[str, Any]
    call_id: str
    raw_response: str
    provider: str
    model: str
    request_payload: dict[str, Any]
    context_payload: dict[str, Any] | None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    tokens_total: int | None = None
    duration_ms: float | None = None


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
        global _OPENAI_CONFIG_LOGGED
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv(model_env, os.getenv("OPENAI_MODEL", default_model)).strip() or default_model
        try:
            self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
        except ValueError:
            self.timeout_seconds = 45.0
        timeout = httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))
        self._client: AsyncOpenAI | None = (
            AsyncOpenAI(api_key=self.api_key, timeout=timeout, max_retries=0)
            if self.api_key
            else None
        )
        self._logger = get_logger()
        if not _OPENAI_CONFIG_LOGGED:
            snapshot = _openai_config_snapshot(self.api_key, self.model, self.timeout_seconds)
            print(f"OpenAI backend config: {json.dumps(snapshot, default=str)}")
            self._logger.log_business_logic("openai.config.loaded", details=snapshot)
            _OPENAI_CONFIG_LOGGED = True

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
        user_id: str | None = None,
        context_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.create_json_detailed(
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            attempts=attempts,
            user_id=user_id,
            context_metadata=context_metadata,
        )
        return result.data

    async def create_json_detailed(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.35,
        max_tokens: int = 2200,
        attempts: int = 2,
        user_id: str | None = None,
        context_metadata: dict[str, Any] | None = None,
    ) -> AIJsonResult:
        if not self._client:
            raise AIServiceError("OpenAI API key is not configured")

        request_payload = {
            "provider": "openai",
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
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
            response_format={"type": "json_object"},
            raw_payload=request_payload,
        )
        last_error: Exception | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
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
                parsed = extract_json_object(content)
                usage = getattr(response, "usage", None)
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                self._logger.log_llm_response(
                    call_id=call_id,
                    response=content,
                    response_json=parsed,
                    tokens_used=getattr(usage, "total_tokens", None),
                    tokens_prompt=getattr(usage, "prompt_tokens", None),
                    tokens_completion=getattr(usage, "completion_tokens", None),
                    duration_ms=duration_ms,
                    attempt=attempt + 1,
                )
                return AIJsonResult(
                    data=parsed,
                    call_id=call_id,
                    raw_response=content,
                    provider="openai",
                    model=self.model,
                    request_payload=request_payload,
                    context_payload=context_metadata,
                    tokens_prompt=getattr(usage, "prompt_tokens", None),
                    tokens_completion=getattr(usage, "completion_tokens", None),
                    tokens_total=getattr(usage, "total_tokens", None),
                    duration_ms=duration_ms,
                )
            except Exception as exc:  # pragma: no cover - provider/network dependent
                last_error = exc
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                self._logger.log_error(
                    error_type="openai_json_call_failed",
                    message=str(exc),
                    user_id=user_id,
                    context={
                        "call_id": call_id,
                        "attempt": attempt + 1,
                        "model": self.model,
                        "duration_ms": duration_ms,
                        "timeout_seconds": self.timeout_seconds,
                        "exception_type": exc.__class__.__name__,
                        "openai_config": _openai_config_snapshot(self.api_key, self.model, self.timeout_seconds),
                    },
                    severity="warning" if attempt + 1 < attempts else "error",
                )
                await asyncio.sleep((2**attempt) * 0.4 + random.random() * 0.2)
        self._logger.log_llm_response(
            call_id=call_id,
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
