"""
ResumeParserService — AI-powered structured extraction from resume text.

Uses OpenAI GPT-4o to extract a rich structured JSON profile from raw resume
text. Falls back to regex-based heuristics when the AI call fails.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert resume parser. Extract ALL available information
from the resume text into a structured JSON object. Be thorough and precise.
Return ONLY valid JSON, no markdown code fences, no extra text."""

USER_PROMPT_TEMPLATE = """Extract all information from this resume into JSON with exactly
these keys (use empty arrays/strings for missing data, never null):

{{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "citizenship": "string (citizenship or visa status if mentioned, else empty)",
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field": "string",
      "graduation_date": "string",
      "gpa": "string"
    }}
  ],
  "gpa": "string (highest/most recent GPA, e.g. '3.9/4.0')",
  "skills": ["list of all technical and soft skills"],
  "tech_stack": ["programming languages, frameworks, tools, databases, cloud platforms"],
  "certifications": ["list of certifications"],
  "work_experience": [
    {{
      "company": "string",
      "title": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string",
      "is_current": false,
      "bullets": ["list of bullet points"]
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "tech_used": ["list"],
      "url": "string"
    }}
  ],
  "leadership": ["list of leadership roles/experiences"],
  "research": ["list of research experience or publications"],
  "awards": ["list of awards and honors"],
  "preferred_domains": ["inferred job domains from experience, e.g. 'Machine Learning', 'Full Stack Development'"],
  "keywords": ["50 most important keywords from the resume for job matching"],
  "linkedin_url": "string",
  "github_url": "string",
  "portfolio_url": "string",
  "other_links": ["list of other URLs"]
}}

Resume text:
{resume_text}"""


# ─── Service ──────────────────────────────────────────────────────────────────

class ResumeParserService:
    """
    Parses a resume text string into a structured profile dict using AI.

    Usage:
        parser = ResumeParserService()
        profile = await parser.parse(resume_text)
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._base_url = "https://api.openai.com/v1"

    async def parse(self, resume_text: str) -> dict[str, Any]:
        """
        Parse a resume text and return a structured profile dict.
        Falls back to heuristic extraction if AI is unavailable.
        """
        if self._api_key:
            try:
                return await self._parse_with_ai(resume_text)
            except Exception:
                pass
        return self._parse_with_heuristics(resume_text)

    async def _parse_with_ai(self, resume_text: str) -> dict[str, Any]:
        truncated = resume_text[:12000]  # stay within token budget
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(resume_text=truncated),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["raw_text"] = resume_text
            return self._normalize(parsed)

    def _parse_with_heuristics(self, text: str) -> dict[str, Any]:
        """Best-effort extraction using regex patterns."""
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
        phone_match = re.search(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
        )
        github_match = re.search(
            r"(?:https?://)?(?:www\.)?github\.com/[\w-]+", text, re.IGNORECASE
        )
        linkedin_match = re.search(
            r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", text, re.IGNORECASE
        )
        portfolio_match = re.search(
            r"(?:https?://)?(?:www\.)?(?!github|linkedin)[\w-]+\.(?:io|dev|me|com)/[\w/-]*",
            text,
            re.IGNORECASE,
        )

        # Extract skills from common skill keywords
        common_skills = [
            "Python", "JavaScript", "TypeScript", "React", "Node.js", "SQL",
            "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS",
            "GCP", "Azure", "Git", "FastAPI", "Django", "Flask", "Next.js",
            "Vue", "Angular", "GraphQL", "REST", "Machine Learning", "TensorFlow",
            "PyTorch", "scikit-learn", "Pandas", "NumPy", "Java", "Go", "Rust",
            "C++", "C#", "Swift", "Kotlin", "Ruby", "PHP", "Scala", "R",
        ]
        found_skills = [s for s in common_skills if re.search(rf"\b{re.escape(s)}\b", text, re.IGNORECASE)]

        return self._normalize({
            "full_name": "",
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0) if phone_match else "",
            "location": "",
            "citizenship": "",
            "education": [],
            "gpa": "",
            "skills": found_skills,
            "tech_stack": found_skills,
            "certifications": [],
            "work_experience": [],
            "projects": [],
            "leadership": [],
            "research": [],
            "awards": [],
            "preferred_domains": [],
            "keywords": found_skills,
            "linkedin_url": linkedin_match.group(0) if linkedin_match else "",
            "github_url": github_match.group(0) if github_match else "",
            "portfolio_url": portfolio_match.group(0) if portfolio_match else "",
            "other_links": [],
            "raw_text": text,
        })

    @staticmethod
    def _normalize(profile: dict[str, Any]) -> dict[str, Any]:
        """Ensure all expected keys exist with correct default types."""
        defaults: dict[str, Any] = {
            "full_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "citizenship": "",
            "education": [],
            "gpa": "",
            "skills": [],
            "tech_stack": [],
            "certifications": [],
            "work_experience": [],
            "projects": [],
            "leadership": [],
            "research": [],
            "awards": [],
            "preferred_domains": [],
            "keywords": [],
            "linkedin_url": "",
            "github_url": "",
            "portfolio_url": "",
            "other_links": [],
            "raw_text": "",
        }
        for key, default in defaults.items():
            if key not in profile or profile[key] is None:
                profile[key] = default
        return profile
