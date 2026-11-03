"""Phase 14D workspace-runtime facade integration tests."""

from __future__ import annotations

import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import CommandValidationError


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)
        assert isinstance(run, dict)
        if run["status"] not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.05)
    final = kernel.executions.get_run(run_id)
    assert isinstance(final, dict)
    return final


def test_workspace_runtime_binding_and_capabilities() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="code-scratch",
    )
    assert binding["projectId"] == project_id
    assert binding["artifactType"] == "code-scratch"
    assert binding["workspaceId"].startswith("ws_")
    assert binding["capabilities"]["filesystem"] is True
    assert binding["capabilities"]["snapshots"] is True
    assert binding["capabilities"]["execution"] is True
    assert binding["filesystemEnabled"] is True

    # Same binding on second resolve — not a new workspace per call/revision.
    again = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="code-scratch",
    )
    assert again["workspaceId"] == binding["workspaceId"]
    assert again["artifactId"] == binding["artifactId"]


def test_workspace_runtime_e2e_files_snapshot_execute_logs_output() -> None:
    """artifact → workspace → files → snapshot → execution → logs → output."""
    kernel, _ps, _ks, project_id = build_test_kernel()
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="code-scratch",
        actor=user,
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )

    written = kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="code-scratch",
        path="src/main.py",
        content=b"print('ready')\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert written["file"]["path"] == "src/main.py"
    assert written["file"]["contentReference"].startswith("cas:")

    listed = kernel.workspace_runtime.list_files(
        project_id=project_id, artifact_type="code-scratch"
    )
    assert any(f["path"] == "src/main.py" for f in listed["files"])

    read = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="code-scratch", path="src/main.py"
    )
    assert read["content"] == b"print('ready')\n"

    snap = kernel.workspace_runtime.create_snapshot(
        project_id=project_id,
        artifact_type="code-scratch",
        actor=user,
        reason="phase14d-e2e",
    )
    snapshot_id = snap["snapshotId"]
    assert snapshot_id.startswith("snap_")

    snaps = kernel.workspace_runtime.list_snapshots(
        project_id=project_id, artifact_type="code-scratch"
    )
    assert any(s["snapshotId"] == snapshot_id for s in snaps["snapshots"])

    started = kernel.workspace_runtime.start_execution(
        project_id=project_id,
        artifact_type="code-scratch",
        snapshot_id=snapshot_id,
        actor=user,
        command_spec={
            "schemaVersion": "1.0.0",
            "executable": "python3",
            "arguments": [
                "-c",
                "print('NEXUS_RUNTIME_READY'); open('out.txt','w').write('ok')",
            ],
            "workingDirectory": "",
            "environment": [],
            "declaredOutputs": [{"path": "out.txt", "kind": "result"}],
        },
    )
    run = started["executionRun"]
    run_id = run["executionRunId"]
    assert run.get("executionJobId")
    assert run.get("runtimeIdentity", {}).get("runtimeKind") in {"process", "container"}

    final = _wait_run(kernel, run_id)
    assert final["status"] in {"completed", "completed-with-warnings"}
    assert final.get("runtimeIdentity", {}).get("workspaceSnapshotId") == snapshot_id

    logs = kernel.workspace_runtime.list_logs(project_id=project_id, execution_run_id=run_id)
    stdout = "".join(c["content"] for c in logs["chunks"] if c["stream"] == "stdout")
    assert "NEXUS_RUNTIME_READY" in stdout

    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=run_id
    )
    assert len(outputs["outputs"]) == 1
    assert outputs["outputs"][0]["name"] == "out.txt"


def test_workspace_runtime_cancel_through_facade() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(
        scheduler_config=__import__(
            "nexus_board.execution.scheduler", fromlist=["SchedulerConfig"]
        ).SchedulerConfig(max_running_global=0, max_queued=8),
    )
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="code-scratch", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="code-scratch",
        path="x.txt",
        content=b"x",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    snap = kernel.workspace_runtime.create_snapshot(
        project_id=project_id, artifact_type="code-scratch", actor=user, reason="cancel"
    )
    started = kernel.workspace_runtime.start_execution(
        project_id=project_id,
        artifact_type="code-scratch",
        snapshot_id=snap["snapshotId"],
        actor=user,
        command_spec={
            "schemaVersion": "1.0.0",
            "executable": "python3",
            "arguments": ["-c", "print(1)"],
            "workingDirectory": "",
            "environment": [],
            "declaredOutputs": [],
        },
    )
    run_id = started["executionRun"]["executionRunId"]
    assert kernel.executions.get_run(run_id)["status"] == "queued"
    cancelled = kernel.workspace_runtime.cancel_execution(
        project_id=project_id, execution_run_id=run_id, actor=user
    )
    assert cancelled["executionRun"]["status"] == "cancelled"
    assert cancelled["executionJob"]["status"] == "cancelled"


def test_workspace_runtime_denies_non_filesystem_artifact() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    import pytest
    from nexus_board.services.workspace_runtime import WorkspaceRuntimeCapabilityError

    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id,
        artifact_type="project-brief",
        create_if_missing=True,
    )
    assert binding["capabilities"]["filesystem"] is False
    assert binding["capabilities"]["execution"] is False
    with pytest.raises(WorkspaceRuntimeCapabilityError):
        kernel.workspace_runtime.list_files(project_id=project_id, artifact_type="project-brief")


def test_graph_workspace_snapshot_capability() -> None:
    kernel, project_store, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    artifact = project_store.get_artifact(project_id, "functional-architecture")
    artifact = {
        **artifact,
        "artifactId": artifact["artifactId"] + "_electrical",
        "artifactType": "electrical-architecture",
    }
    project = project_store.get_project(project_id)
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=artifact,
        next_state_version=int(project["currentStateVersion"]) + 1,
        updated_at=artifact["updatedAt"],
        expected_project_state_version=project["currentStateVersion"],
    )
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="electrical-architecture"
    )
    assert binding["workspaceType"] == "graph-workspace"
    assert binding["capabilities"]["snapshots"] is True


@pytest.mark.parametrize("kind", ["unsupported", None])
def test_restore_rejects_unsupported_snapshot_kind(kind: str | None) -> None:
    kernel, _ps, store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="functional-architecture", actor=user
    )
    workspace_id = binding["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=workspace_id,
        requested_by=user,
    )
    snapshot = kernel.workspaces.create_snapshot(
        workspace_id=workspace_id, actor=user, reason="unsupported-kind"
    )
    # Seed an unsupported stored snapshot without changing an immutable snapshot.
    snapshot["snapshotId"] += "_unsupported"
    snapshot["content"] = {"kind": kind, "structuredContent": {"unexpected": True}}
    store.create_snapshot(snapshot)
    before = store.get_draft(workspace_id)
    with pytest.raises(CommandValidationError, match="Unsupported snapshot content kind"):
        kernel.workspaces.restore_snapshot(
            workspace_id=workspace_id, snapshot_id=snapshot["snapshotId"], actor=user
        )
    assert store.get_draft(workspace_id) == before
