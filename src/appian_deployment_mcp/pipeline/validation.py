"""Validation functions for pipeline definitions and run parameters."""

from __future__ import annotations

from typing import Any


def validate_pipeline_stages(
    stages: list[str], environments: dict[str, Any]
) -> dict | None:
    """Validate that all stage names are configured environments with no duplicates.

    Args:
        stages: Ordered list of environment names for the pipeline.
        environments: Dict of configured environments keyed by name.

    Returns:
        None if valid, or a dict with an "error" key containing a message
        that lists all invalid environment names and/or all duplicate names.
    """
    errors: list[str] = []

    # Check for invalid environment names
    invalid_names = [name for name in stages if name not in environments]
    if invalid_names:
        errors.append(
            f"Invalid environment names: {', '.join(invalid_names)}"
        )

    # Check for duplicates
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in stages:
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    if duplicates:
        errors.append(
            f"Duplicate environment names: {', '.join(sorted(duplicates))}"
        )

    if errors:
        return {"error": "; ".join(errors)}

    return None


def validate_run_params(
    uuids: list[str],
    export_type: str,
    stages: list[str],
    approval_environments: list[str] | None,
    min_stages: int = 1,
) -> dict | None:
    """Validate parameters for a pipeline run.

    Args:
        uuids: List of UUIDs to export.
        export_type: Must be "package" or "application".
        stages: Ordered list of environment names for the run.
        approval_environments: Optional list of environments requiring approval.
            Must be a subset of stages.
        min_stages: Minimum number of stages required (default 1).
            Use 2 for ad-hoc pipelines.

    Returns:
        None if valid, or a dict with an "error" key containing a message.
    """
    errors: list[str] = []

    # Validate export_type
    if export_type not in ("package", "application"):
        errors.append(
            f"export_type must be 'package' or 'application', got '{export_type}'"
        )

    # Validate uuids count
    if not uuids:
        errors.append("uuids must contain at least 1 entry")
    elif len(uuids) > 100:
        errors.append(
            f"uuids must contain at most 100 entries, got {len(uuids)}"
        )

    # Validate stages count
    if len(stages) < min_stages:
        errors.append(
            f"stages must contain at least {min_stages} entries, got {len(stages)}"
        )
    elif len(stages) > 20:
        errors.append(
            f"stages must contain at most 20 entries, got {len(stages)}"
        )

    # Validate approval_environments is subset of stages
    if approval_environments:
        stage_set = set(stages)
        invalid_approvals = [
            env for env in approval_environments if env not in stage_set
        ]
        if invalid_approvals:
            errors.append(
                f"approval_environments contains names not in stages: "
                f"{', '.join(invalid_approvals)}"
            )

    if errors:
        return {"error": "; ".join(errors)}

    return None
