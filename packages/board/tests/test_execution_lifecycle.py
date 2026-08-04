"""Fake execution lifecycle tests."""

from __future__ import annotations

from helpers import actor, build_test_kernel, cmd


def test_execution_queued_running_completed() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "requirement-set")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="requirement-set",
        actor=actor(),
    )
    ws = created["workspace"]["workspaceId"]
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"reason": "validate"},
        )
    )
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={
                "snapshotId": snap["snapshotId"],
                "capability": "fake-execution",
            },
        )
    )
    assert result["status"] == "completed"
    assert result.get("executionRunId")
    run = kernel_store.get_execution_run(result["executionRunId"])
    assert run["status"] == "completed"
    assert run.get("startedAt")
    assert run.get("completedAt")
    assert run["outputReferences"]
    outputs = kernel_store.list_produced_outputs(project_id)
    assert any(o["evidenceStatus"] == "unverified" for o in outputs)
    assert any(o["outputType"] == "structured-result" for o in outputs)
    assert any(o["outputType"] == "log" for o in outputs)
