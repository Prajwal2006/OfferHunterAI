"""Discovery source adapters."""

from .ashby import AshbySource
from .base import CompanySource, ProgressCallback
from .clearbit import ClearbitEnrichmentSource
from .community import HackerNewsHiringMiningSource, RedditStartupHiringSource
from .crunchbase import CrunchbaseSource
from .github_discovery import GitHubDiscoverySource
from .greenhouse import GreenhouseSource
from .lever import LeverSource
from .people_data_labs import PeopleDataLabsSource
from .tech_stack import TechStackEnrichmentSource
from .workable import WorkableSource

__all__ = [
    "AshbySource",
    "CompanySource",
    "ProgressCallback",
    "ClearbitEnrichmentSource",
    "CrunchbaseSource",
    "GitHubDiscoverySource",
    "GreenhouseSource",
    "HackerNewsHiringMiningSource",
    "LeverSource",
    "PeopleDataLabsSource",
    "RedditStartupHiringSource",
    "TechStackEnrichmentSource",
    "WorkableSource",
]
