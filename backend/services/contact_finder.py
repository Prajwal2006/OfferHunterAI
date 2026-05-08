"""
ContactFinderService — Discovers email contacts for companies.

Strategies (in order of reliability):
1. Company "About/Team/Contact" page scraping
2. Pattern-based email inference from known domain
3. AI-assisted inference from company metadata
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


# ─── Common Patterns ──────────────────────────────────────────────────────────

EMAIL_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "careers@{domain}",
    "jobs@{domain}",
    "recruiting@{domain}",
    "talent@{domain}",
    "hr@{domain}",
    "hello@{domain}",
    "team@{domain}",
]

GENERIC_CONTACTS = [
    ("careers", "careers@{domain}", "hr", 0.6),
    ("jobs", "jobs@{domain}", "hr", 0.5),
    ("recruiting", "recruiting@{domain}", "recruiter", 0.65),
    ("talent", "talent@{domain}", "recruiter", 0.6),
    ("hello", "hello@{domain}", "other", 0.4),
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OfferHunterAI/1.0; +https://offerhunterai.com/bot)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Service ──────────────────────────────────────────────────────────────────

class ContactFinderService:
    """
    Finds recruiter/founder/hiring manager contacts for a company.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._hunter_api_key = os.getenv("HUNTER_API_KEY", "")

    async def find_contacts(
        self, company: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Find contacts for a company. Returns a list of contact dicts.
        """
        domain = company.get("domain", "")
        if not domain:
            return []

        tasks = [
            self._generate_generic_contacts(domain),
            self._scrape_website_contacts(company),
        ]
        if self._hunter_api_key:
            tasks.append(self._search_hunter(domain))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        contacts: list[dict[str, Any]] = []
        seen_emails: set[str] = set()

        for result in results:
            if isinstance(result, list):
                for contact in result:
                    email = (contact.get("email") or "").lower()
                    if email and email not in seen_emails:
                        seen_emails.add(email)
                        contacts.append(contact)

        # Sort by confidence descending
        contacts.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        return contacts[:10]

    async def _generate_generic_contacts(
        self, domain: str
    ) -> list[dict[str, Any]]:
        """Generate well-known generic email addresses for the domain."""
        contacts = []
        for name, pattern, contact_type, confidence in GENERIC_CONTACTS:
            contacts.append({
                "name": name.capitalize(),
                "title": contact_type.replace("_", " ").title(),
                "email": pattern.format(domain=domain),
                "contact_type": contact_type,
                "confidence": confidence,
                "verified": False,
                "source": "pattern",
            })
        return contacts

    async def _scrape_website_contacts(
        self, company: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Scrape the company website for email addresses."""
        website = company.get("website_url", "")
        domain = company.get("domain", "")

        if not website and domain:
            website = f"https://{domain}"

        if not website:
            return []

        contacts = []
        pages_to_check = [
            website,
            f"{website.rstrip('/')}/about",
            f"{website.rstrip('/')}/team",
            f"{website.rstrip('/')}/careers",
            f"{website.rstrip('/')}/contact",
            f"{website.rstrip('/')}/jobs",
        ]

        found_emails: set[str] = set()

        async with httpx.AsyncClient(
            timeout=10.0,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            for page_url in pages_to_check[:3]:
                try:
                    response = await client.get(page_url)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, "html.parser")
                    text = soup.get_text(" ", strip=True)

                    # Find emails in page text
                    email_regex = re.compile(
                        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
                    )
                    for match in email_regex.finditer(text):
                        email = match.group(0).lower()
                        # Skip image/asset emails and common non-contacts
                        if (
                            email in found_emails
                            or any(ext in email for ext in [".png", ".jpg", ".gif", ".svg", ".css"])
                            or email.endswith((".example.com", "@sentry.io", "@bugsnag.com"))
                        ):
                            continue

                        found_emails.add(email)

                        # Determine contact type from email
                        contact_type = "other"
                        local_part = email.split("@")[0]
                        if any(x in local_part for x in ["recruit", "talent", "hr", "hiring", "people"]):
                            contact_type = "recruiter"
                        elif any(x in local_part for x in ["founder", "ceo", "cto", "coo"]):
                            contact_type = "founder"
                        elif any(x in local_part for x in ["engineer", "eng", "dev"]):
                            contact_type = "engineer"
                        elif any(x in local_part for x in ["careers", "jobs", "apply"]):
                            contact_type = "hr"

                        contacts.append({
                            "name": local_part.replace(".", " ").replace("-", " ").title(),
                            "title": "",
                            "email": email,
                            "contact_type": contact_type,
                            "confidence": 0.75,
                            "verified": False,
                            "source": f"scraped:{page_url}",
                        })

                except (httpx.HTTPError, Exception):
                    continue

        return contacts[:5]

    async def _search_hunter(self, domain: str) -> list[dict[str, Any]]:
        """Search Hunter.io email finder API (requires API key)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.hunter.io/v2/domain-search",
                    params={
                        "domain": domain,
                        "api_key": self._hunter_api_key,
                        "limit": 10,
                        "type": "personal",
                    },
                )
                if response.status_code != 200:
                    return []

                data = response.json()
                emails = data.get("data", {}).get("emails", [])

        except Exception:
            return []

        contacts = []
        for e in emails:
            contact_type = "other"
            dept = (e.get("department") or "").lower()
            if "recruit" in dept or "talent" in dept or "hr" in dept:
                contact_type = "recruiter"
            elif "engineer" in dept or "tech" in dept:
                contact_type = "engineer"
            elif "executive" in dept:
                contact_type = "founder"

            contacts.append({
                "name": f"{e.get('first_name', '')} {e.get('last_name', '')}".strip(),
                "title": e.get("position", ""),
                "email": e.get("value", ""),
                "contact_type": contact_type,
                "linkedin_url": e.get("linkedin", ""),
                "confidence": e.get("confidence", 50) / 100,
                "verified": e.get("verification", {}).get("status") == "valid",
                "source": "hunter.io",
            })

        return contacts
