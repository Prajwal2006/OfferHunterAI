"""Metrics and health primitives for discovery sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SourceRunStatus(str, Enum):
    """Lifecycle status for a source execution."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass(slots=True)
class SourceHealth:
    """A lightweight health report exposed by every source adapter."""

    source: str
    healthy: bool = True
    status: str = "healthy"
    reason: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "healthy": self.healthy,
            "status": self.status,
            "reason": self.reason,
            "checked_at": self.checked_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class SourceMetric:
    """Durable per-source telemetry for observability and ranking feedback."""

    source: str
    status: SourceRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    result_count: int = 0
    duplicate_count: int = 0
    filtered_count: int = 0
    retry_count: int = 0
    error: str = ""
    timeout_seconds: float | None = None
    anti_bot_detected: bool = False
    parser_failures: int = 0
    api_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def complete(
        self,
        status: SourceRunStatus,
        *,
        result_count: int = 0,
        error: str = "",
    ) -> "SourceMetric":
        self.status = status
        self.completed_at = datetime.utcnow()
        self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        self.result_count = result_count
        self.error = error
        return self

    def as_log_row(
        self,
        *,
        user_id: str | None,
        discovery_session_id: str | None,
        queries: list[str],
    ) -> dict[str, Any]:
        status = self.status.value
        if status == SourceRunStatus.SKIPPED.value:
            status = SourceRunStatus.FAILED.value

        return {
            "user_id": user_id,
            "discovery_session_id": discovery_session_id,
            "source": self.source,
            "query_used": queries[:12],
            "status": status,
            "result_count": self.result_count,
            "duplicate_count": self.duplicate_count,
            "filtered_count": self.filtered_count,
            "error": self.error or None,
            "duration_ms": self.duration_ms,
            "metadata": {
                **self.metadata,
                "retry_count": self.retry_count,
                "timeout_seconds": self.timeout_seconds,
                "anti_bot_detected": self.anti_bot_detected,
                "parser_failures": self.parser_failures,
                "api_failures": self.api_failures,
            },
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
