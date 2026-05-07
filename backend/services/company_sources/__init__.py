"""
company_sources package — pluggable company discovery source connectors.

Import all source classes for easy instantiation in CompanyDiscoveryService.
"""

from .base import CompanySource, ProgressCallback
from .utils import (
    DEFAULT_HEADERS,
    slugify_domain,
    extract_domain_from_url,
    normalize_url,
    normalize_company,
    startup_priority_score,
    infer_industry,
    infer_company_size,
    infer_tech_stack,
    infer_funding_stage,
    infer_headquarters,
    infer_culture_tags,
)
from .hackernews import HackerNewsSource
from .remoteok import RemoteOKSource
from .workatastartup import WorkAtAStartupSource
from .wellfound import WellfoundSource
from .yc_companies import YCCompaniesSource
from .ai_discovery import AIDiscoverySource

__all__ = [
    "CompanySource",
    "ProgressCallback",
    # utilities
    "DEFAULT_HEADERS",
    "slugify_domain",
    "extract_domain_from_url",
    "normalize_url",
    "normalize_company",
    "startup_priority_score",
    "infer_industry",
    "infer_company_size",
    "infer_tech_stack",
    "infer_funding_stage",
    "infer_headquarters",
    "infer_culture_tags",
    # sources
    "HackerNewsSource",
    "RemoteOKSource",
    "WorkAtAStartupSource",
    "WellfoundSource",
    "YCCompaniesSource",
    "AIDiscoverySource",
]
