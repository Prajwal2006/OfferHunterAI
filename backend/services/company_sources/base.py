"""
Abstract base class for all company discovery sources.

Every source connector must subclass CompanySource and implement search().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine


ProgressCallback = Callable[[str, str], Coroutine[Any, Any, None]] | None


class CompanySource(ABC):
    """
    Pluggable company discovery source.

    Subclasses represent individual sources (HN, RemoteOK, YC, Wellfound, etc.)
    and expose a uniform async search() interface.
    """

    #: Stable human-readable name used in events and analytics.
    SOURCE_NAME: str = "Unknown"

    @abstractmethod
    async def search(
        self,
        profile: dict[str, Any],
        preferences: dict[str, Any],
        queries: list[str],
        progress_callback: ProgressCallback = None,
    ) -> list[dict[str, Any]]:
        """
        Search this source for companies that match the candidate.

        Args:
            profile:    Parsed resume profile from ResumeParserService.
            preferences: User job preferences from PreferenceCollectorService.
            queries:    Expanded search queries from QueryExpansionService.
            progress_callback: Optional async(source_name, message) for SSE.

        Returns:
            List of normalized company dicts (via utils.normalize_company).
        """
        ...

    async def _notify(
        self,
        progress_callback: ProgressCallback,
        message: str,
    ) -> None:
        """Fire progress callback if provided. Swallows errors."""
        if progress_callback:
            try:
                await progress_callback(self.SOURCE_NAME, message)
            except Exception:
                pass
