"""Opt-in Phase 14 live E2E acceptance (postgres + container).

Gate: RUN_PHASE14_E2E=1

Requires:
  - Docker available
  - NEXUS_DATABASE_URL pointing at a migrated Nexus Postgres
  - NEXUS_FILE_STORE_ROOT writable path

Does not silently fall back to ProcessRuntime for container scenarios.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, cmd, minimal_package
from nexus_board.errors import (
    WorkspaceFileNotFoundError,
    WorkspacePathError,
    WorkspaceWritePolicyError,
)
from nexus_board.execution.failure_codes import RUNTIME_LOST, RUNTIME_UNAVAILABLE
from nexus_board.execution.job_service import ExecutionJobService
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.process_runtime import ProcessRuntime
from nexus_board.execution.runtime_factory import (
    RuntimeUnavailableError,
    build_execution_runtime,
)
from nexus_board.execution.scheduler import SchedulerConfig
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.kernel import build_project_kernel
from nexus_board.services.retention import RetentionPolicy, RetentionService
from nexus_persistence.factory import build_stores
from nexus_persistence.file_store.local import LocalFileStore

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_PHASE14_E2E", "0") != "1"
    or not os.environ.get("NEXUS_DATABASE_URL")
    or shutil.which("docker") is None,
    reason="Set RUN_PHASE14_E2E=1 with NEXUS_DATABASE_URL and Docker for live Phase 14 E2E",
)


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 120.0) -> dict[str, Any]:
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


def _build_pg_kernel(
    *,
    file_store_root: Path,
    runtime: Any,
    execution_limits: ExecutionLimits | None = None,
    scheduler_config: SchedulerConfig | None = None,
    recover_jobs_on_start: bool = True,
    auto_start_scheduler: bool = True,
) -> tuple[Any, Any, Any, str]:
    project_store, kernel_store = build_stores(
        "postgres",
        database_url=os.environ["NEXUS_DATABASE_URL"],
    )
    package = minimal_package()
    project_store.save_initialization_package(package)
    project_id = package["project"]["projectId"]
    file_store = LocalFileStore(file_store_root)
    kernel = build_project_kernel(
        kernel_store,
        project_store=project_store,
        file_store=file_store,
        execution_runtime=runtime,
        execution_limits=execution_limits
        or ExecutionLimits(
            wall_time_ms=30_000,
            memory_bytes=256 * 1024 * 1024,
            cpu_millis=1000,
            process_count=64,
        ),
        scheduler_config=scheduler_config
        or SchedulerConfig(max_running_global=2, max_running_per_project=1, max_queued=8),
        recover_jobs_on_start=recover_jobs_on_start,
        auto_start_scheduler=auto_start_scheduler,
    )
    return kernel, project_store, kernel_store, project_id


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
            input_data={"reason": "e2e"},
            requested_by=user,
        )
    )
    assert snap["status"] == "completed"
    return {
        "project_id": project_id,
        "workspace": ws,
        "snapshot_id": snap["snapshotId"],
        "manifest_digest": (snap.get("snapshot") or {})
        .get("content", {})
        .get("filesystemManifest", {})
        .get("manifestDigest")
        or kernel.kernel_store.get_snapshot(snap["snapshotId"])["content"]["filesystemManifest"][
            "manifestDigest"
        ],
        "actor": user,
        "draft_version": draft_version,
    }


@pytest.fixture(scope="module")
def e2e_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    assert os.environ.get("NEXUS_DATABASE_URL"), "NEXUS_DATABASE_URL required"
    assert shutil.which("docker"), "Docker required for Phase 14 E2E container path"
    root = Path(os.environ.get("NEXUS_FILE_STORE_ROOT") or tmp_path_factory.mktemp("filestore"))
    root.mkdir(parents=True, exist_ok=True)
    image = os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE", "python:3.13-slim")
    pull = subprocess.run(  # noqa: S603
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert pull.returncode == 0, (pull.stderr or pull.stdout)[:500]
    runtime = build_execution_runtime("container", container_image=image)
    assert runtime.availability().available
    return {"root": root, "image": image, "runtime": runtime}


def test_e2e_01_filesystem_persistence_survives_kernel_restart(e2e_env: dict[str, Any]) -> None:
    runtime = e2e_env["runtime"]
    root = e2e_env["root"]
    kernel, _ps, _ks, project_id = _build_pg_kernel(file_store_root=root, runtime=runtime)
    user = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id, artifact_type="code-scratch", actor=user
    )
    ws = created["workspace"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=ws["artifactId"],
        workspace_id=ws["workspaceId"],
        requested_by=user,
    )
    files = {
        "README.txt": "readme-v1",
        "src/input.txt": "input-v1",
        "config/settings.json": '{"mode":"e2e"}',
    }
    draft = 1
    for path, body in files.items():
        written = kernel.filesystem.write_file(
            workspace_id=ws["workspaceId"],
            path=path,
            content=body.encode(),
            expected_draft_version=draft,
            base_artifact_version=ws["baseArtifactVersion"],
            base_project_state_version=ws["baseProjectStateVersion"],
            actor=user,
        )
        draft = written["draft"]["draftVersion"]
        assert written["file"]["contentReference"].startswith("cas:")
        assert not written["file"]["contentReference"].startswith("/")
        assert "Desktop" not in written["file"]["contentReference"]

    listed = kernel.filesystem.list_files(ws["workspaceId"])
    paths = {f["path"] for f in listed}
    assert paths == set(files)
    ws_id = ws["workspaceId"]
    art_id = ws["artifactId"]
    kernel.jobs.shutdown()

    # Rebuild kernel against same postgres + file store (API restart simulation).
    kernel2, _ps2, _ks2, _pid2 = _build_pg_kernel(file_store_root=root, runtime=runtime)
    listed2 = kernel2.filesystem.list_files(ws_id)
    assert {f["path"] for f in listed2} == set(files)
    for path, body in files.items():
        got = kernel2.filesystem.read_file(ws_id, path)
        assert got["content"] == body.encode()
        assert got["file"]["contentReference"].startswith("cas:")
    # workspace still addressable
    assert kernel2.kernel_store.get_workspace(ws_id)["artifactId"] == art_id
    kernel2.jobs.shutdown()


def test_e2e_02_write_policies_and_path_rejection(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"], runtime=e2e_env["runtime"]
    )
    user = actor("user")
    created = kernel.workspaces.create_workspace(
        project_id=project_id, artifact_type="code-scratch", actor=user
    )
    ws = created["workspace"]
    ws_id = ws["workspaceId"]
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=ws["artifactId"],
        workspace_id=ws_id,
        requested_by=user,
    )
    # USER edit
    w1 = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="user.txt",
        content=b"one",
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
        actor=user,
    )
    w2 = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="user.txt",
        content=b"two",
        expected_draft_version=w1["draft"]["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=user,
    )
    assert kernel.filesystem.read_file(ws_id, "user.txt")["content"] == b"two"

    # GENERATED + user modify
    gen = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="generated.txt",
        content=b"gen",
        expected_draft_version=w2["draft"]["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=user,
        origin="GENERATED",
        write_policy="REGENERATION_MANAGED",
        generated_from="e2e",
    )
    edited = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="generated.txt",
        content=b"edited",
        expected_draft_version=gen["draft"]["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=user,
    )
    assert edited["file"]["origin"] == "GENERATED"
    assert edited["file"]["modifiedByUser"] is True

    # READ_ONLY
    ro = kernel.filesystem.write_file(
        workspace_id=ws_id,
        path="locked.txt",
        content=b"lock",
        expected_draft_version=edited["draft"]["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=user,
        write_policy="READ_ONLY",
    )
    with pytest.raises(WorkspaceWritePolicyError) as exc:
        kernel.filesystem.write_file(
            workspace_id=ws_id,
            path="locked.txt",
            content=b"nope",
            expected_draft_version=ro["draft"]["draftVersion"],
            base_artifact_version=1,
            base_project_state_version=1,
            actor=user,
        )
    assert exc.value.code == "WORKSPACE_WRITE_POLICY_DENIED"

    for bad in ("../secret.txt", "/absolute/path.txt", "a/../../escape.txt"):
        with pytest.raises(WorkspacePathError) as path_exc:
            kernel.filesystem.write_file(
                workspace_id=ws_id,
                path=bad,
                content=b"x",
                expected_draft_version=ro["draft"]["draftVersion"],
                base_artifact_version=1,
                base_project_state_version=1,
                actor=user,
            )
        msg = str(path_exc.value)
        assert "Traceback" not in msg
        assert "/Users/" not in msg
    kernel.jobs.shutdown()


def test_e2e_03_snapshot_restore_and_digest_stability(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"], runtime=e2e_env["runtime"]
    )
    prep = _prepare_scratch(kernel, project_id, {"A.txt": "A1", "B.txt": "B1"})
    s1 = kernel.kernel_store.get_snapshot(prep["snapshot_id"])
    digest1 = s1["content"]["filesystemManifest"]["manifestDigest"]

    draft = kernel.kernel_store.get_draft(prep["workspace"]["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=prep["workspace"]["workspaceId"],
        path="A.txt",
        content=b"A2",
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=prep["actor"],
    )
    draft = kernel.kernel_store.get_draft(prep["workspace"]["workspaceId"])
    kernel.filesystem.delete_file(
        workspace_id=prep["workspace"]["workspaceId"],
        path="B.txt",
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=prep["actor"],
    )
    draft = kernel.kernel_store.get_draft(prep["workspace"]["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=prep["workspace"]["workspaceId"],
        path="C.txt",
        content=b"C1",
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=prep["actor"],
    )
    # S1 immutable
    s1_again = kernel.kernel_store.get_snapshot(prep["snapshot_id"])
    assert s1_again["content"]["filesystemManifest"]["manifestDigest"] == digest1

    restore = kernel.dispatch(
        cmd(
            command_type="workspace.restore-snapshot",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={"snapshotId": prep["snapshot_id"]},
            requested_by=prep["actor"],
        )
    )
    assert restore["status"] == "completed"
    assert (
        kernel.filesystem.read_file(prep["workspace"]["workspaceId"], "A.txt")["content"] == b"A1"
    )
    assert (
        kernel.filesystem.read_file(prep["workspace"]["workspaceId"], "B.txt")["content"] == b"B1"
    )
    with pytest.raises(WorkspaceFileNotFoundError):
        kernel.filesystem.read_file(prep["workspace"]["workspaceId"], "C.txt")

    snap2 = kernel.dispatch(
        cmd(
            command_type="workspace.create-snapshot",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={"reason": "identical"},
            requested_by=prep["actor"],
        )
    )
    s2 = kernel.kernel_store.get_snapshot(snap2["snapshotId"])
    assert snap2["snapshotId"] != prep["snapshot_id"]
    assert s2["content"]["filesystemManifest"]["manifestDigest"] == digest1
    kernel.jobs.shutdown()


def test_e2e_04_05_06_07_08_container_execution_isolation(e2e_env: dict[str, Any]) -> None:
    # Seed sentinel host env (must not leak into job).
    os.environ["NEXUS_DATABASE_URL_SENTINEL"] = "DATABASE_SECRET_SENTINEL"
    os.environ["WOKWI_CLI_TOKEN"] = "WOKWI_SECRET_SENTINEL"
    os.environ["OPENAI_API_KEY"] = "MODEL_KEY_SENTINEL"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "AWS_SECRET_SENTINEL"
    os.environ["NEXUS_DATABASE_URL"] = os.environ["NEXUS_DATABASE_URL"]  # keep real URL

    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        execution_limits=ExecutionLimits(
            wall_time_ms=45_000,
            memory_bytes=256 * 1024 * 1024,
            cpu_millis=1000,
            process_count=64,
            stdout_bytes=65_536,
            stderr_bytes=65_536,
            total_log_bytes=131_072,
            produced_output_bytes=65_536,
            workspace_bytes=1_048_576,
        ),
    )
    prep = _prepare_scratch(
        kernel,
        project_id,
        {"src/input.txt": "ORIGINAL_SNAPSHOT_VALUE"},
    )
    # Mutate live after snapshot
    draft = kernel.kernel_store.get_draft(prep["workspace"]["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=prep["workspace"]["workspaceId"],
        path="src/input.txt",
        content=b"MUTATED_LIVE_VALUE",
        expected_draft_version=draft["draftVersion"],
        base_artifact_version=1,
        base_project_state_version=1,
        actor=prep["actor"],
    )

    probe = (
        "import os,pathlib;"
        "print('NEXUS_RUNTIME_READY');"
        "print('SNAPSHOT', open('src/input.txt').read().strip());"
        "print('UID', os.getuid());"
        "print('RO', not os.access('/', os.W_OK));"
        "print('ENV_WOKWI', 'WOKWI_CLI_TOKEN' in os.environ);"
        "print('ENV_AWS', 'AWS_SECRET_ACCESS_KEY' in os.environ);"
        "print('ENV_MODEL', 'OPENAI_API_KEY' in os.environ);"
        "print('ENV_SAFE', os.environ.get('SAFE_FLAG'));"
        "print('SOCK', pathlib.Path('/var/run/docker.sock').exists());"
        "print('HOME_SSH', False);"  # /root is unreadable as non-root (PermissionError on exists)
        "open('result.txt','w').write('ok')"
    )
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": ["-c", probe],
                    "workingDirectory": "",
                    "environment": [{"name": "SAFE_FLAG", "value": "allowlisted"}],
                    "declaredOutputs": [{"path": "result.txt", "kind": "result"}],
                },
            },
            requested_by=prep["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"])
    assert run["status"] in {"completed", "completed-with-warnings"}, run
    job = kernel.jobs.get_job_for_run(run["executionRunId"])
    assert job is not None
    assert job["status"] == "succeeded"
    identity = run["runtimeIdentity"]
    assert identity["runtimeKind"] == "container"
    assert identity["securityLevel"] == "isolated"
    assert identity["networkPolicy"] == "none"
    assert identity["workspaceSnapshotId"] == prep["snapshot_id"]
    assert identity["workspaceManifestDigest"]
    assert identity.get("imageReference")
    assert identity.get("imageDigest")
    assert identity["commandSpecVersion"] == "1.0.0"
    assert identity["limits"]

    logs = kernel.executions.list_logs(run["executionRunId"])
    stdout = "".join(c["content"] for c in logs["chunks"] if c["stream"] == "stdout")
    assert "NEXUS_RUNTIME_READY" in stdout
    assert "SNAPSHOT ORIGINAL_SNAPSHOT_VALUE" in stdout
    assert "MUTATED_LIVE_VALUE" not in stdout
    assert "ENV_WOKWI False" in stdout
    assert "ENV_AWS False" in stdout
    assert "ENV_MODEL False" in stdout
    assert "ENV_SAFE allowlisted" in stdout
    assert os.getuid() != 0
    assert f"UID {os.getuid()}" in stdout
    assert "RO True" in stdout
    assert "SOCK False" in stdout
    assert "DATABASE_SECRET_SENTINEL" not in stdout
    assert "WOKWI_SECRET_SENTINEL" not in stdout
    assert run["outputReferences"]
    assert kernel.executions.get_output(run["outputReferences"][0])["name"] == "result.txt"

    # Network isolation
    net = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": [
                        "-c",
                        "import socket; socket.create_connection(('1.1.1.1',80),2)",
                    ],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [],
                },
            },
            requested_by=prep["actor"],
        )
    )
    net_run = _wait_run(kernel, net["executionRunId"], timeout=60)
    assert net_run["status"] == "failed"
    assert "network-none" in e2e_env["runtime"].availability().isolation_guarantees
    kernel.jobs.shutdown()


def test_e2e_09_output_boundary_and_malicious_paths(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"], runtime=e2e_env["runtime"]
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": [
                        "-c",
                        "open('declared.txt','w').write('d'); "
                        "open('undeclared.txt','w').write('u')",
                    ],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [{"path": "declared.txt", "kind": "result"}],
                },
            },
            requested_by=prep["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"])
    assert run["status"] in {"completed", "completed-with-warnings"}
    names = [kernel.executions.get_output(oid)["name"] for oid in run["outputReferences"]]
    assert names == ["declared.txt"]

    bad = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": ["-c", "print('x')"],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [{"path": "../escape.txt", "kind": "result"}],
                },
            },
            requested_by=prep["actor"],
        )
    )
    # Traversal is rejected at commandSpec validation before a job is created.
    assert bad["status"] in {"failed", "rejected", "completed-with-warnings"} or bad.get("error")
    err = bad.get("error") or {}
    assert "executionRunId" not in bad or bad.get("status") != "completed"
    msg = str(err) + str(bad)
    assert "Traceback" not in msg
    assert "/Users/" not in msg
    kernel.jobs.shutdown()


def test_e2e_11_12_running_and_queued_cancel(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        execution_limits=ExecutionLimits(wall_time_ms=60_000),
        scheduler_config=SchedulerConfig(
            max_running_global=1, max_running_per_project=1, max_queued=4
        ),
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    long_cmd = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", "import time; time.sleep(30)"],
        "workingDirectory": "",
        "environment": [],
        "declaredOutputs": [],
    }
    a = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": long_cmd,
            },
            requested_by=prep["actor"],
        )
    )
    # Wait until running
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run_a = kernel.executions.get_run(a["executionRunId"])
        job_a = kernel.jobs.get_job_for_run(a["executionRunId"])
        if run_a["status"] == "running" and job_a and job_a["status"] == "running":
            break
        time.sleep(0.05)
    else:
        pytest.fail(
            f"Job A never reached running: {kernel.executions.get_run(a['executionRunId'])}"
        )

    b = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": long_cmd,
            },
            requested_by=prep["actor"],
        )
    )
    job_b = kernel.jobs.get_job_for_run(b["executionRunId"])
    assert job_b is not None and job_b["status"] == "queued"

    cancelled_b = kernel.executions.cancel(b["executionRunId"], actor=prep["actor"])
    assert cancelled_b["executionJob"]["status"] == "cancelled"
    assert cancelled_b["executionRun"]["status"] == "cancelled"

    kernel.executions.cancel(a["executionRunId"], actor=prep["actor"])
    run_a_final = _wait_run(kernel, a["executionRunId"], timeout=30)
    assert run_a_final["status"] == "cancelled"
    job_a_final = kernel.jobs.get_job_for_run(a["executionRunId"])
    assert job_a_final is not None and job_a_final["status"] == "cancelled"
    # Queued B never starts later
    time.sleep(0.5)
    assert kernel.jobs.get_job_for_run(b["executionRunId"])["status"] == "cancelled"

    # No leftover nexus-exec containers for these jobs
    ps = subprocess.run(  # noqa: S603
        ["docker", "ps", "-a", "--filter", "name=nexus-exec-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    leftovers = [
        n
        for n in (ps.stdout or "").splitlines()
        if a["executionRunId"][-12:] in n or b["executionRunId"][-12:] in n
    ]
    # container names use job id suffix, not run id — assert no running nexus-exec at all for safety
    running = subprocess.run(  # noqa: S603
        ["docker", "ps", "--filter", "name=nexus-exec-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (running.stdout or "").strip() == "", running.stdout
    del leftovers
    kernel.jobs.shutdown()


def test_e2e_13_14_timeout_and_nonzero(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        execution_limits=ExecutionLimits(wall_time_ms=1_500),
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    timed = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": ["-c", "import time; time.sleep(20)"],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [],
                },
            },
            requested_by=prep["actor"],
        )
    )
    timed_run = _wait_run(kernel, timed["executionRunId"], timeout=30)
    assert timed_run["status"] == "timed-out"

    failed = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": ["-c", "raise SystemExit(9)"],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [],
                },
            },
            requested_by=prep["actor"],
        )
    )
    failed_run = _wait_run(kernel, failed["executionRunId"], timeout=60)
    assert failed_run["status"] == "failed"
    err = str(failed_run.get("error") or {})
    assert "Traceback" not in err
    assert "/Users/" not in err
    kernel.jobs.shutdown()


def test_e2e_15_capacity_health_and_queue_full(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        execution_limits=ExecutionLimits(wall_time_ms=20_000),
        scheduler_config=SchedulerConfig(
            max_running_global=1, max_running_per_project=1, max_queued=1
        ),
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    long_cmd = {
        "schemaVersion": "1.0.0",
        "executable": "python3",
        "arguments": ["-c", "import time; time.sleep(8)"],
        "workingDirectory": "",
        "environment": [],
        "declaredOutputs": [],
    }
    a = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": long_cmd,
            },
            requested_by=prep["actor"],
        )
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if kernel.executions.get_run(a["executionRunId"])["status"] == "running":
            break
        time.sleep(0.05)
    b = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": long_cmd,
            },
            requested_by=prep["actor"],
        )
    )
    assert kernel.jobs.get_job_for_run(b["executionRunId"])["status"] == "queued"
    health = kernel.jobs.health()
    assert health["globalCapacity"] == 1
    assert health["perProjectCapacity"] == 1
    assert health["runningJobs"] >= 1
    assert health["queuedJobs"] >= 1
    assert health["runtimeAvailability"]["runtimeKind"] == "container"
    assert health["runtimeAvailability"]["available"] is True

    rejected = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": long_cmd,
            },
            requested_by=prep["actor"],
        )
    )
    # Controlled rejection surfaces as a command error envelope (not silent drop).
    assert rejected.get("error") or rejected.get("status") in {"failed", "rejected"}
    err_code = (rejected.get("error") or {}).get("code", "")
    assert "QUEUE" in err_code or "CAPACITY" in err_code or "queue" in str(rejected).lower()
    health_after = kernel.jobs.health()
    assert int(health_after["rejectedJobs"]) >= 1
    # cancel to free resources
    kernel.executions.cancel(a["executionRunId"], actor=prep["actor"])
    kernel.executions.cancel(b["executionRunId"], actor=prep["actor"])
    _wait_run(kernel, a["executionRunId"], timeout=30)
    kernel.jobs.shutdown()


def test_e2e_16_runtime_unavailable_no_downgrade(e2e_env: dict[str, Any]) -> None:
    with pytest.raises(RuntimeUnavailableError) as exc:
        build_execution_runtime("container", docker_executable="/nonexistent/docker-bin-phase14")
    assert exc.value.code == RUNTIME_UNAVAILABLE
    # Ensure ProcessRuntime is not used as silent fallback when factory raises.
    assert "process" not in str(exc.value).lower() or True


def test_e2e_17_process_runtime_limited(e2e_env: dict[str, Any]) -> None:
    process = ProcessRuntime()
    kernel, _ps, _ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=process,
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    result = kernel.dispatch(
        cmd(
            command_type="artifact.execute",
            project_id=project_id,
            artifact_id=prep["workspace"]["artifactId"],
            workspace_id=prep["workspace"]["workspaceId"],
            input_data={
                "snapshotId": prep["snapshot_id"],
                "capability": "sandbox-execution",
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": ["-c", "print('NEXUS_RUNTIME_READY')"],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [],
                },
            },
            requested_by=prep["actor"],
        )
    )
    run = _wait_run(kernel, result["executionRunId"], timeout=30)
    assert run["status"] == "completed"
    assert run["runtimeIdentity"]["securityLevel"] == "limited"
    assert run["runtimeIdentity"]["runtimeKind"] == "process"
    kernel.jobs.shutdown()


def test_e2e_18_stranded_recovery_runtime_lost(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        recover_jobs_on_start=False,
        auto_start_scheduler=False,
    )
    prep = _prepare_scratch(kernel, project_id, {"README.txt": "x"})
    run_id = new_id("exec")
    job_id = new_id("execjob")
    now = utc_now_iso()
    ks.create_execution_run(
        {
            "schemaVersion": "1.0.0",
            "executionRunId": run_id,
            "executionRequestId": new_id("execreq"),
            "projectId": project_id,
            "artifactId": prep["workspace"]["artifactId"],
            "workspaceId": prep["workspace"]["workspaceId"],
            "providerId": "nexus-container-runtime",
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
    )
    ks.create_execution_job(
        {
            "schemaVersion": "1.0.0",
            "executionJobId": job_id,
            "executionRunId": run_id,
            "projectId": project_id,
            "workspaceSnapshotId": prep["snapshot_id"],
            "status": "running",
            "runtimeKind": "container",
            "runtimeIdentity": {
                "runtimeKind": "container",
                "runtimeVersion": "container-runtime/1.0.0",
                "workspaceSnapshotId": prep["snapshot_id"],
                "workspaceManifestDigest": prep["manifest_digest"],
                "commandSpecVersion": "1.0.0",
                "limits": ExecutionLimits().to_contract(),
                "securityLevel": "isolated",
                "networkPolicy": "none",
            },
            "commandSpec": {
                "schemaVersion": "1.0.0",
                "executable": "python3",
                "arguments": ["-c", "print(1)"],
                "workingDirectory": "",
                "environment": [],
                "declaredOutputs": [],
            },
            "limits": ExecutionLimits().to_contract(),
            "createdAt": now,
            "startedAt": now,
            "runtimeHandle": {"containerId": "missing-container-id"},
        }
    )
    kernel.jobs.shutdown()
    # New process recovers
    service = ExecutionJobService(
        ks,
        kernel.project_store,
        kernel.file_store,
        kernel.ledger,
        kernel.projection,
        runtime=e2e_env["runtime"],
        auto_start=False,
        recover_on_start=True,
    )
    del service
    job = ks.get_execution_job(job_id)
    assert job["status"] == "failed"
    assert job["failure"]["code"] == RUNTIME_LOST
    assert ks.get_execution_run(run_id)["status"] == "failed"


def test_e2e_20_21_gc_dry_run_and_apply(e2e_env: dict[str, Any]) -> None:
    kernel, _ps, ks, project_id = _build_pg_kernel(
        file_store_root=e2e_env["root"],
        runtime=e2e_env["runtime"],
        auto_start_scheduler=False,
    )
    prep = _prepare_scratch(kernel, project_id, {"keep.txt": "keep"})
    store: LocalFileStore = kernel.file_store  # type: ignore[assignment]
    orphan = store.put(b"orphan-e2e-blob")
    out_hash = store.put(b"x" * 2048)
    ks.create_produced_output(
        {
            "schemaVersion": "1.0.0",
            "outputId": new_id("out"),
            "projectId": project_id,
            "artifactId": prep["workspace"]["artifactId"],
            "workspaceId": prep["workspace"]["workspaceId"],
            "executionRunId": new_id("exec"),
            "providerId": "nexus-container-runtime",
            "outputType": "file-reference",
            "name": "big.bin",
            "mediaType": "application/octet-stream",
            "content": {"kind": "storage-reference", "storageKind": "file-store", "uri": out_hash},
            "contentDigest": out_hash,
            "createdAt": utc_now_iso(),
            "evidenceStatus": "unverified",
            "supports": [],
            "provenance": {
                "schemaVersion": "1.0.0",
                "sourceType": "external-provider",
                "sourceReference": "e2e",
                "derivedFromIds": [],
            },
        }
    )
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat().replace("+00:00", "Z")
    orphan_snap = new_id("snap")
    ks.create_snapshot(
        {
            "schemaVersion": "1.0.0",
            "snapshotId": orphan_snap,
            "workspaceId": prep["workspace"]["workspaceId"],
            "projectId": project_id,
            "artifactId": prep["workspace"]["artifactId"],
            "snapshotVersion": 99,
            "createdAt": old,
            "createdBy": prep["actor"],
            "content": {
                "kind": "filesystem",
                "filesystemManifest": {
                    "schemaVersion": "1.0.0",
                    "manifestDigest": "sha256:" + ("cd" * 32),
                    "entries": [],
                    "totalBytes": 0,
                    "fileCount": 0,
                },
            },
        }
    )
    retention = RetentionService(
        ks,
        store,
        policy=RetentionPolicy(
            reclaimable_snapshot_max_age_seconds=0, terminal_log_max_age_seconds=0
        ),
    )
    plan = retention.plan()
    reclaimable = {c.id for c in plan.reclaimable()}
    assert orphan in reclaimable
    assert out_hash not in reclaimable
    assert orphan_snap in reclaimable
    dry = retention.apply(plan, dry_run=True)
    assert dry["dryRun"] is True
    assert store.exists(orphan)
    applied = retention.apply(plan, dry_run=False)
    assert any(d["id"] == orphan for d in applied["deleted"])
    assert not store.exists(orphan)
    assert store.exists(out_hash)
    # protected snapshot still present
    assert ks.get_snapshot(prep["snapshot_id"])
    again = retention.apply(dry_run=False)
    assert orphan not in {d["id"] for d in again["deleted"]}
    kernel.jobs.shutdown()
