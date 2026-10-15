"""Bounded local subprocess execution for circuit providers."""

from __future__ import annotations

import os
import signal
import stat
import subprocess
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from .errors import CircuitExecutionError
from .types import RunnerRequest, RunnerResult

MAX_HOST_TIMEOUT_SECONDS = 310.0
DEFAULT_MAX_OUTPUT_BYTES = 1_000_000
ALLOWED_FILENAMES = frozenset(
    {
        "diagram.json",
        "mapping-manifest.json",
        "wokwi.toml",
        "firmware.elf",
        "serial.log",
        "trace.vcd",
        "screenshot.png",
    }
)


class ProcessRunner(Protocol):
    def run(self, request: RunnerRequest) -> RunnerResult: ...


def sanitize_diagnostic(value: bytes | str, token: str | None = None) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    if token:
        text = text.replace(token, "[REDACTED]")
    return text


class SafeSubprocessRunner:
    """Run a trusted executable in an isolated, bounded temporary workspace."""

    def __init__(self, *, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self.max_output_bytes = max_output_bytes

    def run(self, request: RunnerRequest) -> RunnerResult:
        executable = request.executable.resolve()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise CircuitExecutionError(
                code="SIMULATOR_EXECUTABLE_UNAVAILABLE",
                message="Configured simulator executable is unavailable",
            )
        self._validate_filenames(request)
        timeout = max(0.1, min(float(request.timeout_seconds), MAX_HOST_TIMEOUT_SECONDS))

        with TemporaryDirectory(prefix="nexus-circuit-") as directory:
            workspace = Path(directory)
            for filename, content in request.files.items():
                (workspace / filename).write_bytes(content)
            argv = [
                str(executable),
                *(
                    str(workspace) if argument == "{workspace}" else argument
                    for argument in request.arguments
                ),
            ]
            if any("\x00" in argument for argument in argv):
                raise CircuitExecutionError(
                    code="SIMULATOR_ARGUMENT_INVALID",
                    message="Simulator argument contains an invalid character",
                )
            environment = {"PATH": os.defpath}
            if request.token:
                environment["WOKWI_CLI_TOKEN"] = request.token
            try:
                process = subprocess.Popen(
                    argv,
                    cwd=workspace,
                    env=environment,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    timed_out = True
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    try:
                        stdout, stderr = process.communicate(timeout=1.0)
                    except subprocess.TimeoutExpired as error:
                        stdout, stderr = error.output or b"", error.stderr or b""
                        if process.stdout:
                            process.stdout.close()
                        if process.stderr:
                            process.stderr.close()
                        with suppress(subprocess.TimeoutExpired):
                            process.wait(timeout=1.0)
            except OSError as error:
                raise CircuitExecutionError(
                    code="SIMULATOR_START_FAILED",
                    message="Simulator process could not be started",
                    retryable=False,
                ) from error

            outputs: dict[str, bytes] = {}
            truncated: set[str] = set()
            for filename in request.output_filenames:
                output_path = workspace / filename
                # Reject links and special files before reading. O_NOFOLLOW also
                # closes the symlink-swap race between inspection and open.
                try:
                    descriptor = os.open(output_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                except OSError:
                    continue
                with os.fdopen(descriptor, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        continue
                    content = stream.read(self.max_output_bytes + 1)
                outputs[filename], was_truncated = self._truncate(content)
                if was_truncated:
                    truncated.add(filename)
            stdout, stdout_truncated = self._truncate(stdout)
            stderr, stderr_truncated = self._truncate(stderr)
            if stdout_truncated:
                truncated.add("stdout")
            if stderr_truncated:
                truncated.add("stderr")
            return RunnerResult(
                exit_code=None if timed_out else process.returncode,
                timed_out=timed_out,
                stdout=stdout,
                stderr=stderr,
                outputs=outputs,
                truncated_outputs=frozenset(truncated),
            )

    def _validate_filenames(self, request: RunnerRequest) -> None:
        filenames = set(request.files) | set(request.output_filenames)
        if not filenames.issubset(ALLOWED_FILENAMES):
            raise CircuitExecutionError(
                code="WORKSPACE_FILENAME_NOT_ALLOWED",
                message="Provider workspace contains a filename outside the allowlist",
            )
        if any(Path(name).name != name for name in filenames):
            raise CircuitExecutionError(
                code="WORKSPACE_FILENAME_NOT_ALLOWED",
                message="Provider workspace filenames must not contain paths",
            )

    def _truncate(self, value: bytes) -> tuple[bytes, bool]:
        if len(value) <= self.max_output_bytes:
            return value, False
        return value[: self.max_output_bytes], True
