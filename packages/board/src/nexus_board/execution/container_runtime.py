"""Docker-backed LocalContainerRuntime with honest isolation guarantees.

Requires Docker only when selected via NEXUS_EXECUTION_RUNTIME=container.
Ordinary make check remains offline and uses ProcessRuntime.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from typing import Any

from nexus_board.execution.command_spec import environment_entries_to_mapping
from nexus_board.execution.env import assert_no_host_secrets, build_sandbox_environment
from nexus_board.execution.failure_codes import (
    CANCELLED,
    CONTAINER_START_FAILED,
    NETWORK_POLICY_DENIED,
    NONZERO_EXIT,
    RESOURCE_EXHAUSTED,
    TIMED_OUT,
)
from nexus_board.execution.process_runtime import (
    OutputCollectionError,
    collect_declared_outputs,
)
from nexus_board.execution.runtime_protocol import (
    NETWORK_POLICY_NONE,
    SECURITY_LEVEL_ISOLATED,
    RuntimeAvailability,
    RuntimeExecuteRequest,
    RuntimeExecuteResult,
)

RUNTIME_VERSION = "container-runtime/1.0.0"

ISOLATION_GUARANTEES = [
    "no-inherited-env",
    "no-provider-secrets",
    "ephemeral-workspace",
    "container-termination",
    "bounded-stdout-stderr",
    "declared-outputs-only",
    "network-none",
    "nonroot",
    "readonly-rootfs",
    "no-docker-socket",
    "memory-limit",
    "cpu-limit",
    "pids-limit",
]

ISOLATION_LIMITATIONS = [
    "requires-docker",
    "host-docker-daemon-trust-boundary",
    "no-seccomp-custom-profile",
]


class LocalContainerRuntime:
    """Secure-path runtime when Docker is available and explicitly selected."""

    def __init__(
        self,
        *,
        image_reference: str = "python:3.13-slim",
        docker_executable: str = "docker",
    ) -> None:
        self._image_reference = image_reference
        self._docker = docker_executable
        self._lock = threading.Lock()
        self._containers: dict[str, str] = {}  # job_id -> container_id
        self._resolved_digest: str | None = None

    def availability(self) -> RuntimeAvailability:
        docker_path = shutil.which(self._docker)
        if docker_path is None:
            return RuntimeAvailability(
                available=False,
                runtime_kind="container",
                runtime_version=RUNTIME_VERSION,
                security_level=SECURITY_LEVEL_ISOLATED,
                network_policy=NETWORK_POLICY_NONE,
                isolation_guarantees=list(ISOLATION_GUARANTEES),
                isolation_limitations=list(ISOLATION_LIMITATIONS),
                unavailable_reason=f"Docker executable not found: {self._docker}",
            )
        try:
            probe = subprocess.run(  # noqa: S603
                [self._docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                env={"PATH": os.environ.get("PATH", os.defpath)},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return RuntimeAvailability(
                available=False,
                runtime_kind="container",
                runtime_version=RUNTIME_VERSION,
                security_level=SECURITY_LEVEL_ISOLATED,
                network_policy=NETWORK_POLICY_NONE,
                isolation_guarantees=list(ISOLATION_GUARANTEES),
                isolation_limitations=list(ISOLATION_LIMITATIONS),
                unavailable_reason=f"Docker daemon unreachable: {exc}",
            )
        if probe.returncode != 0:
            return RuntimeAvailability(
                available=False,
                runtime_kind="container",
                runtime_version=RUNTIME_VERSION,
                security_level=SECURITY_LEVEL_ISOLATED,
                network_policy=NETWORK_POLICY_NONE,
                isolation_guarantees=list(ISOLATION_GUARANTEES),
                isolation_limitations=list(ISOLATION_LIMITATIONS),
                unavailable_reason=(probe.stderr or probe.stdout or "docker info failed")[:300],
            )
        return RuntimeAvailability(
            available=True,
            runtime_kind="container",
            runtime_version=RUNTIME_VERSION,
            security_level=SECURITY_LEVEL_ISOLATED,
            network_policy=NETWORK_POLICY_NONE,
            isolation_guarantees=list(ISOLATION_GUARANTEES),
            isolation_limitations=list(ISOLATION_LIMITATIONS),
            details={
                "dockerExecutable": docker_path,
                "dockerServerVersion": (probe.stdout or "").strip(),
                "imageReference": self._image_reference,
            },
        )

    def cancel(self, job_id: str) -> None:
        with self._lock:
            container_id = self._containers.get(job_id)
        if container_id:
            self._docker_run(["kill", container_id], timeout=10)

    def cleanup(self, job_id: str, *, handle: dict[str, Any] | None = None) -> None:
        del handle
        self.cancel(job_id)
        with self._lock:
            container_id = self._containers.pop(job_id, None)
        if container_id:
            self._docker_run(["rm", "-f", container_id], timeout=10)

    def reconcile_handle(self, handle: dict[str, Any]) -> str | None:
        container_id = handle.get("containerId")
        if not container_id:
            return "failed"
        probe = self._docker_run(
            ["inspect", "-f", "{{.State.Running}}", str(container_id)],
            timeout=5,
        )
        if probe.returncode != 0:
            return "failed"
        running = (probe.stdout or "").strip().lower()
        if running == "true":
            self._docker_run(["rm", "-f", str(container_id)], timeout=10)
        return "failed"

    def resolve_image_digest(self) -> tuple[str, str]:
        """Return (imageReference, imageDigest). Pulls if needed."""
        if self._resolved_digest:
            return self._image_reference, self._resolved_digest
        inspect = self._docker_run(
            ["image", "inspect", self._image_reference, "--format", "{{json .RepoDigests}}"],
            timeout=30,
        )
        if inspect.returncode != 0:
            pull = self._docker_run(["pull", self._image_reference], timeout=300)
            if pull.returncode != 0:
                raise RuntimeError((pull.stderr or pull.stdout or "docker pull failed")[:500])
            inspect = self._docker_run(
                [
                    "image",
                    "inspect",
                    self._image_reference,
                    "--format",
                    "{{json .RepoDigests}}",
                ],
                timeout=30,
            )
        if inspect.returncode != 0:
            raise RuntimeError((inspect.stderr or "image inspect failed")[:500])
        digests = json.loads(inspect.stdout or "[]")
        digest = digests[0] if digests else self._image_reference
        # Prefer sha256-only form when present as name@sha256:...
        if "@" in digest:
            digest = digest.split("@", 1)[1]
        self._resolved_digest = digest
        return self._image_reference, digest

    def execute(self, request: RuntimeExecuteRequest) -> RuntimeExecuteResult:
        if request.network_policy not in {NETWORK_POLICY_NONE, "none"}:
            return _failed(
                NETWORK_POLICY_DENIED,
                f"Unsupported networkPolicy={request.network_policy}; only none is enforced",
            )
        avail = self.availability()
        if not avail.available:
            return _failed(
                "RUNTIME_UNAVAILABLE",
                avail.unavailable_reason or "Container runtime unavailable",
            )

        try:
            image_ref, image_digest = self.resolve_image_digest()
        except Exception as exc:  # noqa: BLE001
            return _failed(CONTAINER_START_FAILED, str(exc)[:500])

        spec = request.command_spec
        limits = request.limits
        root = request.workspace_root.resolve()
        working_directory = spec.get("workingDirectory") or ""
        if working_directory:
            cwd_host = (root / working_directory).resolve()
            if not str(cwd_host).startswith(str(root) + os.sep) and cwd_host != root:
                return _failed("WORKING_DIRECTORY_INVALID", "workingDirectory escaped workspace")
            container_workdir = f"/workspace/{working_directory}"
        else:
            container_workdir = "/workspace"

        executable = str(spec["executable"])
        if executable.startswith("/") or ".." in executable.split("/"):
            return _failed(
                "EXECUTABLE_INVALID", "executable must be basename or workspace-relative"
            )
        if "/" in executable:
            exe_host = (root / executable).resolve()
            if not str(exe_host).startswith(str(root) + os.sep):
                return _failed("EXECUTABLE_INVALID", "executable escaped workspace")
            argv0 = f"/workspace/{executable}"
        else:
            argv0 = executable
        argv = [argv0, *[str(a) for a in spec.get("arguments") or []]]

        env_map = environment_entries_to_mapping(spec.get("environment") or [])
        # Container gets only approved env; PATH set inside image.
        env = build_sandbox_environment(env_map, path="/usr/local/bin:/usr/bin:/bin")
        assert_no_host_secrets(env)
        # Drop host-like HOME; container nonroot home.
        env["HOME"] = "/tmp"
        env.pop("PATH", None)

        memory = limits.memory_bytes or (256 * 1024 * 1024)
        cpus = max((limits.cpu_millis or 1000) / 1000.0, 0.1)
        pids = limits.process_count or 64
        name = f"nexus-exec-{request.job_id[-20:]}"

        owner = root.stat()
        if owner.st_uid == 0:
            return _failed(CONTAINER_START_FAILED, "Workspace owner must be nonroot")
        docker_args = [
            "run",
            "--detach",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            f"{owner.st_uid}:{owner.st_gid}",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            str(memory),
            "--memory-swap",
            str(memory),
            "--cpus",
            f"{cpus:.3f}",
            "--pids-limit",
            str(pids),
            "--workdir",
            container_workdir,
            "--mount",
            f"type=bind,source={root},target=/workspace",
        ]
        for key, value in env.items():
            docker_args.extend(["--env", f"{key}={value}"])
        # Prefer digest-pinned image when digest is a sha256 content digest.
        image_to_run = image_ref
        if image_digest.startswith("sha256:") and "@" not in image_ref:
            image_to_run = f"{image_ref}@{image_digest}"
        docker_args.append(image_to_run)
        docker_args.extend(argv)

        create = self._docker_run(docker_args, timeout=30)
        if create.returncode != 0:
            return RuntimeExecuteResult(
                status="failed",
                exit_code=None,
                stdout="",
                stderr=create.stderr or "",
                system_messages=[(create.stderr or create.stdout or "docker run failed")[:500]],
                outputs=[],
                log_truncated=False,
                failure_code=CONTAINER_START_FAILED,
                failure_message=(create.stderr or "docker run failed")[:500],
                image_reference=image_ref,
                image_digest=image_digest,
            )
        container_id = (create.stdout or "").strip()
        with self._lock:
            self._containers[request.job_id] = container_id
        if request.on_started:
            request.on_started({"containerId": container_id})

        system_messages = [f"Started container {container_id[:12]}"]
        timed_out = False
        cancelled = False
        exit_code: int | None = None
        oom = False
        stdout = ""
        stderr = ""
        truncated = False
        deadline = time.monotonic() + (limits.wall_time_ms / 1000.0)
        try:
            while True:
                if request.cancel_check and request.cancel_check():
                    cancelled = True
                    self._docker_run(["kill", container_id], timeout=10)
                    system_messages.append("Cancellation requested; container killed")
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    self._docker_run(["kill", container_id], timeout=10)
                    system_messages.append("Wall-clock timeout; container killed")
                    break
                state = self._docker_run(
                    [
                        "inspect",
                        "-f",
                        "{{.State.Status}}|{{.State.ExitCode}}|{{.State.OOMKilled}}",
                        container_id,
                    ],
                    timeout=5,
                )
                if state.returncode != 0:
                    break
                status_text, exit_text, oom_text = (state.stdout or "|||").strip().split("|", 2)
                if status_text not in {"running", "created"}:
                    try:
                        exit_code = int(exit_text)
                    except ValueError:
                        exit_code = None
                    oom = oom_text.strip().lower() == "true"
                    break
                time.sleep(0.05)

            logs = self._docker_run(
                ["logs", "--timestamps=false", container_id],
                timeout=30,
            )
            stdout, stdout_trunc = _bound_text(logs.stdout or "", limits.stdout_bytes)
            stderr, stderr_trunc = _bound_text(logs.stderr or "", limits.stderr_bytes)
            truncated = stdout_trunc or stderr_trunc
        finally:
            self._docker_run(["rm", "-f", container_id], timeout=10)
            with self._lock:
                self._containers.pop(request.job_id, None)

        if cancelled:
            status, failure_code, failure_message = "cancelled", CANCELLED, "Execution cancelled"
        elif timed_out:
            status, failure_code, failure_message = (
                "timed-out",
                TIMED_OUT,
                "Execution exceeded wallTimeMs",
            )
        elif oom:
            status, failure_code, failure_message = (
                "failed",
                RESOURCE_EXHAUSTED,
                "Container killed by memory limit",
            )
        elif exit_code == 0:
            status, failure_code, failure_message = "succeeded", None, None
        else:
            status = "failed"
            failure_code = NONZERO_EXIT
            failure_message = f"Container exited with code {exit_code}"

        outputs = []
        if status in {"succeeded", "failed"}:
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
            stdout=stdout,
            stderr=stderr,
            system_messages=system_messages,
            outputs=outputs,
            log_truncated=truncated,
            failure_code=failure_code,
            failure_message=failure_message,
            executable_fingerprint=f"{RUNTIME_VERSION}:{image_digest}:{argv0}",
            image_reference=image_ref,
            image_digest=image_digest,
        )

    def _docker_run(self, args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [self._docker, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={"PATH": os.environ.get("PATH", os.defpath)},
        )


def _bound_text(text: str, limit: int) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return text, False
    return data[:limit].decode("utf-8", errors="replace"), True


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
