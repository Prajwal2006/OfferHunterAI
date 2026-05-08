"""Mandatory preference enforcement that runs before downstream processing."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ...models.work_mode import STRICT_REMOTE_CONFIDENCE, WorkMode, normalize_company_work_mode


@dataclass
class HardConstraintResult:
    visible_companies: list[dict[str, Any]]
    hidden_companies: list[dict[str, Any]]
    counts_by_source: dict[str, dict[str, int]]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def normalize_preference_payload(preferences: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(preferences or {})
    if _as_bool(normalized.get("remote_only")):
        normalized["work_mode"] = WorkMode.REMOTE.value
    normalized.pop("remote_only", None)
    return normalized


def _strict_remote_enabled(preferences: dict[str, Any]) -> bool:
    return _as_bool(preferences.get("remote_only")) or str(preferences.get("work_mode") or "").lower() == WorkMode.REMOTE.value


def _normalized_set(values: Any) -> set[str]:
    if not values:
        return set()
    if not isinstance(values, (list, tuple, set)):
        values = [values]
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _location_matches_any(value: str, tokens: set[str]) -> bool:
    lowered = (value or "").lower()
    return any(token in lowered for token in tokens)


def _parse_salary_bounds(value: Any) -> tuple[int | None, int | None]:
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        amount = int(value)
        return amount, amount
    matches = [int(match.replace(",", "")) for match in re.findall(r"\$?([0-9]{2,3}(?:,[0-9]{3})+|[0-9]{5,6})", str(value))]
    if not matches:
        return None, None
    return min(matches), max(matches)


def _ensure_source_counts(counts: dict[str, dict[str, int]], source: str) -> dict[str, int]:
    return counts.setdefault(
        source,
        {
            "hard_constraints_filtered": 0,
            "remote_filtered": 0,
            "hybrid_filtered": 0,
            "onsite_filtered": 0,
            "unknown_filtered": 0,
            "blocked_company_filtered": 0,
            "visa_filtered": 0,
            "salary_filtered": 0,
            "location_filtered": 0,
            "visible": 0,
        },
    )


def _job_passes_constraints(job: dict[str, Any], preferences: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    strict_remote = _strict_remote_enabled(preferences)
    if strict_remote:
        if job.get("work_mode") != WorkMode.REMOTE.value:
            reasons.append(f"work_mode={job.get('work_mode', WorkMode.UNKNOWN.value)}")
        elif float(job.get("remote_confidence") or 0.0) < STRICT_REMOTE_CONFIDENCE:
            reasons.append(f"remote_confidence<{STRICT_REMOTE_CONFIDENCE:.2f}")

    salary_min = preferences.get("salary_min")
    if salary_min is not None:
        _, job_max = _parse_salary_bounds(job.get("salary_range"))
        if job_max is not None and job_max < int(salary_min):
            reasons.append("salary_below_minimum")

    excluded_locations = _normalized_set(preferences.get("excluded_countries") or preferences.get("excluded_locations"))
    if excluded_locations and _location_matches_any(str(job.get("location") or ""), excluded_locations):
        reasons.append("excluded_location")

    preferred_locations = _normalized_set(preferences.get("preferred_locations"))
    if preferred_locations and not _strict_remote_enabled(preferences) and not _as_bool(preferences.get("open_to_relocation")):
        if job.get("location") and not _location_matches_any(str(job.get("location") or ""), preferred_locations):
            reasons.append("outside_preferred_locations")

    return not reasons, reasons


def _annotate_hidden_company(company: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    annotated = dict(company)
    annotated["preference_enforcement"] = {
        **dict(annotated.get("preference_enforcement") or {}),
        "hidden_by_preferences": True,
        "reasons": reasons,
    }
    return annotated


def _apply_company_constraints(company: dict[str, Any], preferences: dict[str, Any]) -> tuple[bool, dict[str, Any], list[str]]:
    normalized = normalize_company_work_mode(deepcopy(company), source=str(company.get("source") or ""))
    reasons: list[str] = []

    blocked_names = _normalized_set(preferences.get("avoided_companies") or preferences.get("blocked_companies") or preferences.get("_excluded_names"))
    blocked_domains = _normalized_set(preferences.get("blocked_domains") or preferences.get("_disliked_domains"))
    company_name = str(normalized.get("name") or "").strip().lower()
    company_domain = str(normalized.get("domain") or "").strip().lower()

    if company_name and company_name in blocked_names:
        reasons.append("blocked_company")
    if company_domain and company_domain in blocked_domains:
        reasons.append("blocked_domain")

    if _as_bool(preferences.get("sponsorship_required")) and normalized.get("sponsorship_available") is False:
        reasons.append("sponsorship_unavailable")

    original_positions = list(normalized.get("open_positions") or [])
    filtered_positions: list[dict[str, Any]] = []
    filtered_jobs: list[dict[str, Any]] = []
    for job in original_positions:
        keep, job_reasons = _job_passes_constraints(job, preferences)
        if keep:
            filtered_positions.append(job)
        else:
            filtered_jobs.append({
                "title": job.get("title", ""),
                "work_mode": job.get("work_mode", WorkMode.UNKNOWN.value),
                "reasons": job_reasons,
            })

    if original_positions:
        normalized["open_positions"] = filtered_positions
        normalized["preference_enforcement"] = {
            **dict(normalized.get("preference_enforcement") or {}),
            "filtered_jobs": filtered_jobs,
            "filtered_job_count": len(filtered_jobs),
        }
        normalized = normalize_company_work_mode(normalized, source=str(normalized.get("source") or ""))
        if not filtered_positions:
            reasons.append("no_jobs_remaining_after_hard_constraints")

    strict_remote = _strict_remote_enabled(preferences)
    if strict_remote and not original_positions:
        if normalized.get("work_mode") != WorkMode.REMOTE.value:
            reasons.append(f"work_mode={normalized.get('work_mode', WorkMode.UNKNOWN.value)}")
        elif float(normalized.get("remote_confidence") or 0.0) < STRICT_REMOTE_CONFIDENCE:
            reasons.append(f"remote_confidence<{STRICT_REMOTE_CONFIDENCE:.2f}")

    salary_min = preferences.get("salary_min")
    if salary_min is not None and not original_positions:
        _, company_max = _parse_salary_bounds((normalized.get("metadata") or {}).get("salary_range"))
        if company_max is not None and company_max < int(salary_min):
            reasons.append("salary_below_minimum")

    excluded_locations = _normalized_set(preferences.get("excluded_countries") or preferences.get("excluded_locations"))
    preferred_locations = _normalized_set(preferences.get("preferred_locations"))
    if excluded_locations and _location_matches_any(str(normalized.get("headquarters") or ""), excluded_locations):
        reasons.append("excluded_location")
    if preferred_locations and not strict_remote and not _as_bool(preferences.get("open_to_relocation")):
        headquarters = str(normalized.get("headquarters") or "")
        if headquarters and not _location_matches_any(headquarters, preferred_locations):
            reasons.append("outside_preferred_locations")

    normalized["preference_enforcement"] = {
        **dict(normalized.get("preference_enforcement") or {}),
        "hidden_by_preferences": bool(reasons),
        "reasons": reasons,
    }
    return not reasons, normalized, reasons


def apply_hard_constraints(companies: list[dict[str, Any]], user_preferences: dict[str, Any]) -> list[dict[str, Any]]:
    return apply_hard_constraints_with_diagnostics(companies, user_preferences).visible_companies


def apply_hard_constraints_with_diagnostics(
    companies: list[dict[str, Any]],
    user_preferences: dict[str, Any],
) -> HardConstraintResult:
    preferences = normalize_preference_payload(user_preferences)
    visible: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    counts_by_source: dict[str, dict[str, int]] = {}

    for company in companies:
        source = str(company.get("source") or "Unknown")
        source_counts = _ensure_source_counts(counts_by_source, source)
        keep, normalized, reasons = _apply_company_constraints(company, preferences)
        if keep:
            source_counts["visible"] += 1
            visible.append(normalized)
            continue

        source_counts["hard_constraints_filtered"] += 1
        mode = str(normalized.get("work_mode") or WorkMode.UNKNOWN.value)
        if mode == WorkMode.REMOTE.value:
            source_counts["remote_filtered"] += 1
        elif mode == WorkMode.HYBRID.value:
            source_counts["hybrid_filtered"] += 1
        elif mode == WorkMode.ONSITE.value:
            source_counts["onsite_filtered"] += 1
        else:
            source_counts["unknown_filtered"] += 1

        if any(reason in {"blocked_company", "blocked_domain"} for reason in reasons):
            source_counts["blocked_company_filtered"] += 1
        if "sponsorship_unavailable" in reasons:
            source_counts["visa_filtered"] += 1
        if "salary_below_minimum" in reasons:
            source_counts["salary_filtered"] += 1
        if any(reason in {"excluded_location", "outside_preferred_locations"} for reason in reasons):
            source_counts["location_filtered"] += 1

        hidden.append(_annotate_hidden_company(normalized, reasons))

    return HardConstraintResult(
        visible_companies=visible,
        hidden_companies=hidden,
        counts_by_source=counts_by_source,
    )


def partition_workspace_companies(
    companies: list[dict[str, Any]],
    user_preferences: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    archived: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for company in companies:
        workspace = company.get("workspace") or {}
        if workspace.get("archived"):
            archived.append(normalize_company_work_mode(deepcopy(company), source=str(company.get("source") or "")))
        else:
            active.append(company)

    result = apply_hard_constraints_with_diagnostics(active, user_preferences)
    return result.visible_companies, result.hidden_companies, archived