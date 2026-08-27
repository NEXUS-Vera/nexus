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


class DraftEditLeaseHeldError(BoardError):
    code = "DRAFT_EDIT_LEASE_HELD"


class DraftEditLeaseRequiredError(BoardError):
    code = "DRAFT_EDIT_LEASE_REQUIRED"


class GraphBoundExceededError(BoardError):
    code = "GRAPH_BOUND_EXCEEDED"


class WorkspacePathError(BoardError):
    code = "WORKSPACE_PATH_INVALID"


class WorkspaceQuotaExceededError(BoardError):
    code = "WORKSPACE_QUOTA_EXCEEDED"


class WorkspaceFileNotFoundError(BoardError):
    code = "WORKSPACE_FILE_NOT_FOUND"


class WorkspaceWritePolicyError(BoardError):
    code = "WORKSPACE_WRITE_POLICY_DENIED"


class WorkspaceNotFilesystemError(BoardError):
    code = "WORKSPACE_NOT_FILESYSTEM"


class WorkspaceScaffoldConflictError(BoardError):
    """Scaffold target path exists and does not match the deterministic template."""

    code = "WORKSPACE_SCAFFOLD_CONFLICT"


class FirmwarePatchValidationError(BoardError):
    code = "FIRMWARE_PATCH_VALIDATION_FAILED"


class FirmwarePatchStaleError(BoardError):
    code = "FIRMWARE_PATCH_STALE"


class FirmwarePatchNotFoundError(BoardError):
    code = "FIRMWARE_PATCH_NOT_FOUND"


class FirmwarePatchGenerationError(BoardError):
    code = "FIRMWARE_PATCH_GENERATION_FAILED"


class FirmwareToolchainValidationError(BoardError):
    code = "FIRMWARE_TOOLCHAIN_VALIDATION_FAILED"


class FirmwareTestNotConfiguredError(BoardError):
    code = "FIRMWARE_TEST_NOT_CONFIGURED"


class AnalysisPatchValidationError(BoardError):
    code = "ANALYSIS_PATCH_VALIDATION_FAILED"


class AnalysisPatchStaleError(BoardError):
    code = "ANALYSIS_PATCH_STALE"


class AnalysisPatchNotFoundError(BoardError):
    code = "ANALYSIS_PATCH_NOT_FOUND"


class AnalysisPatchGenerationError(BoardError):
    code = "ANALYSIS_PATCH_GENERATION_FAILED"
