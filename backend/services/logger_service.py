"""
Comprehensive logging service for OfferHunter AI.
Handles all logging across backend services, LLM calls, and API requests.
All logs are timestamped and stored in the logs directory.
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from enum import Enum


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log category enumeration."""
    API_REQUEST = "API_REQUEST"
    API_RESPONSE = "API_RESPONSE"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    DATABASE = "DATABASE"
    BUSINESS_LOGIC = "BUSINESS_LOGIC"
    AGENT = "AGENT"
    ERROR = "ERROR"
    PERFORMANCE = "PERFORMANCE"
    FRONTEND_EVENT = "FRONTEND_EVENT"


class LoggerService:
    """Centralized logging service for the entire application."""
    
    def __init__(self):
        """Initialize the logger service."""
        self.logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.unified_log_file = self.logs_dir / "app.log"
        self.unified_log_file.touch(exist_ok=True)
        self._session_id = str(uuid.uuid4())
        self._request_counter = 0

    def _format_log_line(self, entry: dict[str, Any]) -> str:
        """Render one readable text log line."""
        def format_value(value: Any) -> str:
            if isinstance(value, (dict, list)):
                text = json.dumps(value, ensure_ascii=False, default=str)
            else:
                text = str(value)
            return text if len(text) <= 4000 else text[:4000] + "...[truncated]"

        ts = str(entry.get("timestamp") or datetime.utcnow().isoformat())
        log_type = str(entry.get("log_type") or "event")
        session_id = str(entry.get("session_id") or "-")

        parts = [f"{ts}", f"type={log_type}", f"session={session_id}"]
        preferred = [
            "request_id",
            "user_id",
            "endpoint",
            "method",
            "status_code",
            "duration_ms",
            "action",
            "event_type",
            "agent_name",
            "message",
            "error",
        ]
        seen = {"timestamp", "log_type", "session_id"}

        for key in preferred:
            value = entry.get(key)
            if value is None:
                continue
            parts.append(f"{key}={format_value(value)}")
            seen.add(key)

        for key, value in entry.items():
            if key in seen or value is None:
                continue
            parts.append(f"{key}={format_value(value)}")

        return " | ".join(parts)
    
    def _safe_serialize(self, value: Any, max_chars: int = 5000) -> Any:
        """Safely serialize values for JSON logging."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            text = str(value)
            return text if len(text) <= max_chars else text[:max_chars] + "...[truncated]"
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
            if len(text) <= max_chars:
                return value
            return text[:max_chars] + "...[truncated]"
        except Exception:
            text = str(value)
            return text if len(text) <= max_chars else text[:max_chars] + "...[truncated]"
    
    def _write_log(self, log_type: str, data: dict[str, Any]) -> None:
        """Write log entry to file."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self._session_id,
            "log_type": log_type,
            **data,
        }
        try:
            with self.unified_log_file.open("a", encoding="utf-8") as f:
                f.write(self._format_log_line(entry) + "\n")
        except Exception as e:
            print(f"Failed to write log: {e}", file=sys.stderr)
    
    def log_api_request(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        headers: Optional[dict] = None,
        body: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """Log incoming API request with full details."""
        request_id = str(uuid.uuid4())
        self._write_log(
            "api-requests",
            {
                "request_id": request_id,
                "endpoint": endpoint,
                "method": method,
                "user_id": user_id,
                "headers": self._safe_serialize(
                    {k: v for k, v in (headers or {}).items() if k.lower() not in ["authorization", "cookie"]},
                    2000,
                ),
                "body": self._safe_serialize(body, 3000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
        return request_id
    
    def log_api_response(
        self,
        request_id: str,
        status_code: int,
        response_body: Optional[Any] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log API response details."""
        self._write_log(
            "api-responses",
            {
                "request_id": request_id,
                "status_code": status_code,
                "response_body": self._safe_serialize(response_body, 3000),
                "duration_ms": duration_ms,
                "error": error,
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_llm_call(
        self,
        provider: str = "openai",
        model: str = "",
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[str] = None,
        context: Optional[dict] = None,
        **kwargs: Any,
    ) -> str:
        """Log LLM call with full prompt and parameters."""
        call_id = str(uuid.uuid4())
        self._write_log(
            "llm-calls",
            {
                "call_id": call_id,
                "provider": provider,
                "model": model,
                "system_prompt": self._safe_serialize(system_prompt, 8000),
                "user_prompt": self._safe_serialize(user_prompt, 8000),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "user_id": user_id,
                "context": self._safe_serialize(context, 3000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
        return call_id
    
    def log_llm_response(
        self,
        call_id: str,
        response: Optional[str] = None,
        response_json: Optional[dict] = None,
        tokens_used: Optional[int] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log LLM response with usage metrics."""
        self._write_log(
            "llm-responses",
            {
                "call_id": call_id,
                "response": self._safe_serialize(response, 8000),
                "response_json": self._safe_serialize(response_json, 8000),
                "tokens_used": tokens_used,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "duration_ms": duration_ms,
                "error": error,
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_database_operation(
        self,
        operation: str,  # SELECT, INSERT, UPDATE, DELETE
        table: str,
        user_id: Optional[str] = None,
        filters: Optional[dict] = None,
        data: Optional[dict] = None,
        result_count: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log database operations."""
        self._write_log(
            "database-operations",
            {
                "operation": operation,
                "table": table,
                "user_id": user_id,
                "filters": self._safe_serialize(filters, 3000),
                "data": self._safe_serialize(data, 3000),
                "result_count": result_count,
                "duration_ms": duration_ms,
                "error": error,
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_business_logic(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[dict] = None,
        level: LogLevel = LogLevel.INFO,
        **kwargs: Any,
    ) -> None:
        """Log business logic events (company discovery, email generation, etc.)."""
        self._write_log(
            "business-logic",
            {
                "action": action,
                "user_id": user_id,
                "level": level.value,
                "details": self._safe_serialize(details, 4000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_agent_event(
        self,
        agent_name: str,
        event_type: str,  # started, processing, completed, failed
        user_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """Log agent-related events."""
        self._write_log(
            "agent-events",
            {
                "agent_name": agent_name,
                "event_type": event_type,
                "user_id": user_id,
                "task_id": task_id,
                "message": message,
                "status": status,
                "metadata": self._safe_serialize(metadata, 3000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_error(
        self,
        error_type: str,
        message: str,
        user_id: Optional[str] = None,
        context: Optional[dict] = None,
        stack_trace: Optional[str] = None,
        severity: str = "error",
        **kwargs: Any,
    ) -> None:
        """Log errors with full context."""
        self._write_log(
            "errors",
            {
                "error_type": error_type,
                "message": message,
                "user_id": user_id,
                "context": self._safe_serialize(context, 3000),
                "stack_trace": stack_trace,
                "severity": severity,
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        user_id: Optional[str] = None,
        threshold_ms: Optional[float] = None,
        metadata: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """Log performance metrics."""
        is_slow = threshold_ms is not None and duration_ms > threshold_ms
        self._write_log(
            "performance",
            {
                "operation": operation,
                "duration_ms": duration_ms,
                "is_slow": is_slow,
                "threshold_ms": threshold_ms,
                "user_id": user_id,
                "metadata": self._safe_serialize(metadata, 3000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )
    
    def log_frontend_event(
        self,
        event_type: str,  # click, api_call, error, etc.
        component: str,
        user_id: Optional[str] = None,
        details: Optional[dict] = None,
        level: str = "info",
        **kwargs: Any,
    ) -> None:
        """Log frontend events received from client."""
        self._write_log(
            "frontend-events",
            {
                "event_type": event_type,
                "component": component,
                "user_id": user_id,
                "level": level,
                "details": self._safe_serialize(details, 3000),
                **{k: self._safe_serialize(v, 2000) for k, v in kwargs.items()},
            },
        )


# Global logger instance
_logger: Optional[LoggerService] = None


def get_logger() -> LoggerService:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = LoggerService()
    return _logger
