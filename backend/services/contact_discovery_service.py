"""Layered contact discovery and ranking for outreach."""
from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OfferHunterAI/1.0; contact discovery)",
    "Accept": "text/html,application/xhtml+xml",
}


class ContactDiscoveryService:
    """Finds public emails and ranks likely outreach recipients."""

    TARGET_PATHS = ["", "/contact", "/about", "/team", "/careers", "/jobs", "/press"]
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

    async def discover(self, company: dict[str, Any], job: dict[str, Any] | None = None) -> dict[str, Any]:
        domain = self._domain(company)
        if not domain:
            return {"contacts": []}
        scraped, guessed = await asyncio.gather(
            self._scrape(company, domain),
            self._pattern_guesses(company, domain),
            return_exceptions=True,
        )
        contacts: list[dict[str, Any]] = []
        for result in [scraped, guessed]:
            if isinstance(result, list):
                contacts.extend(result)
        deduped = self._dedupe(contacts)
        ranked = [self._rank(c, company, job or {}) for c in deduped]
        ranked.sort(key=lambda c: c["priority_score"], reverse=True)
        return {"contacts": ranked[:15]}

    def _domain(self, company: dict[str, Any]) -> str:
        domain = (company.get("domain") or "").strip().lower()
        if domain:
            return domain.replace("https://", "").replace("http://", "").split("/")[0]
        website = (company.get("website_url") or "").strip().lower()
        return website.replace("https://", "").replace("http://", "").split("/")[0]

    async def _scrape(self, company: dict[str, Any], domain: str) -> list[dict[str, Any]]:
        base = company.get("website_url") or f"https://{domain}"
        contacts: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            for path in self.TARGET_PATHS:
                url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
                try:
                    response = await client.get(url)
                    if response.status_code >= 400 or "text/html" not in response.headers.get("content-type", ""):
                        continue
                    soup = BeautifulSoup(response.text, "html.parser")
                    text = soup.get_text(" ", strip=True)
                    for email in self.EMAIL_RE.findall(text):
                        email = email.lower()
                        if not self._usable(email, domain):
                            continue
                        contacts.append({
                            "name": self._name_from_email(email),
                            "role": self._role_from_email(email),
                            "title": self._role_from_email(email),
                            "email": email,
                            "confidence": 0.82 if email.endswith("@" + domain) else 0.68,
                            "verified": False,
                            "source": url,
                            "contact_type": self._type_from_email(email),
                        })
                except Exception:
                    continue
        return contacts

    async def _pattern_guesses(self, company: dict[str, Any], domain: str) -> list[dict[str, Any]]:
        contacts = [
            ("Talent", "talent", "Recruiting", 0.58, "recruiter"),
            ("Careers", "careers", "Careers", 0.56, "hr"),
            ("Jobs", "jobs", "Careers", 0.52, "hr"),
            ("Recruiting", "recruiting", "Recruiting", 0.6, "recruiter"),
            ("Hello", "hello", "General", 0.38, "other"),
        ]
        founder = self._founder_name(company)
        rows = [
            {
                "name": name,
                "role": role,
                "title": role,
                "email": f"{local}@{domain}",
                "confidence": confidence,
                "verified": False,
                "source": "pattern",
                "contact_type": contact_type,
            }
            for name, local, role, confidence, contact_type in contacts
        ]
        if founder:
            first, *rest = founder.lower().split()
            last = rest[-1] if rest else ""
            patterns = [first, f"{first}.{last}" if last else "", f"{first[0]}{last}" if last else ""]
            for local in [p for p in patterns if p]:
                rows.append({
                    "name": founder.title(),
                    "role": "Founder",
                    "title": "Founder",
                    "email": f"{local}@{domain}",
                    "confidence": 0.48,
                    "verified": False,
                    "source": "founder_pattern",
                    "contact_type": "founder",
                })
        return rows

    def _dedupe(self, contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_email: dict[str, dict[str, Any]] = {}
        for contact in contacts:
            email = (contact.get("email") or "").lower()
            if not email:
                continue
            existing = by_email.get(email)
            if not existing or contact.get("confidence", 0) > existing.get("confidence", 0):
                by_email[email] = contact
        return list(by_email.values())

    def _rank(self, contact: dict[str, Any], company: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        role = f"{contact.get('role', '')} {contact.get('title', '')} {contact.get('email', '')}".lower()
        score = int(float(contact.get("confidence", 0.4)) * 65)
        if any(x in role for x in ["founder", "ceo", "cto"]):
            score += 25 if self._is_startup(company) else 12
        if any(x in role for x in ["talent", "recruit", "hiring"]):
            score += 20
        if any(x in role for x in ["engineering", "engineer", "cto"]):
            score += 12
        if job and any(x in role for x in ["recruit", "hiring", "talent", "engineering"]):
            score += 8
        if contact.get("source") != "pattern":
            score += 8
        return {**contact, "priority_score": max(1, min(100, score))}

    def _usable(self, email: str, domain: str) -> bool:
        if any(ext in email for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js"]):
            return False
        if any(skip in email for skip in ["example.com", "sentry.io", "wixpress.com"]):
            return False
        return "." in email.split("@")[-1] and (email.endswith("@" + domain) or domain.split(".")[0] in email)

    def _name_from_email(self, email: str) -> str:
        local = email.split("@")[0]
        return local.replace(".", " ").replace("_", " ").replace("-", " ").title()

    def _role_from_email(self, email: str) -> str:
        local = email.split("@")[0].lower()
        if any(x in local for x in ["founder", "ceo"]):
            return "Founder"
        if "cto" in local:
            return "CTO"
        if any(x in local for x in ["talent", "recruit", "hiring"]):
            return "Recruiting"
        if any(x in local for x in ["career", "jobs", "hr", "people"]):
            return "People"
        if any(x in local for x in ["eng", "dev"]):
            return "Engineering"
        return "General"

    def _type_from_email(self, email: str) -> str:
        role = self._role_from_email(email).lower()
        if role in {"founder", "cto"}:
            return "founder"
        if role == "recruiting":
            return "recruiter"
        if role == "people":
            return "hr"
        if role == "engineering":
            return "engineer"
        return "other"

    def _founder_name(self, company: dict[str, Any]) -> str:
        info = company.get("founder_info") or company.get("metadata", {}).get("founder_info") or {}
        if isinstance(info, dict):
            return str(info.get("name") or "")
        if isinstance(info, list) and info:
            first = info[0]
            return str(first.get("name") if isinstance(first, dict) else first)
        return ""

    def _is_startup(self, company: dict[str, Any]) -> bool:
        text = f"{company.get('funding_stage', '')} {company.get('size', '')}".lower()
        return any(x in text for x in ["seed", "series", "yc", "1-", "10-", "50"])
