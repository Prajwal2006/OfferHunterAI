"""Shared anti-bot resilience helpers for scraping-only fallbacks."""

from __future__ import annotations

import random


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
]


def browser_headers() -> dict[str, str]:
    """Return human-browser-like headers for sources without public APIs."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def detect_anti_bot(status_code: int, text: str) -> str:
    """Classify common anti-bot responses for diagnostics."""
    lowered = (text or "").lower()[:3000]
    if status_code in {401, 403, 429}:
        return f"HTTP {status_code} likely access/rate-limit block"
    if any(token in lowered for token in ["captcha", "cloudflare", "checking your browser", "bot detection", "challenge"]):
        return "Blocked by anti-bot challenge"
    return ""
