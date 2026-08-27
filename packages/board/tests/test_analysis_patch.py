"""Phase 16C analysis patch proposal tests."""

from __future__ import annotations

import copy

from typing import Any

import pytest

from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.analysis.patch import (
    ANALYSIS_PATCH_GENERATOR_ID,
    validate_analysis_patch_proposal,
)
from nexus_board.errors import (
    AnalysisPatchStaleError,
    AnalysisPatchValidationError,
)
from nexus_persistence.file_store.hashing import blob_digest


def _setup_scaffolded_analysis(kernel: Any, project_id: str, user: dict[str, Any] | None = None) -> dict[str, Any]:
    from nexus_board.analysis.scaffold import (
        ANALYSIS_PYTHON_V1_PROFILE_ID,
    )

    user = user or actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        profile_id=ANALYSIS_PYTHON_V1_PROFILE_ID,
    )
    return dict(binding)


def test_patch_validation_accepts_valid_operations() -> None:
    base_hash = blob_digest(b"old")
    new_hash = blob_digest(b"new")
    proposal = {
        "schemaVersion": "1.0.0",
        "proposalId": "anpatch_test000000000001",
        "projectId": "proj_test000000000001",
        "artifactId": "art_test000000000001",
        "artifactType": "analysis",
        "workspaceId": "ws_test000000000001",
        "baseSnapshotId": "snap_test000000000001",
        "requestedChange": "test change",
        "generatorId": ANALYSIS_PATCH_GENERATOR_ID,
        "generatorVersion": "1.0.0",
        "inputArtifactReferences": [],
        "operations": [
            {
                "operationType": "create-file",
                "path": "data/new.json",
                "content": "new",
                "contentHash": new_hash,
            },
            {
                "operationType": "replace-file",
                "path": "analysis.py",
                "expectedBaseHash": base_hash,
                "content": "new",
                "contentHash": new_hash,
            },
            {
                "operationType": "delete-file",
                "path": "README.md",
                "expectedBaseHash": base_hash,
            },
        ],
        "status": "proposed",
        "requestedBy": actor(),
        "requestedAt": "2026-08-11T00:00:00Z",
    }
    base_snapshot = {
        "snapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "content": {
            "kind": "filesystem",
            "filesystemManifest": {
                "manifestDigest": "sha256:" + "0" * 64,
                "entries": [
                    {
                        "path": "analysis.py",
                        "contentHash": base_hash,
                        "contentReference": "cas:" + "0" * 64,
                        "sizeBytes": 3,
                        "origin": "GENERATED",
                        "writePolicy": "REGENERATION_MANAGED",
                        "modifiedByUser": False,
                    },
                    {
                        "path": "README.md",
                        "contentHash": base_hash,
                        "contentReference": "cas:" + "1" * 64,
                        "sizeBytes": 3,
                        "origin": "USER",
                        "writePolicy": "USER_EDITABLE",
                        "modifiedByUser": True,
                    },
                ],
            },
        },
    }

    # WorkspaceFilesystemLimits is enforced by the filesystem service in real calls;
    # in this unit test we use a permissive shim object.
    class _Limits:
        max_file_bytes = 1_000_000

    validate_analysis_patch_proposal(proposal, base_snapshot=base_snapshot, limits=_Limits())  # type: ignore[arg-type]


def test_patch_validation_rejects_invalid_paths_and_duplicates() -> None:
    base_snapshot = {
        "snapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "content": {"kind": "filesystem", "filesystemManifest": {"entries": []}},
    }
    dup = {
        "artifactType": "analysis",
        "baseSnapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "operations": [
            {
                "operationType": "create-file",
                "path": "data/a.txt",
                "content": "x",
                "contentHash": blob_digest(b"x"),
            },
            {
                "operationType": "create-file",
                "path": "data/a.txt",
                "content": "y",
                "contentHash": blob_digest(b"y"),
            },
        ],
    }
    class _Limits:
        max_file_bytes = 1_000_000

    with pytest.raises(AnalysisPatchValidationError):
        validate_analysis_patch_proposal(dup, base_snapshot=base_snapshot, limits=_Limits())  # type: ignore[arg-type]

    bad_path = copy.deepcopy(dup)
    bad_path["operations"] = [
        {
            "operationType": "create-file",
            "path": "../evil.txt",
            "content": "x",
            "contentHash": blob_digest(b"x"),
        }
    ]
    with pytest.raises(AnalysisPatchValidationError):
        validate_analysis_patch_proposal(bad_path, base_snapshot=base_snapshot, limits=_Limits())  # type: ignore[arg-type]


def test_propose_records_immutable_base_snapshot_and_context() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_analysis(kernel, project_id, user=user)
    before_files = kernel_store.list_workspace_files(binding["workspaceId"])
    before_hashes = {item["path"]: item["contentHash"] for item in before_files}

    result = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Add a marker about 9600 baud (fixture).",
    )
    proposal = result["proposal"]
    assert proposal["status"] == "proposed"
    assert proposal["baseSnapshotId"].startswith("snap_")
    assert len(proposal["inputArtifactReferences"]) == 0
    assert proposal["generatorId"] == ANALYSIS_PATCH_GENERATOR_ID

    after_files = kernel_store.list_workspace_files(binding["workspaceId"])
    after_hashes = {item["path"]: item["contentHash"] for item in after_files}
    assert after_hashes == before_hashes


def test_apply_replace_patch_updates_workspace() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_analysis(kernel, project_id, user=user)

    proposed = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Requested change: hello world",
    )
    proposal = proposed["proposal"]
    draft = kernel_store.get_draft(binding["workspaceId"])

    applied = kernel.workspace_runtime.apply_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert applied["status"] == "applied"
    record = kernel_store.get_workspace_file(binding["workspaceId"], "README.md")
    assert record is not None
    assert "Requested change" in kernel.filesystem.read_file(binding["workspaceId"], "README.md")["content"].decode("utf-8")
    assert record["contentHash"] == next(op for op in proposal["operations"] if op["path"] == "README.md")["contentHash"]


def test_stale_patch_rejected_after_manual_edit() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_analysis(kernel, project_id, user=user)

    proposed = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Requested change: hello world",
    )
    proposal = proposed["proposal"]
    draft = kernel_store.get_draft(binding["workspaceId"])

    # Mutate workspace after proposing; apply should now be stale.
    manual = kernel.filesystem.read_file(binding["workspaceId"], "README.md")
    manual_text = manual["content"].decode("utf-8") + "\n# manual edit\n"
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="README.md",
        content=manual_text.encode("utf-8"),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    draft = kernel_store.get_draft(binding["workspaceId"])
    with pytest.raises(AnalysisPatchStaleError):
        kernel.workspace_runtime.apply_analysis_patch(
            project_id=project_id,
            artifact_type="analysis",
            proposal_id=proposal["proposalId"],
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )

