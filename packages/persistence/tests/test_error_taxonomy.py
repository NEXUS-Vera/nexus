"""Every persistence error is classified by a marker base, with stable codes."""

from __future__ import annotations

import inspect

import nexus_persistence
from nexus_persistence import errors

NOT_FOUND = {
    "ProjectNotFoundError": "PROJECT_NOT_FOUND",
    "ArtifactNotFoundError": "ARTIFACT_NOT_FOUND",
    "ArtifactVersionNotFoundError": "ARTIFACT_VERSION_NOT_FOUND",
    "WorkspaceNotFoundError": "WORKSPACE_NOT_FOUND",
    "SnapshotNotFoundError": "SNAPSHOT_NOT_FOUND",
    "ProposalNotFoundError": "PROPOSAL_NOT_FOUND",
    "ExecutionNotFoundError": "EXECUTION_NOT_FOUND",
    "FirmwarePatchNotFoundError": "FIRMWARE_PATCH_NOT_FOUND",
}
CONFLICT = {
    "SnapshotImmutableError": "SNAPSHOT_IMMUTABLE",
    "LedgerImmutableError": "LEDGER_IMMUTABLE",
    "ArtifactVersionConflictError": "ARTIFACT_VERSION_CONFLICT",
    "ProjectStateConflictError": "PROJECT_STATE_CONFLICT",
}
SERVER_SIDE = {
    "ProjectPersistenceError": "PROJECT_PERSISTENCE_FAILED",
    "ProjectRetrievalError": "PROJECT_RETRIEVAL_FAILED",
}
MARKERS = {"PersistenceError", "PersistenceNotFoundError", "PersistenceConflictError"}


def _error_classes() -> dict[str, type[errors.PersistenceError]]:
    return {
        name: obj
        for name, obj in inspect.getmembers(errors, inspect.isclass)
        if issubclass(obj, errors.PersistenceError) and obj.__module__ == errors.__name__
    }


def test_every_error_class_is_classified() -> None:
    known = set(NOT_FOUND) | set(CONFLICT) | set(SERVER_SIDE) | MARKERS
    assert set(_error_classes()) == known, (
        "classify new persistence errors under PersistenceNotFoundError or "
        "PersistenceConflictError (or list them as server-side here)"
    )


def test_marker_bases_and_codes_are_stable() -> None:
    classes = _error_classes()
    for name, code in NOT_FOUND.items():
        assert issubclass(classes[name], errors.PersistenceNotFoundError), name
        assert not issubclass(classes[name], errors.PersistenceConflictError), name
        assert classes[name].code == code
    for name, code in CONFLICT.items():
        assert issubclass(classes[name], errors.PersistenceConflictError), name
        assert not issubclass(classes[name], errors.PersistenceNotFoundError), name
        assert classes[name].code == code
    for name, code in SERVER_SIDE.items():
        assert not issubclass(
            classes[name], (errors.PersistenceNotFoundError, errors.PersistenceConflictError)
        ), name
        assert classes[name].code == code


def test_package_root_exports_every_error_class() -> None:
    for name, cls in _error_classes().items():
        assert getattr(nexus_persistence, name) is cls, name
        assert name in nexus_persistence.__all__, name


def test_marker_bases_have_their_own_default_codes() -> None:
    assert errors.PersistenceNotFoundError("x").code == "PERSISTENCE_NOT_FOUND"
    assert errors.PersistenceConflictError("x").code == "PERSISTENCE_CONFLICT"
    assert errors.PersistenceError("x").code == "PROJECT_PERSISTENCE_FAILED"
    assert errors.PersistenceNotFoundError("x", code="CUSTOM").code == "CUSTOM"
