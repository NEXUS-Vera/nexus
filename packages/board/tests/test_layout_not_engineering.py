"""Prove layout/draft activity stays outside accepted engineering revision history."""

from __future__ import annotations

from helpers import acquire_edit_lease, actor, build_test_kernel, cmd


def test_repeated_draft_edits_do_not_create_accepted_revisions() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    before_version = art["artifactVersion"]
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

    events_before, _ = kernel_store.list_project_events(project_id, limit=200)
    accepted_before = [e for e in events_before if e.get("eventType") == "artifact.accepted"]

    for i in range(5):
        draft = kernel.kernel_store.get_draft(ws)
        result = kernel.dispatch(
            cmd(
                command_type="workspace.update-draft",
                project_id=project_id,
                artifact_id=art["artifactId"],
                workspace_id=ws,
                input_data={
                    "content": {"requirements": [{"statement": f"layout-adjacent edit {i}"}]},
                    "expectedDraftVersion": draft["draftVersion"],
                },
                requested_by=editor,
            )
        )
        assert result["status"] == "completed"

    after = project_store.get_artifact(project_id, "requirement-set")
    assert after["artifactVersion"] == before_version
    assert after["artifactId"] == art["artifactId"]

    events_after, _ = kernel_store.list_project_events(project_id, limit=200)
    accepted_after = [e for e in events_after if e.get("eventType") == "artifact.accepted"]
    assert len(accepted_after) == len(accepted_before)

    projection = kernel_store.get_board_projection(project_id) or {}
    # recentChanges may exist; none should claim a new accepted artifact version.
    for change in projection.get("recentChanges") or []:
        assert change.get("artifactVersion") != before_version + 1 or change.get(
            "changeType"
        ) not in {"accepted", "artifact.accepted"}


def test_discard_draft_does_not_accept_revision() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
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
    kernel.dispatch(
        cmd(
            command_type="workspace.update-draft",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={
                "content": {**art["content"], "summary": "dirty"},
                "expectedDraftVersion": 1,
            },
            requested_by=editor,
        )
    )
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
    current = project_store.get_artifact(project_id, "project-brief")
    assert current["artifactVersion"] == art["artifactVersion"]
    assert current["content"]["summary"] == art["content"]["summary"]
