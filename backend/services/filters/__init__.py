"""Central preference and hard-constraint enforcement."""

from .hard_constraints import (
    apply_hard_constraints,
    apply_hard_constraints_with_diagnostics,
    normalize_preference_payload,
    partition_workspace_companies,
)

__all__ = [
    "apply_hard_constraints",
    "apply_hard_constraints_with_diagnostics",
    "normalize_preference_payload",
    "partition_workspace_companies",
]