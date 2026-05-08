"""Normalized work-mode inference shared across discovery sources."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Iterable


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


STRICT_REMOTE_CONFIDENCE = 0.8

_REMOTE_PATTERNS = [
    r"\bremote\b",
    r"work\s+from\s+anywhere",
    r"distributed\s+team",
    r"anywhere\s+in\s+(?:the\s+)?world",
    r"anywhere\s+in\s+(?:the\s+)?us",
    r"fully\s+remote",
    r"remote-first",
    r"remote friendly",
    r"remote role",
]
_HYBRID_PATTERNS = [
    r"\bhybrid\b",
    r"flexible\s+hybrid",
    r"\d+\s+days?\s+(?:a\s+week\s+)?onsite",
    r"split\s+between\s+home\s+and\s+office",
]
_ONSITE_PATTERNS = [
    r"\bonsite\b",
    r"\bon-site\b",
    r"in-?office",
    r"office-based",
    r"must\s+be\s+based\s+in",
    r"relocate\s+to",
]
_AMBIGUOUS_PATTERNS = [
    r"flexible\s+work",
    r"flexible\s+work\s+environment",
    r"work\s+flexibly",
]
_LOCATION_HINT_PATTERNS = [
    r"\b(?:san\s+francisco|new\s+york|seattle|austin|london|berlin|toronto|vancouver|singapore)\b",
    r"\b(?:ca|ny|wa|tx|ma|il|fl)\b",
]

_SOURCE_DEFAULTS: dict[str, tuple[WorkMode, float, str]] = {
    "RemoteOK": (WorkMode.REMOTE, 0.99, "RemoteOK only lists remote roles"),
}


def _flatten_signal(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "remote" if value else ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_signal(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_signal(item) for item in value)
    return str(value)


def _search_patterns(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def infer_work_mode(
    signals: Iterable[Any],
    *,
    source: str = "",
) -> tuple[WorkMode, float, list[str]]:
    """Infer a normalized work mode from free-form source metadata."""
    text = " ".join(_flatten_signal(signal) for signal in signals if signal is not None).strip()
    lowered = re.sub(r"\s+", " ", text.lower())
    reasons: list[str] = []

    if lowered:
        hybrid_match = _search_patterns(lowered, _HYBRID_PATTERNS)
        if hybrid_match:
            reasons.append(f"Matched hybrid signal: {hybrid_match}")
            return WorkMode.HYBRID, 0.92, reasons

        onsite_match = _search_patterns(lowered, _ONSITE_PATTERNS)
        if onsite_match:
            reasons.append(f"Matched onsite signal: {onsite_match}")
            return WorkMode.ONSITE, 0.9, reasons

        remote_match = _search_patterns(lowered, _REMOTE_PATTERNS)
        if remote_match:
            reasons.append(f"Matched remote signal: {remote_match}")
            return WorkMode.REMOTE, 0.93, reasons

        if _search_patterns(lowered, _LOCATION_HINT_PATTERNS):
            reasons.append("Specific office location found without remote markers")
            return WorkMode.ONSITE, 0.72, reasons

        ambiguous_match = _search_patterns(lowered, _AMBIGUOUS_PATTERNS)
        if ambiguous_match:
            reasons.append(f"Ambiguous work arrangement phrase: {ambiguous_match}")
            return WorkMode.UNKNOWN, 0.35, reasons

    source_default = _SOURCE_DEFAULTS.get(source)
    if source_default:
        mode, confidence, reason = source_default
        reasons.append(reason)
        return mode, confidence, reasons

    reasons.append("No explicit work-mode signal detected")
    return WorkMode.UNKNOWN, 0.2, reasons


def normalize_work_mode(value: Any, *, source: str = "") -> WorkMode:
    mode, _, _ = infer_work_mode([value], source=source)
    return mode


def normalize_job_work_mode(job: dict[str, Any], *, source: str = "") -> dict[str, Any]:
    normalized = dict(job)
    mode, confidence, reasons = infer_work_mode(
        [
            normalized.get("work_mode"),
            normalized.get("workplace_type"),
            normalized.get("location"),
            normalized.get("description"),
            normalized.get("tags"),
            normalized.get("source_work_mode_hint"),
            normalized.get("remote_friendly"),
            normalized.get("is_remote"),
        ],
        source=source,
    )
    normalized["work_mode"] = mode.value
    normalized["remote_confidence"] = confidence if mode is WorkMode.REMOTE else min(confidence, 0.49)
    normalized["work_mode_reasoning"] = reasons
    return normalized


def normalize_company_work_mode(company: dict[str, Any], *, source: str = "") -> dict[str, Any]:
    normalized = dict(company)
    positions = [
        normalize_job_work_mode(job, source=source or str(normalized.get("source") or ""))
        for job in (normalized.get("open_positions") or [])
        if isinstance(job, dict)
    ]
    normalized["open_positions"] = positions

    source_name = source or str(normalized.get("source") or "")
    top_mode, top_confidence, top_reasons = infer_work_mode(
        [
            normalized.get("work_mode"),
            normalized.get("headquarters"),
            normalized.get("description"),
            normalized.get("culture_tags"),
            normalized.get("remote_friendly"),
            (normalized.get("metadata") or {}).get("work_mode"),
        ],
        source=source_name,
    )

    if positions:
        remote_positions = [job for job in positions if job.get("work_mode") == WorkMode.REMOTE.value]
        hybrid_positions = [job for job in positions if job.get("work_mode") == WorkMode.HYBRID.value]
        onsite_positions = [job for job in positions if job.get("work_mode") == WorkMode.ONSITE.value]

        if remote_positions and not hybrid_positions and not onsite_positions:
            normalized_mode = WorkMode.REMOTE
            normalized_confidence = max(float(job.get("remote_confidence") or 0.0) for job in remote_positions)
            reasons = ["All matched jobs are remote"]
        elif hybrid_positions and not remote_positions and not onsite_positions:
            normalized_mode = WorkMode.HYBRID
            normalized_confidence = 0.9
            reasons = ["Matched jobs are classified as hybrid"]
        elif onsite_positions and not remote_positions and not hybrid_positions:
            normalized_mode = WorkMode.ONSITE
            normalized_confidence = 0.9
            reasons = ["Matched jobs are classified as onsite"]
        elif remote_positions and (hybrid_positions or onsite_positions):
            normalized_mode = WorkMode.HYBRID if hybrid_positions else WorkMode.UNKNOWN
            normalized_confidence = 0.55
            reasons = ["Matched jobs include both remote and non-remote roles"]
        else:
            normalized_mode = top_mode
            normalized_confidence = top_confidence
            reasons = top_reasons
    else:
        normalized_mode = top_mode
        normalized_confidence = top_confidence
        reasons = top_reasons

    normalized["work_mode"] = normalized_mode.value
    normalized["remote_confidence"] = (
        normalized_confidence if normalized_mode is WorkMode.REMOTE else min(normalized_confidence, 0.49)
    )
    normalized["work_mode_reasoning"] = reasons
    normalized["remote_friendly"] = normalized_mode is WorkMode.REMOTE or bool(normalized.get("remote_friendly"))
    return normalized