"""Workspace lifecycle tests."""

from __future__ import annotations

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd
from nexus_persistence.errors import SnapshotImmutableError


def test_draft_does_not_bump_accepted_version() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    before = project_store.get_artifact(project_id, "requirement-set")
    editor = actor()
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=editor,
    )
    ws = created["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=before["artifactId"],
        workspace_id=ws,
        requested_by=editor,
    )
    result = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=before["artifactId"],
            workspace_id=ws,
            input_data={
                "content": {"requirements": [{"statement": "updated"}]},
                "expectedDraftVersion": 1,
            },
            requested_by=editor,
        )
    )
    assert result["status"] == "completed"
    after = project_store.get_artifact(project_id, "requirement-set")
    assert after["artifactVersion"] == before["artifactVersion"]
    assert after["artifactId"] == before["artifactId"]
    draft = kernel.kernel_store.get_draft(ws)
    assert draft["draftVersion"] == 2


def test_snapshot_immutable_and_restore_creates_new_draft() -> None:
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
            input_data={"reason": "checkpoint"},
            requested_by=editor,
        )
    )
    assert snap["status"] == "completed"
    snapshot = kernel_store.get_snapshot(snap["snapshotId"])
    with pytest.raises(SnapshotImmutableError):
        kernel_store.update_snapshot({**snapshot, "reason": "mutated"})

    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"title": "changed"}, "expectedDraftVersion": 1},
            requested_by=editor,
        )
    )
    restored = kernel.dispatch(
        cmd(
            command_type="workspace.restore-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"snapshotId": snap["snapshotId"]},
            requested_by=editor,
        )
    )
    assert restored["status"] == "completed"
    draft = kernel_store.get_draft(ws)
    assert draft["draftVersion"] == 3
    assert draft["content"] != {"title": "changed"}
