"""Source registration and mode selection for discovery."""

from __future__ import annotations

import os
from typing import Any

from ..company_sources import (
    AIDiscoverySource,
    HackerNewsSource,
    RemoteOKSource,
    WellfoundSource,
    WorkAtAStartupSource,
    YCCompaniesSource,
)
from .sources import (
    AshbySource,
    CrunchbaseSource,
    GitHubDiscoverySource,
    GreenhouseSource,
    LeverSource,
    WorkableSource,
)


class SourceRegistry:
    """Owns available discovery sources and source-mode routing."""

    def __init__(self, *, openai_api_key: str = "", openai_model: str = "") -> None:
        self._sources: list[Any] = [
            GreenhouseSource(),
            LeverSource(),
            AshbySource(),
            WorkableSource(),
            CrunchbaseSource(),
            GitHubDiscoverySource(),
            RemoteOKSource(),
            HackerNewsSource(),
            YCCompaniesSource(),
            WorkAtAStartupSource(),
            WellfoundSource(),
            AIDiscoverySource(
                api_key=openai_api_key or os.getenv("OPENAI_API_KEY", ""),
                model=openai_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            ),
        ]
        self._modes: dict[str, set[str]] = {
            "all": {s.SOURCE_NAME for s in self._sources},
            "startups": {
                "Greenhouse",
                "Lever",
                "Ashby",
                "Workable",
                "Crunchbase",
                "GitHubDiscovery",
                "HackerNews",
                "YCombinator",
                "WorkAtAStartup",
                "Wellfound",
                "AI Discovery",
            },
            "yc": {"YCombinator", "WorkAtAStartup", "Greenhouse", "Lever", "Ashby"},
            "remote": {"RemoteOK", "Greenhouse", "Lever", "Ashby", "Workable", "HackerNews"},
            "ai": {"Greenhouse", "Lever", "Ashby", "GitHubDiscovery", "AI Discovery"},
            "fortune500": {"Greenhouse", "Lever", "Workable", "RemoteOK", "AI Discovery"},
            "stealth": {"AI Discovery", "HackerNews", "GitHubDiscovery"},
            "international": {"RemoteOK", "Lever", "Ashby", "Workable", "GitHubDiscovery", "AI Discovery"},
            "visa": {"Greenhouse", "Lever", "RemoteOK", "Wellfound", "AI Discovery"},
        }

    @property
    def sources(self) -> list[Any]:
        return list(self._sources)

    def for_mode(self, source_mode: str | None) -> list[Any]:
        allowed = self._modes.get((source_mode or "all").strip().lower(), self._modes["all"])
        return [source for source in self._sources if source.SOURCE_NAME in allowed]

    def by_name(self, source_names: list[str] | set[str] | None) -> list[Any]:
        if not source_names:
            return self.sources
        wanted = {name.strip() for name in source_names}
        return [source for source in self._sources if source.SOURCE_NAME in wanted]

    async def health(self) -> list[dict[str, Any]]:
        result = []
        for source in self._sources:
            health_fn = getattr(source, "health", None)
            if not health_fn:
                result.append({"source": source.SOURCE_NAME, "healthy": True, "status": "healthy"})
                continue
            try:
                health = await health_fn()
                result.append(health.as_dict() if hasattr(health, "as_dict") else dict(health))
            except Exception as exc:
                result.append({
                    "source": source.SOURCE_NAME,
                    "healthy": False,
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}",
                })
        return result
