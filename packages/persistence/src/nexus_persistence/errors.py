"""Stable persistence and retrieval errors (no SQL leakage)."""

from __future__ import annotations


class PersistenceError(Exception):
    code: str = "PROJECT_PERSISTENCE_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class ProjectNotFoundError(PersistenceError):
    code = "PROJECT_NOT_FOUND"


class ArtifactNotFoundError(PersistenceError):
    code = "ARTIFACT_NOT_FOUND"


class ArtifactVersionNotFoundError(PersistenceError):
    code = "ARTIFACT_VERSION_NOT_FOUND"


class ProjectPersistenceError(PersistenceError):
    code = "PROJECT_PERSISTENCE_FAILED"


class ProjectRetrievalError(PersistenceError):
    code = "PROJECT_RETRIEVAL_FAILED"


class WorkspaceNotFoundError(PersistenceError):
    code = "WORKSPACE_NOT_FOUND"


class SnapshotNotFoundError(PersistenceError):
    code = "SNAPSHOT_NOT_FOUND"


class ProposalNotFoundError(PersistenceError):
    code = "PROPOSAL_NOT_FOUND"


class ExecutionNotFoundError(PersistenceError):
    code = "EXECUTION_NOT_FOUND"


class SnapshotImmutableError(PersistenceError):
    code = "SNAPSHOT_IMMUTABLE"


class LedgerImmutableError(PersistenceError):
    code = "LEDGER_IMMUTABLE"


class ArtifactVersionConflictError(PersistenceError):
    code = "ARTIFACT_VERSION_CONFLICT"


class ProjectStateConflictError(PersistenceError):
    code = "PROJECT_STATE_CONFLICT"


class FirmwarePatchNotFoundError(PersistenceError):
    code = "FIRMWARE_PATCH_NOT_FOUND"
