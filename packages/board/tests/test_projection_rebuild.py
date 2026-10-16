"""Projection rebuild determinism tests."""

from __future__ import annotations

from helpers import acquire_edit_lease, actor, build_test_kernel, cmd


def test_rebuild_matches_stored_projection() -> None:
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
    kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "board"},
            requested_by=editor,
        )
    )
    stored = kernel.get_board(project_id)
    rebuilt = kernel.projection.rebuild_project_board_projection(project_id)

    # Ignore volatile fields that intentionally increment on rebuild.
    for key in ("projectionVersion", "updatedAt"):
        stored.pop(key, None)
        rebuilt.pop(key, None)
    assert rebuilt == stored

    types = {s["artifactType"] for s in rebuilt["artifactSummaries"]}
    assert "project-brief" in types
    assert "component-plan" in types
    assert "next-action" in types
    component = next(
        s for s in rebuilt["artifactSummaries"] if s["artifactType"] == "component-plan"
    )
    assert component["lifecycleStatus"] == "drafted"
