"""Phase 16B Analysis input upload/import tests."""

from __future__ import annotations

import time

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import CommandValidationError, WorkspaceQuotaExceededError


def _wait_run(kernel: object, run_id: str, *, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = kernel.executions.get_run(run_id)  # type: ignore[attr-defined]
        assert isinstance(run, dict)
        status = run.get("status")
        if status not in {"queued", "starting", "running", "cancelling"}:
            return run
        time.sleep(0.05)
    final = kernel.executions.get_run(run_id)  # type: ignore[attr-defined]
    assert isinstance(final, dict)
    return final


def test_analysis_input_upload_writes_under_data_and_sets_origin() -> None:
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

    write = kernel.workspace_runtime.write_analysis_input_file(
        project_id=project_id,
        artifact_type="analysis",
        path="data/user.txt",
        content=b"hello\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        media_type="text/plain",
    )
    assert write["file"]["path"] == "data/user.txt"

    read = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="analysis", path="data/user.txt"
    )
    assert read["content"] == b"hello\n"
    assert read["file"]["origin"] == "USER"


def test_analysis_input_upload_rejects_outside_data() -> None:
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

    with pytest.raises(CommandValidationError):
        kernel.workspace_runtime.write_analysis_input_file(
            project_id=project_id,
            artifact_type="analysis",
            path="src/user.txt",
            content=b"nope\n",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )


def test_analysis_input_upload_rejects_large_file() -> None:
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

    too_big = b"a" * 1_048_577
    with pytest.raises(WorkspaceQuotaExceededError):
        kernel.workspace_runtime.write_analysis_input_file(
            project_id=project_id,
            artifact_type="analysis",
            path="data/too-big.txt",
            content=too_big,
            actor=user,
            expected_draft_version=1,
            base_artifact_version=int(binding["baseArtifactVersion"]),
            base_project_state_version=int(binding["baseProjectStateVersion"]),
        )


def test_analysis_import_produced_output_into_data() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel()
    user = actor("user")

    code_binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="code-scratch", actor=user
    )

    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=code_binding["artifactId"],
        workspace_id=code_binding["workspaceId"],
        requested_by=user,
    )

    snapshot = kernel.workspace_runtime.create_snapshot(
        project_id=project_id,
        artifact_type="code-scratch",
        actor=user,
        reason="analysis-import-test",
    )
    command_spec = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": [
            "-c",
            "open('out.txt','w',encoding='utf-8').write('hello')",
        ],
        "workingDirectory": "",
        "environment": [],
        "declaredOutputs": [{"path": "out.txt", "kind": "result"}],
    }
    started = kernel.workspace_runtime.start_execution(
        project_id=project_id,
        artifact_type="code-scratch",
        snapshot_id=snapshot["snapshotId"],
        actor=user,
        command_spec=command_spec,
        base_artifact_version=int(code_binding["baseArtifactVersion"]),
        base_project_state_version=int(code_binding["baseProjectStateVersion"]),
    )
    run_id = started["executionRun"]["executionRunId"]
    final = _wait_run(kernel, run_id)
    assert final["status"] in {
        "completed",
        "completed-with-warnings",
        "failed",
        "cancelled",
    }  # pragma: no cover

    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=run_id
    )["outputs"]
    out = next(o for o in outputs if o["name"] == "out.txt")

    analysis_binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="analysis", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=analysis_binding["artifactId"],
        workspace_id=analysis_binding["workspaceId"],
        requested_by=user,
    )

    imported = kernel.workspace_runtime.import_produced_output_into_analysis_input(
        project_id=project_id,
        artifact_type="analysis",
        output_id=str(out["outputId"]),
        path="data/out.txt",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(analysis_binding["baseArtifactVersion"]),
        base_project_state_version=int(analysis_binding["baseProjectStateVersion"]),
    )
    assert imported["file"]["path"] == "data/out.txt"
    read = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="analysis", path="data/out.txt"
    )
    assert read["content"] == b"hello"
    assert read["file"]["origin"] == "RUNTIME_OUTPUT"
