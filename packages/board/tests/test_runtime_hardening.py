"""Phase 14C runtime hardening, recovery, GC, and capacity tests."""

from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel, cmd
from nexus_board.execution.failure_codes import RUNTIME_LOST, RUNTIME_UNAVAILABLE
from nexus_board.execution.job_service import ExecutionJobService
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.process_runtime import ProcessRuntime
from nexus_board.execution.runtime_factory import (
    RuntimeUnavailableError,
    build_execution_runtime,
    resolve_execution_runtime_kind,
)
from nexus_board.execution.scheduler import (
    ExecutionQueueFullError,
    InProcessExecutionScheduler,
    SchedulerConfig,
)
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.services.retention import RetentionPolicy, RetentionService
from nexus_persistence.file_store.memory import InMemoryFileStore


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


def _fixture_command(*, sleep_s: float = 0.0) -> dict[str, Any]:
    code = (
        "import os; print('NEXUS_RUNTIME_READY'); "
        "print('secret-check', 'WOKWI_CLI_TOKEN' in os.environ, "
        "'NEXUS_DATABASE_URL' in os.environ, 'AWS_SECRET_ACCESS_KEY' in os.environ, "
        "'OPENAI_API_KEY' in os.environ); "
        f"import time; time.sleep({sleep_s}); "
        "open('result.txt','w').write('ok')"
    )
    return {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", code],
        "workingDirectory": "",
        "environment": [],
        "declaredOutputs": [{"path": "result.txt", "kind": "result"}],
    }


def test_runtime_selection_no_silent_downgrade() -> None:
    assert resolve_execution_runtime_kind("process") == "process"
    assert resolve_execution_runtime_kind("container") == "container"
    with pytest.raises(RuntimeUnavailableError):
        resolve_execution_runtime_kind("wasm")
    with pytest.raises(RuntimeUnavailableError) as exc:
        build_execution_runtime("container", docker_executable="/nonexistent/docker-bin")
    assert exc.value.code == RUNTIME_UNAVAILABLE


def test_process_runtime_security_level_limited() -> None:
    avail = ProcessRuntime().availability()
    assert avail.security_level == "limited"
    assert avail.network_policy == "none"
    assert "no-network-isolation" in avail.isolation_limitations


def test_secret_sentinels_absent_from_process_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOKWI_CLI_TOKEN", "sentinel-wokwi")
    monkeypatch.setenv("NEXUS_DATABASE_URL", "sentinel-db")
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-model")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sentinel-aws")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "sentinel-nexus-model")
    kernel, _ps, _ks, project_id = build_test_kernel()
    prep = _prepare_scratch(kernel, project_id, {"main.py": "print(1)"})
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            base_artifact_version=prep["workspace"]["baseArtifactVersion"],
            base_project_state_version=prep["workspace"]["baseProjectStateVersion"],
            input_data={
                "capability": "sandbox-execution",
                "commandSpec": _fixture_command(),
                "snapshotId": prep["snapshot_id"],
            },
            requested_by=prep["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"])
    assert run["status"] in {"completed", "completed-with-warnings"}
    assert run["runtimeIdentity"]["securityLevel"] == "limited"
    logs = kernel.jobs.list_logs(run["executionRunId"])
    joined = "\n".join(c["content"] for c in logs["chunks"])
    assert "secret-check False False False False" in joined
    assert "sentinel-" not in joined


def test_cleanup_twice_is_safe() -> None:
    runtime = ProcessRuntime()
    runtime.cleanup("execjob_missing000001")
    runtime.cleanup("execjob_missing000001")


def test_stranded_running_job_recovered() -> None:
    kernel, _ps, ks, project_id = build_test_kernel(
        auto_start_scheduler=False,
        recover_jobs_on_start=False,
    )
    prep = _prepare_scratch(kernel, project_id, {"main.py": "x=1"})
    run_id = new_id("exec")
    job_id = new_id("execjob")
    now = utc_now_iso()
    run = {
        "schemaVersion": "1.0.0",
        "executionRunId": run_id,
        "executionRequestId": new_id("execreq"),
        "projectId": project_id,
        "artifactId": prep["workspace"]["artifactId"],
        "workspaceId": prep["workspace"]["workspaceId"],
        "providerId": "nexus-process-runtime",
        "capability": "sandbox-execution",
        "status": "running",
        "baseArtifactVersion": 1,
        "baseProjectStateVersion": 1,
        "inputSnapshotId": prep["snapshot_id"],
        "startedAt": now,
        "outputReferences": [],
        "evidenceReferences": [],
        "executionJobId": job_id,
    }
    job = {
        "schemaVersion": "1.0.0",
        "executionJobId": job_id,
        "executionRunId": run_id,
        "projectId": project_id,
        "workspaceSnapshotId": prep["snapshot_id"],
        "status": "running",
        "runtimeKind": "process",
        "runtimeIdentity": {
            "runtimeKind": "process",
            "runtimeVersion": "process-runtime/1.1.0",
            "workspaceSnapshotId": prep["snapshot_id"],
            "workspaceManifestDigest": "sha256:deadbeef",
            "commandSpecVersion": "1.0.0",
            "limits": ExecutionLimits().to_contract(),
            "securityLevel": "limited",
            "networkPolicy": "none",
        },
        "commandSpec": _fixture_command(),
        "limits": ExecutionLimits().to_contract(),
        "createdAt": now,
        "startedAt": now,
        "runtimeHandle": {"pid": 999999},
    }
    ks.create_execution_run(run)
    ks.create_execution_job(job)

    service = ExecutionJobService(
        ks,
        kernel.project_store,
        kernel.file_store,
        kernel.ledger,
        kernel.projection,
        runtime=ProcessRuntime(),
        auto_start=False,
        recover_on_start=True,
    )
    del service
    updated = ks.get_execution_job(job_id)
    assert updated["status"] == "failed"
    assert updated["failure"]["code"] == RUNTIME_LOST
    synced = ks.get_execution_run(run_id)
    assert synced["status"] == "failed"


def test_scheduler_health_and_queue_rejection() -> None:
    rejected = {"count": 0}

    def _noop(_job_id: str) -> None:
        time.sleep(0.2)

    sched = InProcessExecutionScheduler(
        SchedulerConfig(max_running_global=1, max_running_per_project=1, max_queued=1),
        on_dispatch=_noop,
    )
    sched.start()
    try:
        sched.enqueue("j1", "p1")
        # Fill queue while first is running or queued.
        time.sleep(0.05)
        try:
            sched.enqueue("j2", "p1")
        except ExecutionQueueFullError:
            rejected["count"] += 1
        health = sched.health()
        assert health["globalCapacity"] == 1
        assert health["perProjectCapacity"] == 1
        rejected_jobs = health["rejectedJobs"]
        assert isinstance(rejected_jobs, int)
        assert rejected_jobs >= rejected["count"]
        assert "queuedJobs" in health
        assert "runningJobs" in health
    finally:
        sched.stop(wait=False)


def test_gc_orphan_blob_and_protected_refs() -> None:
    kernel, _ps, ks, project_id = build_test_kernel(auto_start_scheduler=False)
    prep = _prepare_scratch(kernel, project_id, {"keep.py": "print('keep')"})
    store: InMemoryFileStore = kernel.file_store  # type: ignore[assignment]
    orphan = store.put(b"orphan-blob-bytes")
    referenced = ks.list_referenced_content_hashes()
    assert orphan not in referenced

    # Large produced output storage-reference must protect its blob.
    big = b"x" * 2048
    out_hash = store.put(big)
    ks.create_produced_output(
        {
            "schemaVersion": "1.0.0",
            "outputId": new_id("out"),
            "projectId": project_id,
            "artifactId": prep["workspace"]["artifactId"],
            "workspaceId": prep["workspace"]["workspaceId"],
            "executionRunId": new_id("exec"),
            "providerId": "nexus-process-runtime",
            "outputType": "file-reference",
            "name": "big.bin",
            "mediaType": "application/octet-stream",
            "content": {
                "kind": "storage-reference",
                "storageKind": "file-store",
                "uri": out_hash,
            },
            "contentDigest": out_hash,
            "createdAt": utc_now_iso(),
            "evidenceStatus": "unverified",
            "supports": [],
            "provenance": {
                "schemaVersion": "1.0.0",
                "sourceType": "external-provider",
                "sourceReference": "test",
                "derivedFromIds": [],
            },
        }
    )
    assert out_hash in ks.list_referenced_content_hashes()

    retention = RetentionService(
        ks,
        store,
        policy=RetentionPolicy(
            reclaimable_snapshot_max_age_seconds=0,
            terminal_log_max_age_seconds=0,
        ),
    )
    plan = retention.plan()
    reclaimable_ids = {c.id for c in plan.reclaimable() if c.kind == "blob"}
    assert orphan in reclaimable_ids
    assert out_hash not in reclaimable_ids
    dry = retention.apply(plan, dry_run=True)
    assert dry["dryRun"] is True
    assert store.exists(orphan)

    applied = retention.apply(plan, dry_run=False)
    assert any(d["id"] == orphan for d in applied["deleted"])
    assert not store.exists(orphan)
    assert store.exists(out_hash)

    # Idempotent second pass.
    again = retention.apply(dry_run=False)
    assert orphan not in {d["id"] for d in again["deleted"]}


def test_gc_reclaimable_snapshot_vs_protected() -> None:
    kernel, _ps, ks, project_id = build_test_kernel(auto_start_scheduler=False)
    prep = _prepare_scratch(kernel, project_id, {"a.py": "a=1"})
    # Create a second snapshot then clear workspace current pointer by writing files
    # and snapshotting again — older snap may still be protected by currentSnapshotId
    # unless we reclaim an abandoned one with no refs.
    user = prep["actor"]
    ws = prep["workspace"]
    written = kernel.filesystem.write_file(
        workspace_id=ws["workspaceId"],
        path="b.py",
        content=b"b=2",
        expected_draft_version=2,
        base_artifact_version=ws["baseArtifactVersion"],
        base_project_state_version=ws["baseProjectStateVersion"],
        actor=user,
    )
    snap2 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=ws["artifactId"],
            workspace_id=ws["workspaceId"],
            base_artifact_version=ws["baseArtifactVersion"],
            base_project_state_version=ws["baseProjectStateVersion"],
            input_data={"reason": "second"},
            requested_by=user,
        )
    )
    assert snap2["status"] == "completed"
    del written

    # Manually insert an unreferenced filesystem snapshot with old createdAt.
    orphan_snap_id = new_id("snap")
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    manifest = {
        "schemaVersion": "1.0.0",
        "manifestDigest": "sha256:" + ("ab" * 32),
        "entries": [],
        "totalBytes": 0,
        "fileCount": 0,
    }
    ks.create_snapshot(
        {
            "schemaVersion": "1.0.0",
            "snapshotId": orphan_snap_id,
            "workspaceId": ws["workspaceId"],
            "projectId": project_id,
            "artifactId": ws["artifactId"],
            "snapshotVersion": 99,
            "createdAt": old,
            "createdBy": user,
            "content": {"kind": "filesystem", "filesystemManifest": manifest},
        }
    )
    retention = RetentionService(
        ks,
        kernel.file_store,
        policy=RetentionPolicy(reclaimable_snapshot_max_age_seconds=0),
    )
    protected = retention.protected_snapshot_ids()
    assert prep["snapshot_id"] in protected or snap2["snapshotId"] in protected
    assert orphan_snap_id not in protected
    plan = retention.plan()
    reclaim = [c for c in plan.reclaimable() if c.id == orphan_snap_id]
    assert reclaim
    retention.apply(plan, dry_run=False)
    with pytest.raises(Exception):
        ks.get_snapshot(orphan_snap_id)


def test_kernel_health_exposes_runtime() -> None:
    kernel, *_rest = build_test_kernel(auto_start_scheduler=False)
    health = kernel.jobs.health()
    assert health["runtimeAvailability"]["runtimeKind"] == "process"
    assert health["runtimeAvailability"]["securityLevel"] == "limited"
    assert "queuedJobs" in health
    assert "rejectedJobs" in health


@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_INTEGRATION", "0") != "1" or shutil.which("docker") is None,
    reason="Docker integration disabled (set RUN_DOCKER_INTEGRATION=1)",
)
def test_container_runtime_isolation_smoke() -> None:
    image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "python:3.13-slim")
    pull = __import__("subprocess").run(
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert pull.returncode == 0, (pull.stderr or pull.stdout)[:500]

    runtime = build_execution_runtime("container", container_image=image)
    avail = runtime.availability()
    assert avail.available
    assert avail.security_level == "isolated"
    assert "network-none" in avail.isolation_guarantees

    kernel, _ps, _ks, project_id = build_test_kernel(
        execution_runtime=runtime,
        execution_limits=ExecutionLimits(
            wall_time_ms=20_000,
            memory_bytes=128 * 1024 * 1024,
            cpu_millis=500,
            process_count=32,
            stdout_bytes=65_536,
            stderr_bytes=65_536,
            total_log_bytes=131_072,
            produced_output_bytes=65_536,
            workspace_bytes=1_048_576,
            output_file_count=8,
        ),
    )
    prep = _prepare_scratch(kernel, project_id, {"main.py": "print(1)"})
    ok_cmd = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": [
            "-c",
            "print('NEXUS_RUNTIME_READY'); open('result.txt','w').write('ok')",
        ],
        "workingDirectory": "",
        "environment": [{"name": "SAFE_FLAG", "value": "1"}],
        "declaredOutputs": [{"path": "result.txt", "kind": "result"}],
    }
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            base_artifact_version=prep["workspace"]["baseArtifactVersion"],
            base_project_state_version=prep["workspace"]["baseProjectStateVersion"],
            input_data={
                "capability": "sandbox-execution",
                "commandSpec": ok_cmd,
                "snapshotId": prep["snapshot_id"],
            },
            requested_by=prep["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"], timeout=120.0)
    assert run["status"] in {"completed", "completed-with-warnings"}, run
    assert run["runtimeIdentity"]["securityLevel"] == "isolated"
    assert run["runtimeIdentity"].get("imageDigest")

    # Network should fail inside --network none.
    net_cmd = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": [
            "-c",
            "import socket; socket.create_connection(('1.1.1.1', 80), 2)",
        ],
        "workingDirectory": "",
        "environment": [],
        "declaredOutputs": [],
    }
    result2 = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            base_artifact_version=prep["workspace"]["baseArtifactVersion"],
            base_project_state_version=prep["workspace"]["baseProjectStateVersion"],
            input_data={
                "capability": "sandbox-execution",
                "commandSpec": net_cmd,
                "snapshotId": prep["snapshot_id"],
            },
            requested_by=prep["actor"],
        )
    )
    run2 = _wait_run(kernel, result2["executionRunId"], timeout=60.0)
    assert run2["status"] == "failed", run2
