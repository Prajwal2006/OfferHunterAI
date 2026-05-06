"""
PreferenceCollectorService — Conversational AI for collecting user job preferences.

Maintains a conversation thread, asks contextual questions based on the resume
profile, avoids duplicate questions, and returns structured preferences.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent career coach assistant for OfferHunterAI.
Your job is to conversationally collect job search preferences from the user.

You already have their resume profile. Ask smart, contextual questions — don't ask
things you can already infer from their resume. Keep questions concise and friendly.

When you have gathered enough information to fill the preferences JSON (or the user
signals they're done), respond with a special line:
  PREFERENCES_COMPLETE: {json}

Where {json} is a valid JSON object with all collected preferences.

Track what you've already asked. Never repeat a question.

Preferences to collect:
- preferred_roles: list of job roles (confirm/update from resume inferences)
- preferred_locations: list of cities/regions
- open_to_relocation: boolean
- work_mode: "remote" | "hybrid" | "onsite" | "flexible"
- employment_type: list of ["internship", "full_time", "part_time", "contract"]
- salary_min: integer (USD annual)
- salary_max: integer (USD annual)
- open_to_startups: boolean
- company_size_pref: list of ["startup (<50)", "small (50-200)", "mid (200-1000)", "large (1000-5000)", "enterprise (5000+)"]
- industries_of_interest: list of industries
- sponsorship_required: boolean
- work_authorization: string (e.g. "US Citizen", "H1B", "OPT", "CPT", "Green Card")
- graduation_date: string (YYYY-MM)
- earliest_start: string (e.g. "Immediately", "June 2025")
- preferred_tech_stack: list of technologies
- career_priorities: dict with keys: compensation, learning, brand_value, growth, work_life_balance, research — each scored 1-5
- avoided_companies: list of company names
- avoided_industries: list of industries
- open_to_cold_outreach: boolean
- profile_links: dict with keys: github, linkedin, portfolio, twitter, devpost, kaggle, leetcode

Be warm, concise, and professional. One or two questions per message."""


def _build_initial_message(profile: dict[str, Any]) -> str:
    name = profile.get("full_name") or "there"
    skills = profile.get("skills") or []
    tech_stack = profile.get("tech_stack") or []
    work_exp = profile.get("work_experience") or []
    roles = profile.get("preferred_domains") or []

    # Build a readable skills/experience summary
    all_skills = list(dict.fromkeys(skills[:4] + tech_stack[:3]))  # deduplicated
    skills_preview = ", ".join(all_skills[:5]) if all_skills else None

    most_recent = None
    if work_exp:
        most_recent = work_exp[0].get("title") or work_exp[0].get("company")

    edu = profile.get("education") or []
    degree_str = ""
    if edu:
        e = edu[0]
        field = e.get("field") or ""
        inst = e.get("institution") or ""
        if field and inst:
            degree_str = f" studying {field} at {inst}"
        elif inst:
            degree_str = f" at {inst}"

    # Build the opening line
    parts = [f"Hi {name}!"]
    if degree_str:
        parts.append(f"I've reviewed your resume{degree_str}.")
    else:
        parts.append("I've reviewed your resume.")

    if skills_preview:
        parts.append(f"I can see you have experience with {skills_preview}.")
    elif most_recent:
        parts.append(f"I can see you've worked as a {most_recent}.")

    parts.append("Let's find the best companies for you — I'll ask a few quick questions.")
    if roles:
        parts.append(f"Based on your background, I'll start with roles like {', '.join(roles[:2])}.")

    return " ".join(parts)


# ─── Service ──────────────────────────────────────────────────────────────────

class PreferenceCollectorService:
    """
    Manages a conversational session to collect user preferences.

    Each call to `chat()` takes the user's message and conversation history,
    returns the assistant reply and any completed preferences dict.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._base_url = "https://api.openai.com/v1"

    def get_initial_message(self, profile: dict[str, Any]) -> str:
        """Return the first message to start the preferences conversation."""
        return _build_initial_message(profile)

    async def chat(
        self,
        user_message: str,
        history: list[dict[str, str]],
        profile: dict[str, Any],
        current_prefs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process user message and return:
          {
            "reply": "assistant message",
            "preferences": dict | None,   # filled when PREFERENCES_COMPLETE
            "is_complete": bool,
          }
        """
        if not self._api_key:
            return self._fallback_reply(user_message, history, current_prefs)

        # Build the messages list for the API call
        context_note = (
            f"\n\nUser's resume summary:\n"
            f"- Name: {profile.get('full_name', 'Unknown')}\n"
            f"- Skills: {', '.join(profile.get('skills', [])[:10])}\n"
            f"- Tech stack: {', '.join(profile.get('tech_stack', [])[:8])}\n"
            f"- Preferred domains: {', '.join(profile.get('preferred_domains', []))}\n"
            f"- Education: {json.dumps(profile.get('education', [])[:2])}\n"
            f"- LinkedIn: {profile.get('linkedin_url', 'not provided')}\n"
            f"- GitHub: {profile.get('github_url', 'not provided')}\n"
        )
        if current_prefs:
            context_note += f"\nAlready collected preferences:\n{json.dumps(current_prefs, indent=2)}\n"
            context_note += "\nDo NOT ask about anything already in the collected preferences above."

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + context_note},
            *history,
            {"role": "user", "content": user_message},
        ]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]

            return self._parse_response(content)
        except Exception as e:
            return {
                "reply": "I'm having trouble connecting right now. Please try again in a moment.",
                "preferences": None,
                "is_complete": False,
                "error": str(e),
            }

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        """Check if the response contains PREFERENCES_COMPLETE and extract JSON."""
        marker = "PREFERENCES_COMPLETE:"
        if marker in content:
            idx = content.index(marker)
            reply_part = content[:idx].strip()
            json_part = content[idx + len(marker):].strip()

            # Extract the first JSON object
            brace_start = json_part.find("{")
            brace_end = json_part.rfind("}") + 1
            if brace_start != -1 and brace_end > brace_start:
                try:
                    prefs = json.loads(json_part[brace_start:brace_end])
                    return {
                        "reply": reply_part or "Great! I have all the information I need. Let me find the best companies for you!",
                        "preferences": prefs,
                        "is_complete": True,
                    }
                except json.JSONDecodeError:
                    pass

        return {
            "reply": content,
            "preferences": None,
            "is_complete": False,
        }

    @staticmethod
    def _fallback_reply(
        user_message: str,
        history: list[dict[str, str]],
        current_prefs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Simple rule-based fallback when AI is unavailable."""
        turn = len([m for m in history if m["role"] == "assistant"])
        questions = [
            "What job roles are you targeting? (e.g. Software Engineer, ML Engineer)",
            "What locations do you prefer? Are you open to relocation?",
            "Do you prefer remote, hybrid, or onsite work?",
            "Are you looking for internships, full-time, or both?",
            "What is your expected salary range?",
            "Are you open to startups? What company size do you prefer?",
            "Do you require visa sponsorship?",
            "When are you available to start?",
            "What are your top career priorities? (compensation, learning, growth, etc.)",
        ]

        if turn < len(questions):
            return {
                "reply": questions[turn],
                "preferences": None,
                "is_complete": False,
            }

        # Compile basic preferences from conversation
        prefs: dict[str, Any] = current_prefs or {}
        prefs.setdefault("preferred_roles", [])
        prefs.setdefault("work_mode", "flexible")
        prefs.setdefault("open_to_startups", True)
        prefs.setdefault("open_to_cold_outreach", True)
        prefs.setdefault("profile_links", {})

        return {
            "reply": "Thanks! I have enough information to find great matches for you.",
            "preferences": prefs,
            "is_complete": True,
        }
