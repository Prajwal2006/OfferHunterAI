"""End-to-end opportunity intelligence pipeline facade."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from ..query_expansion import QueryExpansionService
from .recursive_expansion import RecursiveExpansionService
from .source_orchestrator import SourceOrchestrator
from .source_registry import SourceRegistry

ProgressCallback = Callable[[str, str], Coroutine[Any, Any, None]] | None


class DiscoveryPipeline:
    """Semantic expansion -> parallel sources -> dedup -> recursive expansion hooks."""

    def __init__(
        self,
        *,
        registry: SourceRegistry | None = None,
        query_expander: QueryExpansionService | None = None,
        orchestrator: SourceOrchestrator | None = None,
        recursive_expander: RecursiveExpansionService | None = None,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.query_expander = query_expander or QueryExpansionService()
        self.orchestrator = orchestrator or SourceOrchestrator()
        self.recursive_expander = recursive_expander or RecursiveExpansionService()

    async def run(
        self,
        *,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        target_count: int,
        progress_callback: ProgressCallback = None,
        source_mode: str = "all",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """Run the discovery pipeline and return companies, metrics, queries."""
        if progress_callback:
            await progress_callback("QueryExpansion", "Generating semantic query expansions...")
        try:
            queries = await self.query_expander.expand_queries(profile, preferences)
        except Exception:
            queries = self.query_expander._base_queries(profile, preferences)

        sources = self.registry.for_mode(source_mode)
        if progress_callback:
            await progress_callback(
                "Discovery",
                f"Running {len(sources)} independent sources: {', '.join(s.SOURCE_NAME for s in sources)}",
            )

        companies, metrics = await self.orchestrator.run(
            sources=sources,
            profile=profile,
            preferences=preferences,
            queries=queries,
            progress_callback=progress_callback,
        )
        recursive = self.recursive_expander.expand(companies)
        if progress_callback and recursive["queries"]:
            await progress_callback(
                "RecursiveExpansion",
                f"Prepared {len(recursive['queries'])} adjacent graph expansion queries",
            )

        return companies[: max(target_count * 4, target_count)], [m.as_log_row(
            user_id=preferences.get("_user_id"),
            discovery_session_id=preferences.get("_discovery_session_id"),
            queries=queries,
        ) for m in metrics], queries
