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
    assert output["content"]["structuredResult"]["snapshotId"] == snap["snapshotId"]
    assert output["evidenceStatus"] == "unverified"
    workspace = kernel_store.get_workspace(ws)
    assert workspace["externalWorkspaceReferences"][0]["externalReferenceId"] == (
        "workspace:injected"
    )


def test_agent_claim_cannot_promote_execution_evidence() -> None:
    """M4: agent-supplied passing claims never become authoritative evidence."""
    kernel, projects, store, project_id = build_test_kernel()
    artifact = projects.get_artifact(project_id, "requirement-set")
    editor = actor()
    workspace = kernel.workspaces.create_workspace(
        project_id=project_id, artifact_type="requirement-set", actor=editor
    )["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=artifact["artifactId"],
        workspace_id=workspace,
        requested_by=editor,
    )
    snapshot = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=artifact["artifactId"],
            workspace_id=workspace,
            input_data={"reason": "agent claim"},
            requested_by=editor,
        )
    )
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=artifact["artifactId"],
            workspace_id=workspace,
            requested_by=actor("embedded-systems-agent"),
            input_data={
                "snapshotId": snapshot["snapshotId"],
                "capability": "fake-execution",
                "evidenceStatus": "tested",
                "status": "tested",
            },
        )
    )
    assert result["status"] == "completed"
    outputs = store.list_produced_outputs(project_id)
    assert outputs
    assert all(o["evidenceStatus"] == "unverified" for o in outputs)
    assert projects.get_artifact(project_id, "requirement-set") == artifact
    events, _ = store.list_project_events(project_id)
    evidence = [e for e in events if e["eventType"] == "evidence.attached"]
    assert evidence
    assert all(e["payload"]["evidenceStatus"] == "unverified" for e in evidence)


def test_configuration_failure_is_failed_not_stale() -> None:
    from nexus_circuit_simulation import CircuitConfigurationError

    class UnavailableExecutor:
        def execute(self, request):
            raise CircuitConfigurationError(
                message="Simulator credential missing", code="WOKWI_CREDENTIAL_MISSING"
            )

    kernel, projects, store, pid = build_test_kernel(
        capability_executors={"fake-execution": UnavailableExecutor()}
    )
    art = projects.get_artifact(pid, "requirement-set")
    editor = actor()
    ws = kernel.workspaces.create_workspace(
        project_id=pid, artifact_type="requirement-set", actor=editor
    )["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel, project_id=pid, artifact_id=art["artifactId"], workspace_id=ws, requested_by=editor
    )
    snap = kernel.workspaces.create_snapshot(
        workspace_id=ws, reason="configuration gate", actor=editor
    )
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=pid,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"snapshotId": snap["snapshotId"], "capability": "fake-execution"},
        )
    )
    assert result["error"]["code"] == "WOKWI_CREDENTIAL_MISSING"
    runs, _ = store.list_execution_runs(pid)
    assert runs[0]["status"] == "failed"
    assert runs[0]["error"]["code"] == "WOKWI_CREDENTIAL_MISSING"
    assert runs[0]["outputReferences"] == []
    assert runs[0]["evidenceReferences"] == []


def test_timeout_retains_partial_output() -> None:
    class PartialTimeout(TimeoutError):
        code = "SIMULATION_TIMEOUT"
        partial_outputs = [
            {
                "name": "serial.log",
                "outputType": "log",
                "structuredResult": {"text": "TEL,0,0,0,1", "truncated": True},
                "evidenceStatus": "unverified",
            }
        ]

    class UnavailableExecutor:
        def execute(self, request: dict) -> dict:
            raise PartialTimeout("Simulation timed out")

    kernel, projects, store, pid = build_test_kernel(
        capability_executors={"fake-execution": UnavailableExecutor()}
    )
    art = projects.get_artifact(pid, "requirement-set")
    editor = actor()
    ws = kernel.workspaces.create_workspace(
        project_id=pid, artifact_type="requirement-set", actor=editor
    )["workspace"]["workspaceId"]
    acquire_edit_lease(
        kernel, project_id=pid, artifact_id=art["artifactId"], workspace_id=ws, requested_by=editor
    )
    snap = kernel.workspaces.create_snapshot(
        workspace_id=ws, reason="configuration gate", actor=editor
    )
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=pid,
            artifact_id=art["artifactId"],
            workspace_id=ws,
            input_data={"snapshotId": snap["snapshotId"], "capability": "fake-execution"},
        )
    )
    assert result["error"]["code"] == "SIMULATION_TIMEOUT"
    runs, _ = store.list_execution_runs(pid)
    assert runs[0]["status"] == "timed-out"
    assert runs[0]["error"]["code"] == "SIMULATION_TIMEOUT"
    assert len(runs[0]["outputReferences"]) == 1
    output = store.get_produced_output(runs[0]["outputReferences"][0])
    assert output["evidenceStatus"] == "unverified"
    assert output["content"]["structuredResult"]["truncated"] is True
    assert output["content"]["structuredResult"]["text"] == "TEL,0,0,0,1"
    assert runs[0]["evidenceReferences"] == []
