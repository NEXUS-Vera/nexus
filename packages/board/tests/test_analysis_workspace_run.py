"""Phase 16D analysis.run snapshot-based execution tests."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.analysis.toolchain import (
    ANALYSIS_RUN_OPERATION,
    SNAPSHOT_REASON_BEFORE_RUN,
    build_analysis_command_spec,
)
from nexus_board.errors import CommandValidationError
from nexus_board.services.workspace_runtime import WorkspaceRuntimeCapabilityError


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 8.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run: dict[str, Any] = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running"}:
            return run
        time.sleep(0.05)
    return kernel.executions.get_run(run_id)


def _setup_scaffolded_analysis(
    kernel: Any, project_id: str, user: dict[str, Any]
) -> dict[str, Any]:
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    kernel.workspace_runtime.generate_analysis_scaffold(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    return dict(binding)


def test_run_command_spec_is_approved_and_fixed() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    spec = build_analysis_command_spec()
    assert spec["executable"] == "python3"
    assert spec["arguments"]
    paths = {item["path"] for item in spec["declaredOutputs"]}
    assert "outputs/results.json" in paths


def test_run_creates_snapshot_and_succeeds_with_stub() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = _setup_scaffolded_analysis(kernel, project_id, user)

    started = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    assert started["operation"] == ANALYSIS_RUN_OPERATION
    snap_id = started["executionSnapshotId"]
    run_id = started["executionRun"]["executionRunId"]

    snapshots = kernel_store.list_snapshots(binding["workspaceId"])
    assert any(
        s["snapshotId"] == snap_id and s["reason"] == SNAPSHOT_REASON_BEFORE_RUN for s in snapshots
    )

    run = _wait_run(kernel, run_id)
    assert run["status"] == "completed"
    assert run["inputSnapshotId"] == snap_id

    logs = kernel.executions.list_logs(run_id, after_sequence=0, limit=200)
    text = "".join(chunk["content"] for chunk in logs["chunks"])
    assert "SUCCESS" in text


def test_run_fails_if_no_analysis_py() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    # Write a file that is NOT analysis.py.
    kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/notes.txt",
        content=b"no entrypoint here\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    with pytest.raises((CommandValidationError, Exception)):
        kernel.workspace_runtime.run_analysis(
            project_id=project_id,
            artifact_type="analysis",
            actor=user,
        )


def test_run_denied_for_non_analysis_artifact() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    with pytest.raises(WorkspaceRuntimeCapabilityError):
        kernel.workspace_runtime.run_analysis(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
        )


def test_rerun_against_existing_snapshot() -> None:
    os.environ["NEXUS_ANALYSIS_USE_STUB"] = "1"
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    _setup_scaffolded_analysis(kernel, project_id, user)

    # First run — produces an execution snapshot.
    first = kernel.workspace_runtime.run_analysis(
        project_id=project_id,
        artifact_type="analysis",
        actor=user,
    )
    snap_id = first["executionSnapshotId"]
    _wait_run(kernel, first["executionRun"]["executionRunId"])

    # Rerun against the same immutable snapshot.
    rerun = kernel.workspace_runtime.rerun_analysis(
        project_id=project_id,
        artifact_type="analysis",
        snapshot_id=snap_id,
        actor=user,
    )
    assert rerun["rerun"] is True
    assert rerun["executionSnapshotId"] == snap_id
    rerun_id = rerun["executionRun"]["executionRunId"]
    assert rerun_id != first["executionRun"]["executionRunId"]

    run = _wait_run(kernel, rerun_id)
    assert run["status"] == "completed"
    assert run["inputSnapshotId"] == snap_id


def test_analysis_defaults_to_python_and_labels_explicit_fixture(monkeypatch):
    from nexus_board.analysis.toolchain import (
        analysis_toolchain_profile,
        build_analysis_command_spec,
    )

    monkeypatch.delenv("NEXUS_ANALYSIS_USE_STUB", raising=False)
    assert build_analysis_command_spec()["arguments"] == ["analysis.py"]
    assert analysis_toolchain_profile()["executionMode"] == "python"
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "1")
    assert "analysis_stub.py" in build_analysis_command_spec()["arguments"][0]
    assert analysis_toolchain_profile()["executionMode"] == "fixture"
