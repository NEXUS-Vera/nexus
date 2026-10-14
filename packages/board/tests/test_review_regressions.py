"""N20/N21 review regressions, mapped to N32 fix-plan finding IDs."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from helpers import actor, build_test_kernel
from nexus_board.errors import BoardError
from nexus_board.execution.container_runtime import LocalContainerRuntime
from nexus_board.execution.job_service import ExecutionJobService
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.materialize import materialize_filesystem_snapshot
from nexus_board.execution.process_runtime import (
    OutputCollectionError,
    ProcessRuntime,
    collect_declared_outputs,
)
from nexus_board.execution.runtime_protocol import RuntimeExecuteRequest
from nexus_board.firmware.live_patch_generator import _run_sync
from nexus_board.firmware.toolchain import _pio_executable_and_args
from nexus_board.services.filesystem_service import build_filesystem_manifest
from nexus_board.services.workspace_runtime import WorkspaceRuntimeService
from nexus_persistence.file_store.memory import InMemoryFileStore


@pytest.mark.parametrize("parent", [False, True])
def test_f01_output_symlink_rejected(tmp_path: Path, parent: bool) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real/file").write_bytes(b"secret")
    (tmp_path / "link").symlink_to(tmp_path / "real" if parent else tmp_path / "real/file")
    with pytest.raises(OutputCollectionError, match="Symlink"):
        collect_declared_outputs(
            workspace_root=tmp_path,
            declared=[{"path": "link/file" if parent else "link", "kind": "artifact"}],
            limits=ExecutionLimits(),
        )


def test_f02_oversized_output_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "large").write_bytes(b"x" * 32)
    monkeypatch.setattr(Path, "open", Mock(side_effect=AssertionError("oversized file opened")))
    with pytest.raises(OutputCollectionError, match="exceed"):
        collect_declared_outputs(
            workspace_root=tmp_path,
            declared=[{"path": "large", "kind": "artifact"}],
            limits=ExecutionLimits(produced_output_bytes=16),
        )


def test_f01_materialization_rejects_existing_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = InMemoryFileStore()
    digest = files.put(b"new")
    records = [
        {
            "path": "link",
            "contentHash": digest,
            "contentReference": "cas:" + digest,
            "sizeBytes": 3,
            "origin": "USER",
            "writePolicy": "USER_EDITABLE",
            "modifiedByUser": False,
        }
    ]
    manifest = build_filesystem_manifest(records)
    root = tmp_path / "root"
    root.mkdir()
    (root / "real").write_bytes(b"old")
    (root / "link").symlink_to(root / "real")
    monkeypatch.setattr(
        "nexus_board.execution.materialize.tempfile.mkdtemp", lambda **kw: str(root)
    )
    store = Mock()
    store.get_snapshot.return_value = {
        "content": {"kind": "filesystem", "filesystemManifest": manifest}
    }
    with pytest.raises(BoardError, match="symlink"):
        materialize_filesystem_snapshot(
            kernel_store=store, file_store=files, snapshot_id="snap", workspace_bytes_limit=100
        )


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("finding", ["identity", "logs"])
def test_f03_f04_container_identity_and_log_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool, finding: str
) -> None:
    runtime = LocalContainerRuntime()
    monkeypatch.setattr(runtime, "availability", lambda: SimpleNamespace(available=True))
    monkeypatch.setattr(runtime, "resolve_image_digest", lambda: ("image", "sha256:test"))
    calls: list[list[str]] = []

    def docker(args: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(
            args, 0, "cid" if args[0] == "run" else "retained logs", ""
        )

    monkeypatch.setattr(runtime, "_docker_run", docker)
    result = runtime.execute(
        RuntimeExecuteRequest(
            job_id="job",
            workspace_root=tmp_path,
            command_spec={"executable": "python3"},
            limits=ExecutionLimits(wall_time_ms=0),
            cancel_check=lambda: cancel,
        )
    )
    run = calls[0]
    if finding == "identity":
        assert run[run.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
        assert tmp_path.stat().st_mode & 0o077 == 0
        return
    actions = [c[0] for c in calls]
    assert actions.index("kill") < actions.index("logs") < actions.index("rm")
    assert result.stdout == "retained logs"


def test_f07_inherited_pipe_respects_deadline(tmp_path: Path) -> None:
    runtime = ProcessRuntime()
    handle: dict[str, int] = {}
    result: list[object] = []
    request = RuntimeExecuteRequest(
        job_id="drain",
        workspace_root=tmp_path,
        command_spec={
            "executable": "python3",
            "arguments": ["-c", "import subprocess; subprocess.Popen(['sleep', '3'])"],
        },
        limits=ExecutionLimits(wall_time_ms=150),
        on_started=lambda h: handle.update(h),
    )
    worker = threading.Thread(target=lambda: result.append(runtime.execute(request)), daemon=True)
    started = time.monotonic()
    worker.start()
    worker.join(1)
    elapsed = time.monotonic() - started
    if worker.is_alive():
        os.killpg(handle["pid"], signal.SIGKILL)
        worker.join(2)
    assert elapsed < 0.8
    assert result[0].status == "timed-out"  # type: ignore[attr-defined]


def test_f08_discard_rejects_other_workspace() -> None:
    service = object.__new__(WorkspaceRuntimeService)
    service._require_binding = Mock(
        return_value={
            "workspaceId": "bound",
            "schemaVersion": "1.0.0",
            "projectId": "project",
            "artifactId": "art",
            "artifactType": "firmware",
            "capabilities": {},
            "requiredCapabilities": [],
            "filesystemEnabled": True,
        }
    )
    service._ledger = None
    service._kernel = Mock()
    service._kernel.get_firmware_patch_proposal.return_value = {
        "projectId": "project",
        "workspaceId": "other",
        "status": "proposed",
    }
    with pytest.raises(BoardError, match="workspace"):
        service.discard_firmware_patch(
            project_id="project", artifact_type="firmware", proposal_id="proposal", actor=actor()
        )
    service._kernel.update_firmware_patch_proposal.assert_not_called()


def test_f10_base_exception_propagates_without_hang() -> None:
    async def cancelled() -> None:
        raise asyncio.CancelledError()

    failures: list[BaseException] = []

    def invoke() -> None:
        try:
            _run_sync(cancelled())
        except BaseException as exc:
            failures.append(exc)

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    worker.join(0.5)
    assert not worker.is_alive()
    assert isinstance(failures[0], asyncio.CancelledError)


def test_f10_sync_bridge_timeout() -> None:
    async def slow() -> None:
        await asyncio.sleep(2)

    with pytest.raises(TimeoutError):
        _run_sync(slow(), timeout_seconds=0.02)


def test_f12_available_pio_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXUS_FIRMWARE_USE_STUB", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: "/bin/pio")
    assert _pio_executable_and_args("compile") == ("pio", ["run", "-e", "nexus"])


def test_f05_cleanup_once() -> None:
    service = object.__new__(ExecutionJobService)
    service._kernel = Mock()
    service._kernel.get_execution_job.return_value = {}
    service._runtime = Mock()
    service.cleanup_job("job")
    service._runtime.cleanup.assert_called_once_with("job", handle={})


def test_f16_binding_preserves_actor() -> None:
    kernel, _, _, project_id = build_test_kernel()
    user = actor()
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    assert binding["draft"]["updatedBy"] == user


def test_f06_failed_rename_preserves_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from test_filesystem_workspace import _create_code_workspace

    kernel, _, store, project_id = build_test_kernel()
    user = actor()
    ws = _create_code_workspace(kernel, project_id, user)["workspace"]
    written = kernel.filesystem.write_file(
        workspace_id=ws["workspaceId"],
        path="source",
        content=b"keep",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    monkeypatch.setattr(
        store, "upsert_workspace_file", Mock(side_effect=RuntimeError("storage failure"))
    )
    with pytest.raises(RuntimeError, match="storage failure"):
        kernel.filesystem.rename_file(
            workspace_id=ws["workspaceId"],
            from_path="source",
            to_path="dest",
            actor=user,
            expected_draft_version=written["draft"]["draftVersion"],
            base_artifact_version=1,
            base_project_state_version=1,
        )
    assert kernel.filesystem.read_file(ws["workspaceId"], "source")["content"] == b"keep"


@pytest.mark.parametrize("invalid", ["type", "count", "size", "duplicate"])
def test_f15_restore_guards(invalid: str) -> None:
    from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits
    from nexus_board.services.filesystem_service import FilesystemWorkspaceService

    service = object.__new__(FilesystemWorkspaceService)
    service._kernel = Mock()
    service._kernel.get_workspace.return_value = {
        "workspaceType": "metadata" if invalid == "type" else "filesystem"
    }
    service._files = Mock()
    service._limits = WorkspaceFilesystemLimits(max_file_count=2, max_file_bytes=16)
    entry = {
        "path": "file",
        "contentHash": "sha256:" + "a" * 64,
        "sizeBytes": 32 if invalid == "size" else 1,
        "origin": "USER",
        "writePolicy": "USER_EDITABLE",
    }
    entries = (
        [dict(entry, path=f"file{index}") for index in range(3)]
        if invalid == "count"
        else [entry] * (2 if invalid == "duplicate" else 1)
    )
    with pytest.raises(BoardError):
        service.restore_filesystem_manifest(
            workspace_id="ws", manifest={"entries": entries}, actor=actor()
        )
    service._kernel.replace_workspace_files.assert_not_called()
    if invalid in {"type", "count", "size"}:
        service._files.exists.assert_not_called()


def test_f13_submit_never_overwrites_worker_state() -> None:
    service = object.__new__(ExecutionJobService)
    service._runtime = ProcessRuntime()
    service._kernel = Mock()
    service._defaults = ExecutionLimits()
    service._scheduler = Mock()
    jobs: dict[str, dict] = {}
    runs = {"run": {"executionRunId": "run", "projectId": "project", "status": "queued"}}
    service._kernel.create_execution_job.side_effect = lambda j: jobs.update(
        {j["executionJobId"]: dict(j)}
    )
    service._kernel.update_execution_job.side_effect = lambda j: jobs.update(
        {j["executionJobId"]: dict(j)}
    )
    service._kernel.get_execution_job.side_effect = lambda i: dict(jobs[i])
    service._kernel.update_execution_status.side_effect = lambda i, r: runs.update({i: dict(r)})
    service._kernel.get_execution_run.side_effect = lambda i: dict(runs[i])

    def enqueue(job_id: str, project_id: str, *, on_enqueued=None) -> int:
        if on_enqueued:
            on_enqueued(1)
        jobs[job_id]["status"] = "running"
        runs["run"]["status"] = "running"
        return 1

    service._scheduler.enqueue.side_effect = enqueue
    service.submit(
        run=runs["run"],
        snapshot={
            "snapshotId": "snap",
            "content": {"kind": "filesystem", "filesystemManifest": {"manifestDigest": "digest"}},
        },
        command_spec={
            "schemaVersion": "1.0.0",
            "executable": "python3",
            "arguments": [],
            "environment": [],
            "declaredOutputs": [],
        },
        actor=actor(),
    )
    assert next(iter(jobs.values()))["status"] == "running"
    assert runs["run"]["status"] == "running"


@pytest.mark.parametrize("dispatch", [False, True])
def test_f14_queued_cancel_finalizes(dispatch: bool) -> None:
    service = object.__new__(ExecutionJobService)
    service._kernel = Mock()
    job = {"executionJobId": "job", "executionRunId": "run", "status": "queued"}
    service._kernel.get_execution_job.return_value = job
    service._kernel.get_execution_job_by_run.return_value = job
    service._kernel.get_execution_run.return_value = {
        "executionRunId": "run",
        "projectId": "project",
        "baseProjectStateVersion": 1,
    }
    service._scheduler = Mock()
    service._scheduler.is_cancel_requested.return_value = True
    service._projects = Mock()
    service._projects.get_project.return_value = {"currentStateVersion": 1}
    service._ledger = Mock()
    service._projection = Mock()
    if dispatch:
        service._dispatch_job("job")
    else:
        service.cancel("run")
    service._ledger.append.assert_called_once()
    assert service._ledger.append.call_args.kwargs["event_type"] == "execution.failed"
    assert service._ledger.append.call_args.kwargs["subject_id"] == "run"
    service._projection.update_after_write.assert_called_once_with("project")


def test_f05_materialization_cleanup_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from nexus_board.execution import job_service

    service = object.__new__(ExecutionJobService)
    service._kernel = Mock()
    service._kernel.get_execution_job.return_value = {
        "executionJobId": "job",
        "executionRunId": "run",
        "status": "queued",
    }
    service._kernel.get_execution_run.return_value = {}
    service._scheduler = Mock()
    service._scheduler.is_cancel_requested.return_value = False
    service._runtime = Mock()
    service._runtime.availability.return_value = SimpleNamespace(
        available=False, unavailable_reason="unavailable"
    )
    service._finalize_run = Mock()
    service._cancel_flags = {}
    service._log_bytes = {}
    service._log_seq = {}
    cleanup = Mock()
    monkeypatch.setattr(job_service, "cleanup_materialization", cleanup)
    service._dispatch_job("job")
    cleanup.assert_called_once_with(None)
