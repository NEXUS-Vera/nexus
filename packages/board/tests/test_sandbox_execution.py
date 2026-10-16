"""Phase 14B sandboxed ExecutionJob / runtime tests."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd
from nexus_board.execution.job_states import (
    IllegalJobTransitionError,
    assert_job_transition,
    job_status_to_run_status,
)
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.scheduler import (
    ExecutionQueueFullError,
    InProcessExecutionScheduler,
    SchedulerConfig,
)


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)
        assert isinstance(run, dict)
        if run["status"] not in {"queued", "starting", "running"}:
            return run
        time.sleep(0.05)
    final = kernel.executions.get_run(run_id)
    assert isinstance(final, dict)
    return final


def _prepare_scratch(kernel: Any, project_id: str, files: dict[str, str]) -> dict[str, Any]:
    user = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id,
        artifact_type="code-scratch",
        actor=user,
    )
    ws = created["workspace"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=ws["artifactId"],
        workspace_id=ws["workspaceId"],
        requested_by=user,
    )
    draft_version = 1
    for path, content in files.items():
        written = kernel.filesystem.write_file(
            workspace_id=ws["workspaceId"],
            path=path,
            content=content.encode("utf-8"),
            expected_draft_version=draft_version,
            base_artifact_version=ws["baseArtifactVersion"],
            base_project_state_version=ws["baseProjectStateVersion"],
            actor=user,
        )
        draft_version = written["draft"]["draftVersion"]
    snap = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=ws["artifactId"],
            workspace_id=ws["workspaceId"],
            base_artifact_version=ws["baseArtifactVersion"],
            base_project_state_version=ws["baseProjectStateVersion"],
            input_data={"reason": "exec"},
            requested_by=user,
        )
    )
    assert snap["status"] == "completed"
    return {
        "project_id": project_id,
        "workspace": ws,
        "snapshot_id": snap["snapshotId"],
        "actor": user,
    }


def _fixture_command(*, sleep_s: float = 0.0, write_result: bool = True) -> dict[str, Any]:
    lines = [
        "import os,sys,time",
        "print('NEXUS_RUNTIME_READY')",
        "print('secret-check',"
        " 'WOKWI_CLI_TOKEN' in os.environ, 'NEXUS_DATABASE_URL' in os.environ)",
        f"time.sleep({sleep_s})",
    ]
    if write_result:
        lines.append("open('result.txt','w').write('ok')")
    code = ";".join(lines)
    return {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", code],
        "workingDirectory": "",
        "environment": {"NEXUS_JOB": "fixture"},
        "declaredOutputs": [{"path": "result.txt", "kind": "result"}] if write_result else [],
    }


def test_job_status_transitions_and_mapping() -> None:
    assert_job_transition("queued", "starting")
    assert_job_transition("starting", "running")
    assert_job_transition("running", "succeeded")
    assert_job_transition("queued", "cancelled")
    assert_job_transition("running", "cancelling")
    assert_job_transition("cancelling", "cancelled")
    assert_job_transition("running", "timed-out")
    with pytest.raises(IllegalJobTransitionError):
        assert_job_transition("succeeded", "running")
    with pytest.raises(IllegalJobTransitionError):
        assert_job_transition("queued", "running")
    assert job_status_to_run_status("queued") == "queued"
    assert job_status_to_run_status("succeeded") == "completed"
    assert job_status_to_run_status("timed-out") == "timed-out"
    assert job_status_to_run_status("cancelled") == "cancelled"


def test_scheduler_capacity_fifo_and_queue_bound() -> None:
    started: list[str] = []
    released = {"go": False}

    def on_dispatch(job_id: str) -> None:
        started.append(job_id)
        while not released["go"]:
            time.sleep(0.01)

    scheduler = InProcessExecutionScheduler(
        SchedulerConfig(max_running_global=1, max_running_per_project=1, max_queued=1),
        on_dispatch=on_dispatch,
    )
    scheduler.start()
    try:
        scheduler.enqueue("j1", "p1")
        # Wait until j1 is running so the queue slot frees for j2.
        deadline = time.monotonic() + 2
        while not started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started == ["j1"]
        scheduler.enqueue("j2", "p1")
        snap = scheduler.snapshot()
        assert snap["queued"] == ["j2"]
        with pytest.raises(ExecutionQueueFullError):
            scheduler.enqueue("j3", "p2")
        released["go"] = True
        deadline = time.monotonic() + 2
        while len(started) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started == ["j1", "j2"]
    finally:
        released["go"] = True
        scheduler.stop(wait=True)


def test_sandbox_success_logs_outputs_and_identity() -> None:
    os.environ["WOKWI_CLI_TOKEN"] = "should-not-leak"
    os.environ["NEXUS_DATABASE_URL"] = "postgresql://secret"
    kernel, _, _, project_id = build_test_kernel(
        execution_limits=ExecutionLimits(wall_time_ms=5_000, total_log_bytes=64_000),
        scheduler_config=SchedulerConfig(max_running_global=2, max_running_per_project=1),
    )
    ctx = _prepare_scratch(kernel, project_id, {"README.md": "# scratch"})
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": _fixture_command(),
            },
            requested_by=ctx["actor"],
        )
    )
    assert result["status"] == "completed"
    run_id = result["executionRunId"]
    run = _wait_run(kernel, run_id)
    assert run["status"] == "completed"
    assert run["executionJobId"]
    assert run["runtimeIdentity"]["runtimeKind"] == "process"
    assert run["runtimeIdentity"]["workspaceSnapshotId"] == ctx["snapshot_id"]
    assert run["runtimeIdentity"]["commandSpecVersion"] == "1.0.0"
    assert "workspaceManifestDigest" in run["runtimeIdentity"]
    logs = kernel.executions.list_logs(run_id)
    streams = {c["stream"] for c in logs["chunks"]}
    assert "stdout" in streams
    assert any(
        "NEXUS_RUNTIME_READY" in c["content"] for c in logs["chunks"] if c["stream"] == "stdout"
    )
    secret_lines = [
        c["content"]
        for c in logs["chunks"]
        if c["stream"] == "stdout" and "secret-check" in c["content"]
    ]
    assert secret_lines and "True" not in secret_lines[0]
    assert run["outputReferences"]
    output = kernel.executions.get_output(run["outputReferences"][0])
    assert output["name"] == "result.txt"
    after = kernel.executions.list_logs(run_id, after_sequence=logs["chunks"][0]["sequence"])
    assert all(c["sequence"] > logs["chunks"][0]["sequence"] for c in after["chunks"])


def test_snapshot_isolation_from_mutable_workspace() -> None:
    kernel, _, _, project_id = build_test_kernel()
    ctx = _prepare_scratch(kernel, project_id, {"data.txt": "snapshot-v1"})
    draft = kernel.kernel_store.get_draft(ctx["workspace"]["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=ctx["workspace"]["workspaceId"],
        path="data.txt",
        content=b"mutated-live",
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
        base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
        actor=ctx["actor"],
    )
    command = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", "print(open('data.txt').read())"],
        "workingDirectory": "",
        "environment": {},
        "declaredOutputs": [],
    }
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": command,
            },
            requested_by=ctx["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"])
    assert run["status"] == "completed"
    logs = kernel.executions.list_logs(result["executionRunId"])
    stdout = "".join(c["content"] for c in logs["chunks"] if c["stream"] == "stdout")
    assert "snapshot-v1" in stdout
    assert "mutated-live" not in stdout


def test_queued_cancel_and_running_timeout() -> None:
    kernel, _, _, project_id = build_test_kernel(
        execution_limits=ExecutionLimits(wall_time_ms=200),
        scheduler_config=SchedulerConfig(max_running_global=0, max_queued=8),
    )
    ctx = _prepare_scratch(kernel, project_id, {"README.md": "x"})
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": _fixture_command(sleep_s=0),
            },
            requested_by=ctx["actor"],
        )
    )
    run_id = result["executionRunId"]
    assert kernel.executions.get_run(run_id)["status"] == "queued"
    cancelled = kernel.executions.cancel(run_id, actor=ctx["actor"])
    assert cancelled["executionJob"]["status"] == "cancelled"
    assert cancelled["executionRun"]["status"] == "cancelled"

    kernel2, _, _, project_id2 = build_test_kernel(
        execution_limits=ExecutionLimits(wall_time_ms=200)
    )
    ctx2 = _prepare_scratch(kernel2, project_id2, {"README.md": "x"})
    result2 = kernel2.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx2["project_id"],
            artifact_id=ctx2["workspace"]["artifactId"],
            workspace_id=ctx2["workspace"]["workspaceId"],
            base_artifact_version=ctx2["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx2["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx2["snapshot_id"],
                "capability": "sandbox-execution",
                "maxDurationMs": 200,
                "commandSpec": _fixture_command(sleep_s=2.0, write_result=False),
            },
            requested_by=ctx2["actor"],
        )
    )
    run2 = _wait_run(kernel2, result2["executionRunId"], timeout=5.0)
    assert run2["status"] == "timed-out"


def test_undeclared_output_ignored_and_failed_nonzero() -> None:
    kernel, _, _, project_id = build_test_kernel()
    ctx = _prepare_scratch(kernel, project_id, {"README.md": "x"})
    command = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": [
            "-c",
            "open('undeclared.txt','w').write('nope'); open('result.txt','w').write('yes')",
        ],
        "workingDirectory": "",
        "environment": {},
        "declaredOutputs": [{"path": "result.txt", "kind": "result"}],
    }
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": command,
            },
            requested_by=ctx["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"])
    assert run["status"] == "completed"
    names = [kernel.executions.get_output(oid)["name"] for oid in run["outputReferences"]]
    assert names == ["result.txt"]

    fail_cmd = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", "raise SystemExit(7)"],
        "workingDirectory": "",
        "environment": {},
        "declaredOutputs": [],
    }
    result2 = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": fail_cmd,
            },
            requested_by=ctx["actor"],
        )
    )
    run2 = _wait_run(kernel, result2["executionRunId"])
    assert run2["status"] == "failed"


def test_forbidden_env_rejected() -> None:
    kernel, _, _, project_id = build_test_kernel()
    ctx = _prepare_scratch(kernel, project_id, {"README.md": "x"})
    bad = _fixture_command()
    bad["environment"] = {"WOKWI_CLI_TOKEN": "x"}
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=ctx["project_id"],
            artifact_id=ctx["workspace"]["artifactId"],
            workspace_id=ctx["workspace"]["workspaceId"],
            base_artifact_version=ctx["workspace"]["baseArtifactVersion"],
            base_project_state_version=ctx["workspace"]["baseProjectStateVersion"],
            input_data={
                "snapshotId": ctx["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": bad,
            },
            requested_by=ctx["actor"],
        )
    )
    assert result["status"] in {"conflicted", "failed", "rejected"}
