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


def _setup_scaffolded_analysis(
    kernel: Any, project_id: str, user: dict[str, Any] | None = None
) -> dict[str, Any]:
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
    requirement = _ps.get_artifact(project_id, "requirement-set")
    assert proposal["inputArtifactReferences"] == [
        {key: requirement[key] for key in ("artifactType", "artifactId", "artifactVersion")}
    ]
    stored = kernel_store.get_firmware_patch_proposal(proposal["proposalId"])
    assert stored["inputArtifactReferences"] == proposal["inputArtifactReferences"]
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
    assert "Requested change" in kernel.filesystem.read_file(binding["workspaceId"], "README.md")[
        "content"
    ].decode("utf-8")
    assert (
        record["contentHash"]
        == next(op for op in proposal["operations"] if op["path"] == "README.md")["contentHash"]
    )


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


def test_analysis_patch_survives_sqlite_restart(tmp_path: Any) -> None:
    """The PR3 proposal store must persist analysis decisions across restarts."""
    from helpers import minimal_package
    from nexus_board.kernel import build_project_kernel
    from nexus_persistence import build_stores

    database_url = f"sqlite:///{tmp_path / 'analysis.sqlite'}"
    ps, ks = build_stores(backend="sqlite", database_url=database_url)
    package = minimal_package()
    ps.save_initialization_package(package)
    project_id = package["project"]["projectId"]
    kernel = build_project_kernel(ks, project_store=ps, auto_start_scheduler=False)
    user = actor()
    binding = _setup_scaffolded_analysis(kernel, project_id, user)
    proposal = kernel.workspace_runtime.propose_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        requested_change="Document the input format",
    )["proposal"]

    ps2, ks2 = build_stores(backend="sqlite", database_url=database_url)
    restarted = build_project_kernel(ks2, project_store=ps2, auto_start_scheduler=False)
    result = restarted.workspace_runtime.discard_analysis_patch(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        proposal_id=proposal["proposalId"],
    )
    assert result["proposal"]["status"] == "discarded"
    assert (
        ks2.get_firmware_patch_proposal(proposal["proposalId"])["workspaceId"]
        == binding["workspaceId"]
    )


def test_analysis_patch_rejects_missing_and_firmware_proposals() -> None:
    from nexus_board.errors import AnalysisPatchNotFoundError

    kernel, _ps, ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor()
    _setup_scaffolded_analysis(kernel, project_id, user)
    ks.create_firmware_patch_proposal({"proposalId": "fwpatch_other", "artifactType": "firmware"})
    for proposal_id in ["anpatch_missing", "fwpatch_other"]:
        with pytest.raises(AnalysisPatchNotFoundError):
            kernel.workspace_runtime.discard_analysis_patch(
                project_id=project_id,
                artifact_type="analysis",
                actor=user,
                proposal_id=proposal_id,
            )
