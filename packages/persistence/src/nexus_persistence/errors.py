"""Stable persistence and retrieval errors (no SQL leakage)."""

from __future__ import annotations


class PersistenceError(Exception):
    code: str = "PROJECT_PERSISTENCE_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class PersistenceNotFoundError(PersistenceError):
    """Marker base: the requested record does not exist (HTTP 404 at the API)."""

    code = "PERSISTENCE_NOT_FOUND"


class PersistenceConflictError(PersistenceError):
    """Marker base: the write conflicts with stored state (HTTP 409 at the API)."""

    code = "PERSISTENCE_CONFLICT"


class ProjectNotFoundError(PersistenceNotFoundError):
    code = "PROJECT_NOT_FOUND"


class ArtifactNotFoundError(PersistenceNotFoundError):
    code = "ARTIFACT_NOT_FOUND"


class ArtifactVersionNotFoundError(PersistenceNotFoundError):
    code = "ARTIFACT_VERSION_NOT_FOUND"


class ProjectPersistenceError(PersistenceError):
    code = "PROJECT_PERSISTENCE_FAILED"


class ProjectRetrievalError(PersistenceError):
    code = "PROJECT_RETRIEVAL_FAILED"


class WorkspaceNotFoundError(PersistenceNotFoundError):
    code = "WORKSPACE_NOT_FOUND"


class SnapshotNotFoundError(PersistenceNotFoundError):
    code = "SNAPSHOT_NOT_FOUND"


class ProposalNotFoundError(PersistenceNotFoundError):
    code = "PROPOSAL_NOT_FOUND"


class ExecutionNotFoundError(PersistenceNotFoundError):
    code = "EXECUTION_NOT_FOUND"


class SnapshotImmutableError(PersistenceConflictError):
    code = "SNAPSHOT_IMMUTABLE"


class LedgerImmutableError(PersistenceConflictError):
    code = "LEDGER_IMMUTABLE"


class ArtifactVersionConflictError(PersistenceConflictError):
    code = "ARTIFACT_VERSION_CONFLICT"


class ProjectStateConflictError(PersistenceConflictError):
    code = "PROJECT_STATE_CONFLICT"


class FirmwarePatchNotFoundError(PersistenceNotFoundError):
    code = "FIRMWARE_PATCH_NOT_FOUND"
