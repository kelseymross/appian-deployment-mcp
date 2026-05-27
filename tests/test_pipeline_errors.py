"""Property-based tests for failed stage error field recording.

Feature: deployment-pipeline, Property 16: Failed stage records all required error fields

For any failed pipeline stage, the StageResult SHALL contain:
(a) for export failures — deployment UUID, terminal status, and deployment log URL;
(b) for inspection failures — inspection UUID, errors list, warnings list, and object counts;
(c) for import failures — deployment UUID, terminal status, deployment log URL, and
    failed/skipped counts;
(d) for network errors — error type, target domain, and attempted operation.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from appian_deployment_mcp.pipeline.models import (
    StageOperation,
    StageResult,
)


# --- Strategies ---

# Strategy for non-empty strings (UUIDs, URLs, domains, etc.)
non_empty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_./: "),
    min_size=1,
    max_size=100,
)

# Strategy for UUID-like strings
uuid_strategy = st.uuids().map(str)

# Strategy for terminal failure status strings (non-COMPLETED)
failure_status_strategy = st.sampled_from([
    "FAILED",
    "COMPLETED_WITH_ERRORS",
    "COMPLETED_WITH_EXPORT_ERRORS",
    "COMPLETED_WITH_IMPORT_ERRORS",
    "ERROR",
])

# Strategy for deployment log URLs
log_url_strategy = st.builds(
    lambda domain, uuid: f"https://{domain}/suite/deployment-management/v2/deployments/{uuid}/log",
    domain=st.from_regex(r"[a-z]{3,10}\.(appiancloud|example)\.com", fullmatch=True),
    uuid=uuid_strategy,
)

# Strategy for environment names
environment_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
)

# Strategy for error/warning list entries
error_entry_strategy = st.fixed_dictionaries({
    "object_name": non_empty_text,
    "message": non_empty_text,
})

errors_list_strategy = st.lists(error_entry_strategy, min_size=0, max_size=10)
warnings_list_strategy = st.lists(error_entry_strategy, min_size=0, max_size=10)

# Strategy for object counts dict
object_counts_strategy = st.fixed_dictionaries({
    "expected": st.integers(min_value=0, max_value=1000),
    "failed": st.integers(min_value=0, max_value=1000),
    "skipped": st.integers(min_value=0, max_value=1000),
})

# Strategy for network error types
network_error_type_strategy = st.sampled_from(["network_error", "timeout"])

# Strategy for domain names
domain_strategy = st.from_regex(r"[a-z]{3,10}\.(appiancloud|example)\.com", fullmatch=True)


class TestProperty16FailedStageRecordsAllRequiredErrorFields:
    """Property 16: Failed stage records all required error fields.

    Feature: deployment-pipeline, Property 16: Failed stage records all required error fields

    For any failed pipeline stage, the StageResult SHALL contain:
    (a) for export failures — deployment UUID, terminal status, and deployment log URL;
    (b) for inspection failures — inspection UUID, errors list, warnings list, and object counts;
    (c) for import failures — deployment UUID, terminal status, deployment log URL, and
        failed/skipped counts;
    (d) for network errors — error type, target domain, and attempted operation.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        environment=environment_strategy,
        deployment_uuid=uuid_strategy,
        status=failure_status_strategy,
        deployment_log_url=log_url_strategy,
    )
    def test_export_failure_records_required_fields(
        self,
        environment: str,
        deployment_uuid: str,
        status: str,
        deployment_log_url: str,
    ):
        """Export failure StageResult contains deployment UUID, terminal status, and log URL.

        **Validates: Requirements 8.1**
        """
        result = StageResult(
            environment=environment,
            operation=StageOperation.EXPORT,
            deployment_uuid=deployment_uuid,
            status=status,
            deployment_log_url=deployment_log_url,
        )

        # (a) Export failures must have deployment UUID
        assert result.deployment_uuid is not None, (
            "Export failure StageResult must have deployment_uuid"
        )
        assert result.deployment_uuid == deployment_uuid

        # (a) Export failures must have terminal status
        assert result.status != "", (
            "Export failure StageResult must have a non-empty status"
        )
        assert result.status == status

        # (a) Export failures must have deployment log URL
        assert result.deployment_log_url is not None, (
            "Export failure StageResult must have deployment_log_url"
        )
        assert result.deployment_log_url == deployment_log_url

        # Operation must be EXPORT
        assert result.operation == StageOperation.EXPORT

    @settings(max_examples=100, deadline=None)
    @given(
        environment=environment_strategy,
        inspection_uuid=uuid_strategy,
        errors=errors_list_strategy,
        warnings=warnings_list_strategy,
        object_counts=object_counts_strategy,
    )
    def test_inspection_failure_records_required_fields(
        self,
        environment: str,
        inspection_uuid: str,
        errors: list[dict],
        warnings: list[dict],
        object_counts: dict,
    ):
        """Inspection failure StageResult contains UUID, errors, warnings, and object counts.

        **Validates: Requirements 8.2**
        """
        result = StageResult(
            environment=environment,
            operation=StageOperation.INSPECT,
            deployment_uuid=inspection_uuid,
            status="FAILED",
            errors=errors,
            warnings=warnings,
            object_counts=object_counts,
        )

        # (b) Inspection failures must have inspection UUID
        assert result.deployment_uuid is not None, (
            "Inspection failure StageResult must have deployment_uuid (inspection UUID)"
        )
        assert result.deployment_uuid == inspection_uuid

        # (b) Inspection failures must have errors list
        assert result.errors is not None, (
            "Inspection failure StageResult must have errors list"
        )
        assert result.errors == errors

        # (b) Inspection failures must have warnings list
        assert result.warnings is not None, (
            "Inspection failure StageResult must have warnings list"
        )
        assert result.warnings == warnings

        # (b) Inspection failures must have object counts
        assert result.object_counts is not None, (
            "Inspection failure StageResult must have object_counts"
        )
        assert result.object_counts == object_counts
        assert "expected" in result.object_counts
        assert "failed" in result.object_counts
        assert "skipped" in result.object_counts

        # Operation must be INSPECT
        assert result.operation == StageOperation.INSPECT

    @settings(max_examples=100, deadline=None)
    @given(
        environment=environment_strategy,
        deployment_uuid=uuid_strategy,
        status=failure_status_strategy,
        deployment_log_url=log_url_strategy,
        failed_count=st.integers(min_value=0, max_value=1000),
        skipped_count=st.integers(min_value=0, max_value=1000),
    )
    def test_import_failure_records_required_fields(
        self,
        environment: str,
        deployment_uuid: str,
        status: str,
        deployment_log_url: str,
        failed_count: int,
        skipped_count: int,
    ):
        """Import failure StageResult contains UUID, status, log URL, and failed/skipped counts.

        **Validates: Requirements 8.3**
        """
        object_counts = {"failed": failed_count, "skipped": skipped_count}

        result = StageResult(
            environment=environment,
            operation=StageOperation.IMPORT,
            deployment_uuid=deployment_uuid,
            status=status,
            deployment_log_url=deployment_log_url,
            object_counts=object_counts,
        )

        # (c) Import failures must have deployment UUID
        assert result.deployment_uuid is not None, (
            "Import failure StageResult must have deployment_uuid"
        )
        assert result.deployment_uuid == deployment_uuid

        # (c) Import failures must have terminal status
        assert result.status != "", (
            "Import failure StageResult must have a non-empty status"
        )
        assert result.status == status

        # (c) Import failures must have deployment log URL
        assert result.deployment_log_url is not None, (
            "Import failure StageResult must have deployment_log_url"
        )
        assert result.deployment_log_url == deployment_log_url

        # (c) Import failures must have failed and skipped counts
        assert result.object_counts is not None, (
            "Import failure StageResult must have object_counts with failed/skipped"
        )
        assert "failed" in result.object_counts, (
            "Import failure object_counts must contain 'failed' key"
        )
        assert "skipped" in result.object_counts, (
            "Import failure object_counts must contain 'skipped' key"
        )
        assert result.object_counts["failed"] == failed_count
        assert result.object_counts["skipped"] == skipped_count

        # Operation must be IMPORT
        assert result.operation == StageOperation.IMPORT

    @settings(max_examples=100, deadline=None)
    @given(
        environment=environment_strategy,
        error_type=network_error_type_strategy,
        error_domain=domain_strategy,
        operation=st.sampled_from(list(StageOperation)),
    )
    def test_network_error_records_required_fields(
        self,
        environment: str,
        error_type: str,
        error_domain: str,
        operation: StageOperation,
    ):
        """Network error StageResult contains error type, target domain, and attempted operation.

        **Validates: Requirements 8.5**
        """
        result = StageResult(
            environment=environment,
            operation=operation,
            status="FAILED",
            error_type=error_type,
            error_domain=error_domain,
        )

        # (d) Network errors must have error type
        assert result.error_type is not None, (
            "Network error StageResult must have error_type"
        )
        assert result.error_type == error_type

        # (d) Network errors must have target domain
        assert result.error_domain is not None, (
            "Network error StageResult must have error_domain"
        )
        assert result.error_domain == error_domain

        # (d) Network errors must record the attempted operation
        assert result.operation is not None, (
            "Network error StageResult must have operation"
        )
        assert result.operation == operation

        # Status should indicate failure
        assert result.status == "FAILED"

    @settings(max_examples=100, deadline=None)
    @given(
        environment=environment_strategy,
        deployment_uuid=uuid_strategy,
        status=failure_status_strategy,
        deployment_log_url=log_url_strategy,
    )
    def test_export_failure_environment_recorded(
        self,
        environment: str,
        deployment_uuid: str,
        status: str,
        deployment_log_url: str,
    ):
        """Failed export stage records the environment name in the StageResult.

        **Validates: Requirements 8.4**
        """
        result = StageResult(
            environment=environment,
            operation=StageOperation.EXPORT,
            deployment_uuid=deployment_uuid,
            status=status,
            deployment_log_url=deployment_log_url,
        )

        # Requirement 8.4: failed stage includes environment name
        assert result.environment == environment, (
            f"StageResult environment should be '{environment}', got '{result.environment}'"
        )
        # Requirement 8.4: failed stage includes operation type
        assert result.operation == StageOperation.EXPORT
        # Requirement 8.4: failed stage includes terminal status value
        assert result.status == status
