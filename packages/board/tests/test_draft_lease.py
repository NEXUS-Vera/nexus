"""Draft edit-lease and discard-draft tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helpers import acquire_edit_lease, actor, build_test_kernel, cmd


def test_second_editor_blocked() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    editor_a = actor("user")
    editor_b = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=editor_a,
    )
    ws = created["workspace"]["workspaceId"]
    acquired = acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_a,
    )
    assert acquired["status"] == "completed"

    blocked = acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_b,
    )
    assert blocked["status"] == "failed"
    assert blocked["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"

    update = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": []}, "expectedDraftVersion": 1},
            requested_by=editor_b,
        )
    )
    assert update["status"] == "failed"
    assert update["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"


def test_lease_release_allows_other() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    editor_a = actor("user")
    editor_b = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=editor_a,
    )
    ws = created["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_a,
    )
    released = kernel.dispatch(
        cmd(
            command_type="workspace.release-edit-lease",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            requested_by=editor_a,
        )
    )
    assert released["status"] == "completed"

    acquired_b = acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_b,
    )
    assert acquired_b["status"] == "completed"
    updated = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"x": 1}]}, "expectedDraftVersion": 1},
            requested_by=editor_b,
        )
    )
    assert updated["status"] == "completed"


def test_lease_expiry_allows_reacquire() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    editor_a = actor("user")
    editor_b = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=editor_a,
    )
    ws = created["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_a,
    )
    draft = dict(kernel_store.get_draft(ws))
    lease = dict(draft["editLease"])
    past = (datetime.now(UTC) - timedelta(minutes=1)).replace(microsecond=0)
    lease["expiresAt"] = past.isoformat().replace("+00:00", "Z")
    draft["editLease"] = lease
    kernel_store.update_draft(draft)

    acquired_b = acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor_b,
    )
    assert acquired_b["status"] == "completed"

    # Actor A's stale client session must not mutate after B reacquired.
    rejected = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"from": "a"}]}, "expectedDraftVersion": 1},
            requested_by=editor_a,
        )
    )
    assert rejected["status"] == "failed"
    assert rejected["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"

    # B can mutate; optimistic concurrency still applies.
    allowed = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"from": "b"}]}, "expectedDraftVersion": 1},
            requested_by=editor_b,
        )
    )
    assert allowed["status"] == "completed"


def test_stale_draft_version_still_fails() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    editor = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
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
    first = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"a": 1}]}, "expectedDraftVersion": 1},
            requested_by=editor,
        )
    )
    assert first["status"] == "completed"
    stale = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"a": 2}]}, "expectedDraftVersion": 1},
            requested_by=editor,
        )
    )
    assert stale["status"] == "conflicted"
    assert stale["error"]["code"] == "ARTIFACT_VERSION_CONFLICT"


def test_agent_cannot_update_draft_without_lease() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    agent = actor("vera")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=actor("user"),
    )
    ws = created["workspace"]["workspaceId"]
    result = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": []}, "expectedDraftVersion": 1},
            requested_by=agent,
        )
    )
    assert result["status"] == "failed"
    assert result["error"]["code"] == "DRAFT_EDIT_LEASE_REQUIRED"


def test_discard_restores_accepted_content_without_new_artifact_version() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    original_content = dict(art["content"])
    original_version = art["artifactVersion"]
    editor = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
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
    updated = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={
                "content": {"requirements": [{"statement": "dirty"}]},
                "expectedDraftVersion": 1,
            },
            requested_by=editor,
        )
    )
    assert updated["status"] == "completed"
    events_before = len(kernel_store.list_project_events(project_id)[0])

    discarded = kernel.dispatch(
        cmd(
            command_type="workspace.discard-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"expectedDraftVersion": 2},
            requested_by=editor,
        )
    )
    assert discarded["status"] == "completed"
    draft = kernel_store.get_draft(ws)
    assert draft["draftVersion"] == 3
    assert draft["content"] == original_content
    assert draft["validationState"] == "unvalidated"
    assert "editLease" in draft
    after = project_store.get_artifact(project_id, "requirement-set")
    assert after["artifactVersion"] == original_version
    assert after["artifactId"] == art["artifactId"]
    events_after = len(kernel_store.list_project_events(project_id)[0])
    assert events_after == events_before


def test_agent_cannot_restore_snapshot_without_lease() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "project-brief")
    owner = actor("user")
    agent = actor("vera")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="project-brief",
        actor=owner,
    )
    ws = created["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=owner,
    )
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "checkpoint"},
            requested_by=owner,
        )
    )
    assert snap["status"] == "completed"

    blocked = kernel.dispatch(
        cmd(
            command_type="workspace.restore-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"snapshotId": snap["snapshotId"]},
            requested_by=agent,
        )
    )
    assert blocked["status"] == "failed"
    assert blocked["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"


def test_agent_cannot_create_snapshot_without_lease() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "project-brief")
    agent = actor("vera")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="project-brief",
        actor=actor("user"),
    )
    ws = created["workspace"]["workspaceId"]
    blocked = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "agent-bypass"},
            requested_by=agent,
        )
    )
    assert blocked["status"] == "failed"
    assert blocked["error"]["code"] == "DRAFT_EDIT_LEASE_REQUIRED"
