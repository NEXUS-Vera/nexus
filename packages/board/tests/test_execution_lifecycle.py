"""Fake execution lifecycle tests."""

from __future__ import annotations

from helpers import acquire_edit_lease, actor, build_test_kernel, cmd


class _InjectedExecutor:
    def execute(self, request: dict) -> dict:
        return {
            "providerId": "fake",
            "status": "completed-with-warnings",
            "outputs": [
                {
                    "outputType": "structured-result",
                    "name": "injected-result",
                    "structuredResult": {
                        "snapshotId": request["snapshotId"],
                        "observedOnly": True,
                    },
                    "entityReferences": [],
                }
            ],
            "externalWorkspaceReference": {
                "schemaVersion": "1.0.0",
                "providerId": "fake",
                "externalReferenceId": "workspace:injected",
                "syncStatus": "bound",
                "createdAt": request["snapshot"]["createdAt"],
                "updatedAt": request["snapshot"]["createdAt"],
            },
        }


def test_execution_queued_running_completed() -> None:
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
            input_data={"reason": "validate"},
            requested_by=editor,
        )
    )
    assert snap["status"] == "completed"
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


def test_injected_executor_normalizes_outputs_and_workspace_reference() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel(
        capability_executors={"fake-execution": _InjectedExecutor()}
    )
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
            input_data={"reason": "injected execution"},
            requested_by=editor,
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
    run = kernel_store.get_execution_run(result["executionRunId"])
    assert run["status"] == "completed-with-warnings"
    assert "queuedAt" not in run
    assert "resourceLimits" not in run
    output = kernel_store.list_produced_outputs(project_id)[0]
    assert output["providerId"] == "fake"
    assert output["provenance"]["sourceType"] == "external-provider"
    workspace = kernel_store.get_workspace(ws)
    assert workspace["externalWorkspaceReferences"][0]["externalReferenceId"] == (
        "workspace:injected"
    )
