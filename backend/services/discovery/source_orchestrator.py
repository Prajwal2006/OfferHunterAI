"""Async source orchestrator with per-source isolation and telemetry."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Coroutine

from .source_metrics import SourceMetric, SourceRunStatus

ProgressCallback = Callable[[str, str], Coroutine[Any, Any, None]] | None


class SourceOrchestrator:
    """Runs discovery adapters concurrently without source-level coupling."""

    def __init__(
        self,
        *,
        default_timeout_seconds: float = 18.0,
        max_concurrent_sources: int = 8,
    ) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.max_concurrent_sources = max_concurrent_sources
        self.metrics: list[SourceMetric] = []

    async def run(
        self,
        *,
        sources: list[Any],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> tuple[list[dict[str, Any]], list[SourceMetric]]:
        """Run every source independently and return merged companies + metrics."""
        self.metrics = []
        semaphore = asyncio.Semaphore(self.max_concurrent_sources)

        async def run_one(source: Any) -> list[dict[str, Any]]:
            async with semaphore:
                metric = SourceMetric(
                    source=source.SOURCE_NAME,
                    status=SourceRunStatus.RUNNING,
                    started_at=datetime.utcnow(),
                    timeout_seconds=float(getattr(source, "timeout_seconds", self.default_timeout_seconds)),
                )
                self.metrics.append(metric)
                try:
                    if progress_callback:
                        await progress_callback(source.SOURCE_NAME, f"{source.SOURCE_NAME} started")
                    companies = await asyncio.wait_for(
                        source.search(profile, preferences, queries, progress_callback),
                        timeout=metric.timeout_seconds or self.default_timeout_seconds,
                    )
                    metric.complete(SourceRunStatus.SUCCESS, result_count=len(companies))
                    if progress_callback:
                        await progress_callback(source.SOURCE_NAME, f"{source.SOURCE_NAME}: +{len(companies)} companies")
                    return companies
                except asyncio.TimeoutError:
                    metric.complete(
                        SourceRunStatus.TIMEOUT,
                        error=f"Timed out after {metric.timeout_seconds or self.default_timeout_seconds:.0f} seconds",
                    )
                    if progress_callback:
                        await progress_callback(source.SOURCE_NAME, metric.error)
                    return []
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    metric.complete(SourceRunStatus.FAILED, error=message)
                    lower = message.lower()
                    metric.anti_bot_detected = any(token in lower for token in ["captcha", "challenge", "cloudflare", "403", "blocked"])
                    metric.api_failures = 1
                    if progress_callback:
                        await progress_callback(source.SOURCE_NAME, f"{source.SOURCE_NAME} failed: {type(exc).__name__}")
                    return []

        results = await asyncio.gather(*(run_one(source) for source in sources), return_exceptions=False)
        companies: list[dict[str, Any]] = []
        for batch in results:
            companies.extend(batch)
        return companies, list(self.metrics)

    async def stream(
        self,
        *,
        sources: list[Any],
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> AsyncIterator[tuple[str, list[dict[str, Any]], SourceMetric]]:
        """Yield partial source results as each adapter completes."""
        semaphore = asyncio.Semaphore(self.max_concurrent_sources)

        async def run_one(source: Any) -> tuple[str, list[dict[str, Any]], SourceMetric]:
            async with semaphore:
                metric = SourceMetric(
                    source=source.SOURCE_NAME,
                    status=SourceRunStatus.RUNNING,
                    started_at=datetime.utcnow(),
                    timeout_seconds=float(getattr(source, "timeout_seconds", self.default_timeout_seconds)),
                )
                try:
                    companies = await asyncio.wait_for(
                        source.search(profile, preferences, queries, progress_callback),
                        timeout=metric.timeout_seconds or self.default_timeout_seconds,
                    )
                    metric.complete(SourceRunStatus.SUCCESS, result_count=len(companies))
                    return source.SOURCE_NAME, companies, metric
                except asyncio.TimeoutError:
                    metric.complete(SourceRunStatus.TIMEOUT, error=f"Timed out after {metric.timeout_seconds:.0f} seconds")
                    return source.SOURCE_NAME, [], metric
                except Exception as exc:
                    metric.complete(SourceRunStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
                    return source.SOURCE_NAME, [], metric

        tasks = [asyncio.create_task(run_one(source)) for source in sources]
        for completed in asyncio.as_completed(tasks):
            yield await completed
