"""Concurrency conflict tests."""

from __future__ import annotations

from helpers import actor, build_test_kernel, cmd


def test_artifact_version_conflict_on_draft_update() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=actor(),
    )
    result = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=created["workspace"]["workspaceId"],
            base_artifact_version=99,
            input_data={
                "content": {"requirements": []},
                "expectedDraftVersion": 1,
            },
        )
    )
    assert result["status"] == "conflicted"
    assert result["error"]["code"] == "ARTIFACT_VERSION_CONFLICT"


def test_competing_proposals_conflict() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=actor(),
    )
    ws = created["workspace"]["workspaceId"]
    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": []}, "expectedDraftVersion": 1},
        )
    )
    snap1 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "p1"},
        )
    )
    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": [{"x": 1}]}, "expectedDraftVersion": 2},
        )
    )
    snap2 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "p2"},
        )
    )
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
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=actor(),
    )
    ws = created["workspace"]["workspaceId"]
    updated = kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"content": {"requirements": []}, "expectedDraftVersion": 1},
        )
    )
    assert updated["status"] == "completed"
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "exec"},
        )
    )
    proposal = kernel.dispatch(
        cmd(
            command_type="artifact.propose-revision",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"snapshotId": snap["snapshotId"]},
        )
    )
    accepted = kernel.dispatch(
        cmd(
            command_type="artifact.accept-revision",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"proposalId": proposal["proposalId"]},
        )
    )
    assert accepted["status"] == "completed"
    head = project_store.get_artifact(project_id, "requirement-set")
    assert head["artifactVersion"] == 2

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
    assert current == head
    assert kernel_store.list_produced_outputs(project_id) == []
    events, _ = kernel_store.list_project_events(project_id)
    assert any(
        e["eventType"] == "execution.failed" and e["payload"]["reason"] == "STALE_EXECUTION_RESULT"
        for e in events
    )
