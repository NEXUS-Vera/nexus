"""Phase 15D firmware snapshot history tests."""

from __future__ import annotations

from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.firmware.toolchain import SNAPSHOT_REASON_BEFORE_RESTORE, SNAPSHOT_REASON_MANUAL


def _setup_scaffolded_firmware(kernel: Any, project_id: str, user: dict[str, Any]) -> dict[str, Any]:
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


def test_list_and_create_manual_snapshot() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)

    listed = kernel.workspace_runtime.list_snapshots(
        project_id=project_id, artifact_type="firmware"
    )
    assert listed["snapshots"] == []

    created = kernel.workspace_runtime.create_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason=SNAPSHOT_REASON_MANUAL,
    )
    assert created["reason"] == SNAPSHOT_REASON_MANUAL
    listed_after = kernel.workspace_runtime.list_snapshots(
        project_id=project_id, artifact_type="firmware"
    )
    assert len(listed_after["snapshots"]) == 1
    assert listed_after["snapshots"][0]["snapshotId"] == created["snapshotId"]


def test_restore_creates_before_restore_snapshot() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)
    manual = kernel.workspace_runtime.create_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason=SNAPSHOT_REASON_MANUAL,
    )
    target_id = manual["snapshotId"]

    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="platformio.ini",
        content=b"# edited\n",
        actor=user,
        expected_draft_version=int(kernel_store.get_draft(binding["workspaceId"])["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    restored = kernel.workspace_runtime.restore_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        snapshot_id=target_id,
        actor=user,
    )
    assert restored["beforeRestoreSnapshotId"].startswith("snap_")
    snapshots = kernel_store.list_snapshots(binding["workspaceId"])
    reasons = {snap["reason"] for snap in snapshots}
    assert SNAPSHOT_REASON_BEFORE_RESTORE in reasons
    record = kernel_store.get_workspace_file(binding["workspaceId"], "platformio.ini")
    assert record is not None
    content = kernel.filesystem.read_file(binding["workspaceId"], "platformio.ini")["content"]
    assert b"monitor_speed" in content


def test_read_snapshot_file_without_mutating_workspace() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)
    snap = kernel.workspace_runtime.create_firmware_snapshot(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        reason=SNAPSHOT_REASON_MANUAL,
    )
    before = kernel_store.list_workspace_files(binding["workspaceId"])
    preview = kernel.workspace_runtime.read_firmware_snapshot_file(
        project_id=project_id,
        artifact_type="firmware",
        snapshot_id=snap["snapshotId"],
        path="platformio.ini",
    )
    assert "monitor_speed" in preview["content"]
    after = kernel_store.list_workspace_files(binding["workspaceId"])
    assert after == before


def test_non_firmware_snapshot_create_rejected() -> None:
    kernel, _ps, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    with pytest.raises(Exception):  # noqa: B017
        kernel.workspace_runtime.create_firmware_snapshot(
            project_id=project_id,
            artifact_type="code-scratch",
            actor=user,
        )
