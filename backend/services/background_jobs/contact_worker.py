from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is in Python path for both local and Vercel deployments
_backend_root = str(Path(__file__).resolve().parent.parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from services.contact_finder import ContactFinderService


async def run_contact_worker(
    *,
    companies: list[dict[str, Any]],
    top_n: int = 15,
    per_company_timeout_seconds: float = 20.0,
) -> list[dict[str, Any]]:
    """Attach contacts in the background with per-company hard timeouts."""
    if not companies:
        return companies

    finder = ContactFinderService()
    targets = companies[:top_n]

    async def find_one(company: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            return await asyncio.wait_for(
                finder.find_contacts(company),
                timeout=per_company_timeout_seconds,
            )
        except Exception:
            return []

    results = await asyncio.gather(*[find_one(c) for c in targets], return_exceptions=False)

    for company, contacts in zip(targets, results):
        company["contacts"] = contacts if isinstance(contacts, list) else []

    for company in companies[top_n:]:
        company.setdefault("contacts", [])

    return companies
