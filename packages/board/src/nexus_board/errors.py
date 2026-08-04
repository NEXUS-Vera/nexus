"""Stable board/kernel error codes."""

from __future__ import annotations


class BoardError(Exception):
    code: str = "BOARD_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class ArtifactVersionConflictError(BoardError):
    code = "ARTIFACT_VERSION_CONFLICT"


class ProjectStateConflictError(BoardError):
    code = "PROJECT_STATE_CONFLICT"


class StaleExecutionResultError(BoardError):
    code = "STALE_EXECUTION_RESULT"


class GovernanceRejectedError(BoardError):
    code = "GOVERNANCE_REJECTED"


class ApprovalRequiredError(BoardError):
    code = "APPROVAL_REQUIRED"


class RegistryError(BoardError):
    code = "REGISTRY_ERROR"


class DuplicateRegistrationError(RegistryError):
    code = "DUPLICATE_REGISTRATION"


class WorkspaceNotFoundError(BoardError):
    code = "WORKSPACE_NOT_FOUND"


class ProposalNotFoundError(BoardError):
    code = "PROPOSAL_NOT_FOUND"


class SnapshotNotFoundError(BoardError):
    code = "SNAPSHOT_NOT_FOUND"


class SnapshotImmutableError(BoardError):
    code = "SNAPSHOT_IMMUTABLE"


class LedgerImmutableError(BoardError):
    code = "LEDGER_IMMUTABLE"


class CommandValidationError(BoardError):
    code = "COMMAND_VALIDATION_FAILED"


class GraphBoundExceededError(BoardError):
    code = "GRAPH_BOUND_EXCEEDED"
