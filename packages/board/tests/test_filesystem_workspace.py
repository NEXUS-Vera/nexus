"""Phase 14A filesystem workspace spine tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd
from nexus_board.errors import (
    DraftEditLeaseHeldError,
    DraftEditLeaseRequiredError,
    WorkspaceFileNotFoundError,
    WorkspacePathError,
    WorkspaceQuotaExceededError,
    WorkspaceWritePolicyError,
)
from nexus_board.ids import content_digest
from nexus_board.paths import normalize_workspace_path
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits
from nexus_board.services.filesystem_service import build_filesystem_manifest
from nexus_persistence.file_store import LocalFileStore, blob_digest
from nexus_persistence.file_store.memory import InMemoryFileStore


def _create_code_workspace(kernel: Any, project_id: str, editor: dict[str, Any]) -> Any:
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="code-scratch",
        actor=editor,
    )
    workspace = created["workspace"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=workspace["artifactId"],
        workspace_id=workspace["workspaceId"],
        requested_by=editor,
    )
    return created


def test_path_normalization_and_rejection() -> None:
    assert normalize_workspace_path("src/main.cpp") == "src/main.cpp"
    assert normalize_workspace_path("a/b/c.h") == "a/b/c.h"
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("../etc/passwd")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("/abs/path")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("C:\\Windows\\system32")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("foo\\bar")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("a/./b")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("a//b")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("con")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("foo\x00bar")
    with pytest.raises(WorkspacePathError):
        normalize_workspace_path("~/.ssh/id_rsa")


def test_file_lifecycle_lease_and_metadata() -> None:
    kernel, _project_store, _, project_id = build_test_kernel()
    editor = actor()
    created = _create_code_workspace(kernel, project_id, editor)
    ws_id = created["workspace"]["workspaceId"]
    art_id = created["workspace"]["artifactId"]

    with pytest.raises((DraftEditLeaseRequiredError, DraftEditLeaseHeldError)):
        kernel.filesystem.write_file(
            workspace_id=ws_id,
            path="src/main.cpp",
            content=b"int main() {}",
            actor=actor(),
            expected_draft_version=1,
            base_artifact_version=1,
            base_project_state_version=1,
        )

    written = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"int main() {}",
        actor=editor,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert written["file"]["origin"] == "USER"
    assert written["file"]["writePolicy"] == "USER_EDITABLE"
    assert written["file"]["modifiedByUser"] is False
    assert written["draft"]["draftVersion"] == 2
    assert written["file"]["contentReference"].startswith("cas:")
    assert "/" not in written["file"]["contentReference"]
    assert not Path(written["file"]["contentReference"]).exists()

    listed = kernel.filesystem.list_files(ws_id)
    assert [item["path"] for item in listed] == ["src/main.cpp"]
    read = kernel.filesystem.read_file(ws_id, "src/main.cpp")
    assert read["content"] == b"int main() {}"

    overwritten = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"int main() { return 0; }",
        actor=editor,
        expected_draft_version=2,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert overwritten["file"]["modifiedByUser"] is True
    assert overwritten["draft"]["draftVersion"] == 3

    renamed = kernel.filesystem.rename_file(
        workspace_id=ws_id,
        from_path="src/main.cpp",
        to_path="src/app.cpp",
        actor=editor,
        expected_draft_version=3,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert renamed["file"]["path"] == "src/app.cpp"
    with pytest.raises(WorkspaceFileNotFoundError):
        kernel.filesystem.read_file(ws_id, "src/main.cpp")

    deleted = kernel.filesystem.delete_file(
        workspace_id=ws_id,
        path="src/app.cpp",
        actor=editor,
        expected_draft_version=4,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert deleted["draft"]["draftVersion"] == 5
    assert kernel.filesystem.list_files(ws_id) == []

    # Ordinary file edits must not create artifact revisions.
    workspace_after = kernel.kernel_store.get_workspace(ws_id)
    assert workspace_after["baseArtifactVersion"] == 1
    assert workspace_after["artifactId"] == art_id
    assert kernel.kernel_store.get_draft(ws_id)["draftVersion"] == 5


def test_generated_origin_and_read_only_policy() -> None:
    kernel, _, _, project_id = build_test_kernel()
    editor = actor()
    created = _create_code_workspace(kernel, project_id, editor)
    ws_id = created["workspace"]["workspaceId"]

    generated = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="generated/scaffold.cpp",
        content=b"// scaffold",
        actor=editor,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
        origin="GENERATED",
        write_policy="REGENERATION_MANAGED",
        generated_from="scaffold-v1",
    )
    assert generated["file"]["origin"] == "GENERATED"
    assert generated["file"]["modifiedByUser"] is False

    edited = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="generated/scaffold.cpp",
        content=b"// scaffold edited",
        actor=editor,
        expected_draft_version=2,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert edited["file"]["origin"] == "GENERATED"
    assert edited["file"]["modifiedByUser"] is True
    assert edited["file"]["writePolicy"] == "REGENERATION_MANAGED"

    readonly = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="SYSTEM/README",
        content=b"do not edit",
        actor=editor,
        expected_draft_version=3,
        base_artifact_version=1,
        base_project_state_version=1,
        origin="SYSTEM",
        write_policy="READ_ONLY",
    )
    assert readonly["file"]["writePolicy"] == "READ_ONLY"
    with pytest.raises(WorkspaceWritePolicyError):
        kernel.filesystem.write_file(
            workspace_id=ws_id,
            path="SYSTEM/README",
            content=b"mutated",
            actor=editor,
            expected_draft_version=4,
            base_artifact_version=1,
            base_project_state_version=1,
        )


def test_quotas_and_failed_write_preserves_state(tmp_path: Path) -> None:
    limits = WorkspaceFilesystemLimits(
        max_file_bytes=16,
        max_workspace_bytes=32,
        max_file_count=2,
    )
    kernel, _, _, project_id = build_test_kernel()
    # Rebuild filesystem service with tight limits while keeping the same stores.
    from nexus_board.services.filesystem_service import FilesystemWorkspaceService

    kernel.filesystem = FilesystemWorkspaceService(
        kernel.kernel_store,
        kernel.project_store,
        InMemoryFileStore(),
        kernel.projection,
        limits=limits,
    )
    kernel.workspaces._filesystem = kernel.filesystem  # noqa: SLF001
    editor = actor()
    created = _create_code_workspace(kernel, project_id, editor)
    ws_id = created["workspace"]["workspaceId"]

    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="a.txt",
        content=b"hello",
        actor=editor,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    with pytest.raises(WorkspaceQuotaExceededError):
        kernel.filesystem.write_file(
            workspace_id=ws_id,
            path="big.txt",
            content=b"x" * 20,
            actor=editor,
            expected_draft_version=2,
            base_artifact_version=1,
            base_project_state_version=1,
        )
    assert [f["path"] for f in kernel.filesystem.list_files(ws_id)] == ["a.txt"]
    draft = kernel.kernel_store.get_draft(ws_id)
    assert draft["draftVersion"] == 2


def test_local_file_store_atomic_and_content_addressed(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path / "blobs")
    first = store.put(b"alpha")
    second = store.put(b"alpha")
    assert first == second == blob_digest(b"alpha")
    assert store.get(first) == b"alpha"
    assert store.exists(first)
    other = store.put(b"beta")
    assert other != first
    assert first.startswith("sha256:")
    assert store.exists(other)


def test_snapshot_immutable_restore_and_blob_retention() -> None:
    kernel, _, kernel_store, project_id = build_test_kernel()
    editor = actor()
    created = _create_code_workspace(kernel, project_id, editor)
    ws_id = created["workspace"]["workspaceId"]
    art_id = created["workspace"]["artifactId"]

    first = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"v1",
        actor=editor,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    old_hash = first["file"]["contentHash"]
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art_id,
            workspace_id=ws_id,
            input_data={"reason": "checkpoint"},
            requested_by=editor,
        )
    )
    assert snap["status"] == "completed"
    snapshot = kernel_store.get_snapshot(snap["snapshotId"])
    assert snapshot["content"]["kind"] == "filesystem"
    digest = snapshot["content"]["filesystemManifest"]["manifestDigest"]
    assert snapshot["contentDigest"] == digest

    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/main.cpp",
        content=b"v2",
        actor=editor,
        expected_draft_version=2,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="src/extra.cpp",
        content=b"extra",
        actor=editor,
        expected_draft_version=3,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    # Snapshot unchanged after mutable edits.
    unchanged = kernel_store.get_snapshot(snap["snapshotId"])
    assert unchanged["contentDigest"] == digest
    assert kernel.file_store.exists(old_hash)

    restored = kernel.dispatch(
        cmd(
            command_type="workspace.restore-snapshot",
            project_id=project_id,
            artifact_id=art_id,
            workspace_id=ws_id,
            input_data={"snapshotId": snap["snapshotId"]},
            requested_by=editor,
        )
    )
    assert restored["status"] == "completed"
    files = kernel.filesystem.list_files(ws_id)
    assert [f["path"] for f in files] == ["src/main.cpp"]
    assert kernel.filesystem.read_file(ws_id, "src/main.cpp")["content"] == b"v1"

    # Identical trees produce identical manifest digests.
    again = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art_id,
            workspace_id=ws_id,
            input_data={"reason": "again"},
            requested_by=editor,
        )
    )
    snap2 = kernel_store.get_snapshot(again["snapshotId"])
    assert snap2["contentDigest"] == digest
    assert snap2["snapshotId"] != snap["snapshotId"]

    referenced = kernel_store.list_referenced_content_hashes()
    assert old_hash in referenced


def test_structured_snapshot_still_works() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "project-brief")
    editor = actor()
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="project-brief",
        actor=editor,
    )
    ws = created["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor,
    )
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "structured"},
            requested_by=editor,
        )
    )
    assert snap["status"] == "completed"
    snapshot = kernel_store.get_snapshot(snap["snapshotId"])
    assert snapshot["content"]["kind"] == "structured"


def test_manifest_sort_is_deterministic() -> None:
    files = [
        {
            "path": "b.txt",
            "contentHash": "sha256:" + ("b" * 64),
            "contentReference": "cas:" + ("b" * 64),
            "sizeBytes": 1,
            "origin": "USER",
            "writePolicy": "USER_EDITABLE",
            "modifiedByUser": False,
        },
        {
            "path": "a.txt",
            "contentHash": "sha256:" + ("a" * 64),
            "contentReference": "cas:" + ("a" * 64),
            "sizeBytes": 1,
            "origin": "USER",
            "writePolicy": "USER_EDITABLE",
            "modifiedByUser": False,
        },
    ]
    manifest = build_filesystem_manifest(files)
    assert [e["path"] for e in manifest["entries"]] == ["a.txt", "b.txt"]
    assert manifest["manifestDigest"] == content_digest({"entries": manifest["entries"]})
