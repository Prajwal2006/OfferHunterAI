"""Immutable draft versioning for outreach emails."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class VersioningService:
    """Builds version rows and lightweight comparisons."""

    def create_version(
        self,
        *,
        draft: dict[str, Any],
        event_type: str,
        editor: str,
        changes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "draft_id": draft.get("id"),
            "user_id": draft.get("user_id"),
            "company_id": draft.get("company_id"),
            "version_number": int(draft.get("version_number") or 0) + 1,
            "subject": draft.get("subject") or "",
            "body": draft.get("body") or "",
            "recipient_email": draft.get("recipient_email"),
            "snapshot": draft,
            "event_type": event_type,
            "editor": editor,
            "changes": changes or {},
            "created_at": datetime.utcnow().isoformat(),
        }

    def compare(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        import difflib

        return {
            "subject_changed": left.get("subject") != right.get("subject"),
            "body_diff": "\n".join(
                difflib.unified_diff(
                    (left.get("body") or "").splitlines(),
                    (right.get("body") or "").splitlines(),
                    fromfile=f"v{left.get('version_number')}",
                    tofile=f"v{right.get('version_number')}",
                    lineterm="",
                )
            ),
            "left": left,
            "right": right,
        }
