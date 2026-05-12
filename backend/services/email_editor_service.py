"""Inline AI editing for human-reviewed email drafts."""
from __future__ import annotations

from difflib import unified_diff
import re
from typing import Any

from .ai_common import AIServiceError, OpenAIJsonClient, compact_json


class EmailEditorService:
    """Rewrites selected draft text and returns a diff preview for accept/reject UX."""

    def __init__(self) -> None:
        self.ai = OpenAIJsonClient()

    async def edit_selection(
        self,
        *,
        instruction: str,
        selected_text: str,
        full_body: str,
        subject: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        instruction = instruction.strip()
        selected_text = selected_text or full_body
        replacement = self._deterministic_edit(instruction, selected_text)

        if self.ai.enabled:
            system = (
                "You are an inline email editor. Return only JSON with keys replacement_text and rationale. "
                "Edit only the selected text. Preserve facts. Do not add unsupported claims. "
                "Keep career outreach in first person from the sender's perspective: use I, me, my, and mine. "
                "Never refer to the sender as the user, the candidate, the applicant, or this profile."
            )
            user = (
                f"Instruction: {instruction}\nSubject: {subject}\nSelected text:\n{selected_text}\n\n"
                f"Full email context:\n{full_body}\n\nAdditional context:\n{compact_json(context or {}, 6000)}"
            )
            try:
                data = await self.ai.create_json(
                    system=system,
                    user=user,
                    temperature=0.35,
                    max_tokens=1200,
                    user_id=str((context or {}).get("user_id") or "") or None,
                    context_metadata={
                        "operation": "inline_email_edit",
                        "instruction": instruction,
                        "subject": subject,
                        "selected_text": selected_text,
                        "full_body": full_body,
                        "context": context or {},
                    },
                )
                replacement = str(data.get("replacement_text") or replacement).strip()
                rationale = str(data.get("rationale") or "AI rewrite based on the instruction.")
            except (AIServiceError, ValueError, TypeError):
                rationale = "Rule-based rewrite because AI editing was unavailable."
        else:
            rationale = "Rule-based rewrite because AI editing is not configured."

        replacement = self._sanitize_first_person(replacement)
        updated_body = full_body.replace(selected_text, replacement, 1) if selected_text in full_body else replacement
        diff = "\n".join(
            unified_diff(
                selected_text.splitlines(),
                replacement.splitlines(),
                fromfile="selected",
                tofile="proposed",
                lineterm="",
            )
        )
        return {
            "original_text": selected_text,
            "replacement_text": replacement,
            "updated_body": updated_body,
            "diff": diff,
            "rationale": rationale,
        }

    def _deterministic_edit(self, instruction: str, selected_text: str) -> str:
        lower = instruction.lower()
        text = " ".join(selected_text.split()) if "short" in lower or "fluff" in lower else selected_text.strip()
        if "short" in lower or "remove fluff" in lower:
            sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
            return ". ".join(sentences[:2]) + ("." if sentences else "")
        if "confident" in lower:
            return text.replace("I believe", "I am confident").replace("I think", "I know").replace("would love", "would be excited")
        if "friend" in lower or "startup" in lower:
            return text.replace("Dear", "Hi").replace("I am writing to express", "I wanted to reach out because")
        if "professional" in lower:
            return text.replace("Hi there", "Hi").replace("super", "very").replace("awesome", "impressive")
        if "ai experience" in lower and "AI" not in text:
            return f"{text} I can also bring hands-on AI engineering experience across applied model workflows and production software."
        return text

    def _sanitize_first_person(self, text: str) -> str:
        replacements = [
            (r"\bthe user is qualified in\b", "I have experience in"),
            (r"\bthe user has experience in\b", "I have experience in"),
            (r"\bthe user's background\b", "my background"),
            (r"\bthe user's\b", "my"),
            (r"\bthe user\b", "I"),
            (r"\bthis candidate's\b", "my"),
            (r"\bthe candidate's\b", "my"),
            (r"\bthis candidate is\b", "I am"),
            (r"\bthe candidate is\b", "I am"),
            (r"\bthe candidate has\b", "I have"),
            (r"\bthe candidate can\b", "I can"),
            (r"\bthe candidate\b", "I"),
            (r"\bthe applicant's\b", "my"),
            (r"\bthe applicant is\b", "I am"),
            (r"\bthe applicant has\b", "I have"),
            (r"\bthe applicant\b", "I"),
        ]
        cleaned = text.strip()
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bI is\b", "I am", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bI has\b", "I have", cleaned, flags=re.IGNORECASE)
        return cleaned
