"""Phase 15C firmware patch proposal tests."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import (
    FirmwarePatchNotFoundError,
    FirmwarePatchStaleError,
    FirmwarePatchValidationError,
)
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_board.firmware.patch import (
    FIRMWARE_PATCH_GENERATOR_ID,
    assemble_firmware_generation_context,
    generate_firmware_patch_operations,
    validate_firmware_patch_proposal,
)
from nexus_board.firmware.scaffold import MAIN_CPP_PATH, PLATFORMIO_INI_PATH
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from nexus_persistence.file_store.hashing import blob_digest


def _setup_scaffolded_firmware(
    kernel: Any, project_id: str, user: dict[str, Any] | None = None
) -> dict[str, Any]:
    user = user or actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    return dict(binding)


def test_patch_validation_accepts_valid_operations() -> None:
    base_hash = blob_digest(b"old")
    new_hash = blob_digest(b"new")
    proposal = {
        "schemaVersion": "1.0.0",
        "proposalId": "fwpatch_test000000000001",
        "projectId": "proj_test000000000001",
        "artifactId": "art_test000000000001",
        "artifactType": "firmware",
        "workspaceId": "ws_test000000000001",
        "baseSnapshotId": "snap_test000000000001",
        "requestedChange": "test",
        "generatorId": FIRMWARE_PATCH_GENERATOR_ID,
        "generatorVersion": "1.0.0",
        "inputArtifactReferences": [],
        "operations": [
            {
                "operationType": "create-file",
                "path": "src/new.cpp",
                "content": "new",
                "contentHash": new_hash,
            },
            {
                "operationType": "replace-file",
                "path": PLATFORMIO_INI_PATH,
                "expectedBaseHash": base_hash,
                "content": "new",
                "contentHash": new_hash,
            },
            {
                "operationType": "delete-file",
                "path": "old.txt",
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
                        "path": PLATFORMIO_INI_PATH,
                        "contentHash": base_hash,
                        "contentReference": "cas:" + "0" * 64,
                        "sizeBytes": 3,
                        "origin": "GENERATED",
                        "writePolicy": "REGENERATION_MANAGED",
                        "modifiedByUser": False,
                    },
                    {
                        "path": "old.txt",
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
    validate_firmware_patch_proposal(proposal, base_snapshot=base_snapshot)


def test_patch_validation_rejects_invalid_paths_and_duplicates() -> None:
    base_snapshot = {
        "snapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "content": {"kind": "filesystem", "filesystemManifest": {"entries": []}},
    }
    proposal = {
        "artifactType": "firmware",
        "baseSnapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "operations": [
            {
                "operationType": "create-file",
                "path": "../evil.txt",
                "content": "x",
                "contentHash": blob_digest(b"x"),
            }
        ],
    }
    with pytest.raises(FirmwarePatchValidationError):
        validate_firmware_patch_proposal(proposal, base_snapshot=base_snapshot)

    dup = {
        "artifactType": "firmware",
        "baseSnapshotId": "snap_test000000000001",
        "workspaceId": "ws_test000000000001",
        "projectId": "proj_test000000000001",
        "operations": [
            {
                "operationType": "create-file",
                "path": "a.txt",
                "content": "x",
                "contentHash": blob_digest(b"x"),
            },
            {
                "operationType": "create-file",
                "path": "a.txt",
                "content": "y",
                "contentHash": blob_digest(b"y"),
            },
        ],
    }
    with pytest.raises(FirmwarePatchValidationError):
        validate_firmware_patch_proposal(dup, base_snapshot=base_snapshot)


def test_propose_records_immutable_base_snapshot_and_context() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user=user)
    before_files = kernel_store.list_workspace_files(binding["workspaceId"])
    before_hashes = {item["path"]: item["contentHash"] for item in before_files}

    result = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    proposal = result["proposal"]
    assert proposal["status"] == "proposed"
    assert proposal["baseSnapshotId"].startswith("snap_")
    assert len(proposal["inputArtifactReferences"]) >= 1
    assert proposal["generatorId"] == FIRMWARE_PATCH_GENERATOR_ID
    assert any(op["path"] == PLATFORMIO_INI_PATH for op in proposal["operations"])

    after_files = kernel_store.list_workspace_files(binding["workspaceId"])
    after_hashes = {item["path"]: item["contentHash"] for item in after_files}
    assert after_hashes == before_hashes


def test_apply_replace_patch_updates_workspace() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user=user)
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    proposal = proposed["proposal"]
    draft = kernel_store.get_draft(binding["workspaceId"])
    applied = kernel.workspace_runtime.apply_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        proposal_id=proposal["proposalId"],
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert applied["status"] == "applied"
    assert applied["applySemantics"] == "sequential-non-atomic"
    record = kernel_store.get_workspace_file(binding["workspaceId"], PLATFORMIO_INI_PATH)
    assert record is not None
    replace_op = next(op for op in proposal["operations"] if op["path"] == PLATFORMIO_INI_PATH)
    assert record["contentHash"] == replace_op["contentHash"]
    assert "9600" in kernel.filesystem.read_file(binding["workspaceId"], PLATFORMIO_INI_PATH)[
        "content"
    ].decode("utf-8")


def test_stale_patch_rejected_after_manual_edit() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user=user)
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    proposal = proposed["proposal"]
    draft = kernel_store.get_draft(binding["workspaceId"])
    manual = kernel.filesystem.read_file(binding["workspaceId"], PLATFORMIO_INI_PATH)
    manual_text = manual["content"].decode("utf-8") + "# manual edit\n"
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path=PLATFORMIO_INI_PATH,
        content=manual_text.encode("utf-8"),
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    draft = kernel_store.get_draft(binding["workspaceId"])
    with pytest.raises(FirmwarePatchStaleError):
        kernel.workspace_runtime.apply_firmware_patch(
            project_id=project_id,
            artifact_type="firmware",
            proposal_id=proposal["proposalId"],
            actor=user,
            expected_draft_version=int(draft["draftVersion"]),
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )
    current = kernel.filesystem.read_file(binding["workspaceId"], PLATFORMIO_INI_PATH)
    assert current["content"].decode("utf-8") == manual_text


def test_discard_leaves_workspace_unchanged() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user=user)
    before = copy.deepcopy(kernel_store.list_workspace_files(binding["workspaceId"]))
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    discarded = kernel.workspace_runtime.discard_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        proposal_id=proposed["proposal"]["proposalId"],
        actor=user,
    )
    assert discarded["status"] == "discarded"
    after = kernel_store.list_workspace_files(binding["workspaceId"])
    assert after == before


def test_wrong_base_snapshot_workspace_rejected() -> None:
    kernel, _ps, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user=user)
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Change serial baud to 9600.",
    )
    proposal = dict(proposed["proposal"])
    proposal["baseSnapshotId"] = "snap_other000000000001"
    with pytest.raises(FirmwarePatchValidationError):
        validate_firmware_patch_proposal(
            proposal,
            base_snapshot={
                "snapshotId": "snap_other000000000001",
                "workspaceId": "ws_other000000000001",
                "projectId": project_id,
                "content": {"kind": "filesystem", "filesystemManifest": {"entries": []}},
            },
        )


def test_generation_context_includes_artifact_versions() -> None:
    kernel, project_store, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user=user)
    snapshot = kernel.workspace_runtime.create_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason="test",
    )
    base_snapshot = kernel.kernel_store.get_snapshot(snapshot["snapshotId"])
    context = assemble_firmware_generation_context(
        project_store=project_store,
        project_id=project_id,
        base_snapshot=base_snapshot,
        requested_change="test",
        file_store=kernel.filesystem.file_store,
    )
    assert context["inputArtifactReferences"]
    assert any(ref["artifactType"] == "project-brief" for ref in context["inputArtifactReferences"])
    assert MAIN_CPP_PATH in context["fileContents"]


def test_apply_unknown_proposal_not_found() -> None:
    kernel, _ps, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user=user)
    with pytest.raises(FirmwarePatchNotFoundError):
        kernel.workspace_runtime.apply_firmware_patch(
            project_id=project_id,
            artifact_type="firmware",
            proposal_id="fwpatch_missing00000000001",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )


def test_deterministic_generator_mpu6050() -> None:
    kernel, _ps, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user=user)
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        allow_fixture=True,
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Initialize the MPU6050 over I2C.",
    )
    paths = {op["path"] for op in proposed["proposal"]["operations"]}
    assert MAIN_CPP_PATH in paths
    main_op = next(op for op in proposed["proposal"]["operations"] if op["path"] == MAIN_CPP_PATH)
    assert "Wire.begin" in main_op["content"]
    ops = generate_firmware_patch_operations(
        requested_change="Initialize the MPU6050 over I2C.",
        base_snapshot=kernel.kernel_store.get_snapshot(proposed["proposal"]["baseSnapshotId"]),
        file_store=kernel.filesystem.file_store,
    )
    assert ops[0]["operationType"] == "replace-file"


def test_propose_uses_injected_live_generator() -> None:
    gateway = FakeModelGateway()
    gateway.set_script(
        "firmware.patch-proposal",
        lambda _task, _payload, _schema: {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "platformio.ini",
                    "content": "[env:nexus]\nmonitor_speed = 9600\n",
                }
            ]
        },
    )
    kernel, _ps, _kernel_store, project_id = build_test_kernel(
        auto_start_scheduler=False,
        firmware_patch_generator=LiveFirmwarePatchGenerator(
            gateway=gateway,
            model_policy=ModelPolicy(provider="fake", model="fake-model"),
        ),
    )
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user=user)
    proposed = kernel.workspace_runtime.propose_firmware_patch(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        requested_change="Set baud to 9600",
    )
    proposal = proposed["proposal"]
    assert proposal["generatorId"] == "firmware-patch-generator-llm-v1"
    assert proposal["generatorMetadata"]["mode"] == "regression"
