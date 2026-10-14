"""Process-backed ExecutionRuntime with honest weak-isolation guarantees.

This is NOT equivalent to a container sandbox. It provides:
- no inherited API/provider secrets
- ephemeral workspace materialization
- wall-clock timeout with process-group kill
- bounded stdout/stderr capture
- declared-output collection with symlink/traversal rejection

It does NOT provide network isolation, non-root enforcement, read-only rootfs,
cgroup memory/CPU limits, or host mount restrictions beyond the ephemeral tree.
"""

from __future__ import annotations

import contextlib
import os
import select
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from nexus_persistence.file_store.hashing import blob_digest

from nexus_board.execution.command_spec import environment_entries_to_mapping
from nexus_board.execution.env import assert_no_host_secrets, build_sandbox_environment
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.runtime_protocol import (
    CollectedOutput,
    RuntimeAvailability,
    RuntimeExecuteRequest,
    RuntimeExecuteResult,
)
from nexus_board.paths import normalize_workspace_path

RUNTIME_VERSION = "process-runtime/1.1.0"

ISOLATION_GUARANTEES = [
    "no-inherited-env",
    "no-provider-secrets",
    "ephemeral-workspace",
    "process-group-termination",
    "bounded-stdout-stderr",
    "declared-outputs-only",
]

ISOLATION_LIMITATIONS = [
    "host-process-isolation-only",
    "no-network-isolation",
    "no-memory-cgroup",
    "no-cpu-quota",
    "no-nonroot-enforcement",
    "no-readonly-rootfs",
]


class ProcessRuntime:
    """Local process runtime suitable for Phase 14B tests/dev.

    Security posture: weaker than a container sandbox. See module docstring.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}

    def availability(self) -> RuntimeAvailability:
        return RuntimeAvailability(
            available=True,
            runtime_kind="process",
            runtime_version=RUNTIME_VERSION,
            security_level="limited",
            network_policy="none",
            isolation_guarantees=list(ISOLATION_GUARANTEES),
            isolation_limitations=list(ISOLATION_LIMITATIONS),
            details={"shell": False, "startNewSession": True},
        )

    def cancel(self, job_id: str) -> None:
        with self._lock:
            proc = self._processes.get(job_id)
        if proc is None:
            return
        _kill_process_group(proc)

    def cleanup(self, job_id: str, *, handle: dict[str, Any] | None = None) -> None:
        """Idempotent process-group teardown (ephemeral dirs cleaned by JobService)."""
        del handle
        self.cancel(job_id)
        with self._lock:
            self._processes.pop(job_id, None)

    def reconcile_handle(self, handle: dict[str, Any]) -> str | None:
        """Process handles from a prior API process cannot be proven alive → lost."""
        del handle
        return "lost"

    def execute(self, request: RuntimeExecuteRequest) -> RuntimeExecuteResult:
        spec = request.command_spec
        limits = request.limits
        root = request.workspace_root.resolve()
        cwd = root
        working_directory = spec.get("workingDirectory") or ""
        if working_directory:
            cwd = (root / working_directory).resolve()
            if not str(cwd).startswith(str(root) + os.sep) and cwd != root:
                return _failed("WORKING_DIRECTORY_INVALID", "workingDirectory escaped workspace")
            if not cwd.is_dir():
                return _failed("WORKING_DIRECTORY_MISSING", "workingDirectory does not exist")

        executable = str(spec["executable"])
        # Workspace-relative executable path.
        if "/" in executable:
            exe_path = (root / executable).resolve()
            if not str(exe_path).startswith(str(root) + os.sep):
                return _failed("EXECUTABLE_INVALID", "executable escaped workspace")
            if not exe_path.exists():
                return _failed("EXECUTABLE_MISSING", "executable not found in workspace")
            argv0 = str(exe_path)
        else:
            argv0 = executable

        argv = [argv0, *[str(a) for a in spec.get("arguments") or []]]
        env = build_sandbox_environment(
            environment_entries_to_mapping(spec.get("environment") or [])
        )
        assert_no_host_secrets(env)

        fingerprint = f"{RUNTIME_VERSION}:{argv0}"
        system_messages: list[str] = []
        stdout_buf = bytearray()
        stderr_buf = bytearray()
        truncated = False
        timed_out = False
        cancelled = False
        exit_code: int | None = None

        try:
            proc = subprocess.Popen(  # noqa: S603 — argv list, shell=False
                argv,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
        except OSError as exc:
            return RuntimeExecuteResult(
                status="failed",
                exit_code=None,
                stdout="",
                stderr="",
                system_messages=[f"Failed to start process: {exc}"],
                outputs=[],
                log_truncated=False,
                failure_code="PROCESS_START_FAILED",
                failure_message=str(exc)[:500],
                executable_fingerprint=fingerprint,
            )

        with self._lock:
            self._processes[request.job_id] = proc
        if request.on_started and proc.pid is not None:
            request.on_started({"pid": int(proc.pid)})

        deadline = time.monotonic() + (limits.wall_time_ms / 1000.0)
        try:
            assert proc.stdout is not None and proc.stderr is not None
            streams = {
                proc.stdout: ("stdout", stdout_buf, limits.stdout_bytes),
                proc.stderr: ("stderr", stderr_buf, limits.stderr_bytes),
            }
            while streams:
                if request.cancel_check and request.cancel_check():
                    cancelled = True
                    _kill_process_group(proc)
                    system_messages.append("Cancellation requested; process group killed")
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    _kill_process_group(proc)
                    system_messages.append("Wall-clock timeout; process group killed")
                    break
                ready, _, _ = select.select(list(streams.keys()), [], [], 0.05)
                for fh in ready:
                    name, buf, limit = streams[fh]
                    chunk = os.read(fh.fileno(), 4096)
                    if not chunk:
                        streams.pop(fh, None)
                        continue
                    remaining = limit - len(buf)
                    if remaining <= 0:
                        truncated = True
                        continue
                    if len(chunk) > remaining:
                        buf.extend(chunk[:remaining])
                        truncated = True
                    else:
                        buf.extend(chunk)
            try:
                exit_code = proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                _kill_process_group(proc)
                exit_code = proc.wait(timeout=2)
        finally:
            _kill_process_group(proc)
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            with self._lock:
                self._processes.pop(request.job_id, None)

        stdout_text = _safe_text(bytes(stdout_buf))
        stderr_text = _safe_text(bytes(stderr_buf))

        failure_code: str | None
        failure_message: str | None
        if cancelled:
            status = "cancelled"
            failure_code, failure_message = "CANCELLED", "Execution cancelled"
        elif timed_out:
            status = "timed-out"
            failure_code, failure_message = "TIMED_OUT", "Execution exceeded wallTimeMs"
        elif exit_code == 0:
            status = "succeeded"
            failure_code = None
            failure_message = None
        else:
            status = "failed"
            failure_code = "NONZERO_EXIT"
            failure_message = f"Process exited with code {exit_code}"

        outputs: list[CollectedOutput] = []
        if status == "succeeded" or status == "failed":
            try:
                outputs = collect_declared_outputs(
                    workspace_root=root,
                    declared=list(spec.get("declaredOutputs") or []),
                    limits=limits,
                )
            except OutputCollectionError as exc:
                if status == "succeeded":
                    status = "failed"
                    failure_code = exc.code
                    failure_message = exc.message
                system_messages.append(exc.message)

        return RuntimeExecuteResult(
            status=status,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            system_messages=system_messages,
            outputs=outputs,
            log_truncated=truncated,
            failure_code=failure_code,
            failure_message=failure_message,
            executable_fingerprint=fingerprint,
        )


class OutputCollectionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def collect_declared_outputs(
    *,
    workspace_root: Path,
    declared: list[dict[str, Any]],
    limits: ExecutionLimits,
) -> list[CollectedOutput]:
    root = workspace_root.resolve()
    if len(declared) > limits.output_file_count:
        raise OutputCollectionError("OUTPUT_FILE_COUNT", "Too many declared outputs")
    collected: list[CollectedOutput] = []
    total = 0
    for item in declared:
        path = normalize_workspace_path(str(item["path"]))
        kind = str(item["kind"])
        target = (root / path).resolve()
        if not str(target).startswith(str(root) + os.sep) and target != root:
            raise OutputCollectionError("OUTPUT_PATH_INVALID", f"Output path escaped root: {path}")
        raw_target = root / path
        if raw_target.is_symlink() or any(
            p.is_symlink() for p in raw_target.parents if p != root and root in p.parents
        ):
            raise OutputCollectionError("OUTPUT_SYMLINK_REJECTED", f"Symlink rejected: {path}")
        if not target.is_file():
            # Declared outputs that are missing are skipped.
            continue
        remaining = limits.produced_output_bytes - total
        if target.stat().st_size > remaining:
            raise OutputCollectionError("OUTPUT_BYTES_EXCEEDED", "Produced outputs exceed limit")
        # Bound the read too: a file can grow after stat.
        with target.open("rb") as stream:
            data = stream.read(remaining + 1)
        total += len(data)
        if total > limits.produced_output_bytes:
            raise OutputCollectionError("OUTPUT_BYTES_EXCEEDED", "Produced outputs exceed limit")
        collected.append(
            CollectedOutput(
                path=path,
                kind=kind,
                content=data,
                content_hash=blob_digest(data),
            )
        )
    return collected


def _kill_process_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


def _safe_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _failed(code: str, message: str) -> RuntimeExecuteResult:
    return RuntimeExecuteResult(
        status="failed",
        exit_code=None,
        stdout="",
        stderr="",
        system_messages=[message],
        outputs=[],
        log_truncated=False,
        failure_code=code,
        failure_message=message,
    )
