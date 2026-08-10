"""Concurrency conflict tests."""

from __future__ import annotations

from helpers import acquire_edit_lease, actor, build_test_kernel, cmd


def test_artifact_version_conflict_on_draft_update() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
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
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor,
    )
    result = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            base_artifact_version=99,
            input_data={
                "content": {"requirements": []},
                "expectedDraftVersion": 1,
            },
            requested_by=editor,
        )
    )
    assert result["status"] == "conflicted"
    assert result["error"]["code"] == "ARTIFACT_VERSION_CONFLICT"


def test_competing_proposals_conflict() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
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
        artifact_id=art["artifactId"],
        workspace_id=ws,
        requested_by=editor,
    )
    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": []}, "expectedDraftVersion": 1},
            requested_by=editor,
        )
    )
    snap1 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "p1"},
            requested_by=editor,
        )
    )
    assert snap1["status"] == "completed"
    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"x": 1}]}, "expectedDraftVersion": 2},
            requested_by=editor,
        )
    )
    snap2 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "p2"},
            requested_by=editor,
        )
    )
    assert snap2["status"] == "completed"
    p1 = kernel.dispatch(
        cmd(
            command_type="artifact.propose-revision",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={
                "snapshotId": snap1["snapshotId"],
                "consequenceLevel": "low",
            },
            requested_by=actor("user"),
        )
    )
    p2 = kernel.dispatch(
        cmd(
            command_type="artifact.propose-revision",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={
                "snapshotId": snap2["snapshotId"],
                "consequenceLevel": "low",
            },
            requested_by=actor("user"),
        )
    )
    accept = kernel.dispatch(
        cmd(
            command_type="artifact.accept-revision",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"proposalId": p1["proposalId"]},
            requested_by=actor("user"),
        )
    )
    assert accept["status"] == "completed"
    other = kernel_store.get_proposal(p2["proposalId"])
    assert other["status"] == "conflicted"


def test_stale_execution_not_promoted() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
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
            input_data={"reason": "exec"},
            requested_by=editor,
        )
    )
    assert snap["status"] == "completed"
    project = project_store.get_project(project_id)
    project["currentStateVersion"] = 2
    project_store._projects[project_id] = project  # noqa: SLF001

    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            base_project_state_version=1,
            input_data={
                "snapshotId": snap["snapshotId"],
                "capability": "structured-validation",
            },
        )
    )
    assert result["status"] == "conflicted"
    assert result["error"]["code"] == "STALE_EXECUTION_RESULT"
    runs, _ = kernel_store.list_execution_runs(project_id)
    assert runs
    assert runs[-1]["status"] == "stale"
    current = project_store.get_artifact(project_id, "requirement-set")
    assert current["artifactVersion"] == 1
