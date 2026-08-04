"""Optimistic concurrency checks."""

from __future__ import annotations

from dataclasses import dataclass

from nexus_board.errors import ArtifactVersionConflictError, ProjectStateConflictError


@dataclass(frozen=True)
class ConcurrencyCheckResult:
    ok: bool
    code: str | None = None
    message: str | None = None


def check_artifact_and_project_versions(
    *,
    expected_artifact_version: int,
    actual_artifact_version: int,
    expected_project_state_version: int,
    actual_project_state_version: int,
    raise_on_conflict: bool = True,
) -> ConcurrencyCheckResult:
    if expected_project_state_version != actual_project_state_version:
        result = ConcurrencyCheckResult(
            ok=False,
            code="PROJECT_STATE_CONFLICT",
            message=(
                f"Project state version conflict: expected "
                f"{expected_project_state_version}, actual {actual_project_state_version}"
            ),
        )
        if raise_on_conflict:
            raise ProjectStateConflictError(result.message or "Project state conflict")
        return result
    if expected_artifact_version != actual_artifact_version:
        result = ConcurrencyCheckResult(
            ok=False,
            code="ARTIFACT_VERSION_CONFLICT",
            message=(
                f"Artifact version conflict: expected "
                f"{expected_artifact_version}, actual {actual_artifact_version}"
            ),
        )
        if raise_on_conflict:
            raise ArtifactVersionConflictError(result.message or "Artifact version conflict")
        return result
    return ConcurrencyCheckResult(ok=True)


def check_draft_version(
    *,
    expected_draft_version: int,
    actual_draft_version: int,
    raise_on_conflict: bool = True,
) -> ConcurrencyCheckResult:
    if expected_draft_version != actual_draft_version:
        result = ConcurrencyCheckResult(
            ok=False,
            code="ARTIFACT_VERSION_CONFLICT",
            message=(
                f"Draft version conflict: expected "
                f"{expected_draft_version}, actual {actual_draft_version}"
            ),
        )
        if raise_on_conflict:
            raise ArtifactVersionConflictError(result.message or "Draft version conflict")
        return result
    return ConcurrencyCheckResult(ok=True)
