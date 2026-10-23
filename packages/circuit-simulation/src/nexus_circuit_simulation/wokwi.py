"""Wokwi CLI circuit simulation provider."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .errors import CircuitConfigurationError, CircuitExecutionError
from .runner import (
    DEFAULT_MAX_OUTPUT_BYTES,
    ProcessRunner,
    SafeSubprocessRunner,
    sanitize_diagnostic,
)
from .translator import assess_support, materialize_workspace
from .types import (
    AvailabilityStatus,
    ExecutionOutput,
    ExecutionRequest,
    ExecutionResult,
    Finding,
    FindingSeverity,
    MaterializationRequest,
    ProviderAvailability,
    ProviderWorkspace,
    RunnerRequest,
    SupportAssessment,
    ValidationResult,
)

WOKWI_MAX_SIMULATION_TIMEOUT_SECONDS = 300.0
WOKWI_PROCESS_GRACE_SECONDS = 10.0


class WokwiProvider:
    """Local Wokwi CLI adapter with no installation or arbitrary-argv surface."""

    provider_name = "wokwi"

    def __init__(
        self,
        *,
        token: str | None = None,
        executable: str | Path | None = None,
        runner: ProcessRunner | None = None,
        firmware_elf_path: str | Path | None = None,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self._token = token or None
        self._configured_executable = str(executable) if executable is not None else None
        self._runner = runner or SafeSubprocessRunner(max_output_bytes=max_output_bytes)
        self._firmware_elf_path = Path(firmware_elf_path) if firmware_elf_path is not None else None
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self._max_output_bytes = max_output_bytes

    def availability(self) -> ProviderAvailability:
        executable = self._resolve_executable()
        if executable is None:
            return ProviderAvailability(
                AvailabilityStatus.WOKWI_CLI_MISSING,
                self.provider_name,
                "Wokwi CLI is not installed or configured",
            )
        if not self._token:
            return ProviderAvailability(
                AvailabilityStatus.WOKWI_CREDENTIAL_MISSING,
                self.provider_name,
                "Wokwi CLI credential is not configured",
            )
        return ProviderAvailability(
            AvailabilityStatus.READY,
            self.provider_name,
            "Wokwi CLI and credential are available",
        )

    def assess_support(self, request: MaterializationRequest) -> SupportAssessment:
        return assess_support(request)

    def materialize(self, request: MaterializationRequest) -> ProviderWorkspace:
        return materialize_workspace(request)

    def validate(self, workspace: ProviderWorkspace) -> ValidationResult:
        executable = self._require_executable()
        result = self._runner.run(
            RunnerRequest(
                executable=executable,
                arguments=("lint", "{workspace}"),
                files=workspace.files,
                timeout_seconds=30.0,
            )
        )
        diagnostic = self._diagnostic(result.stdout, result.stderr)
        findings: list[Finding] = list(workspace.findings)
        if result.timed_out:
            findings.append(
                Finding(
                    code="WOKWI_LINT_TIMEOUT",
                    message="Wokwi workspace lint timed out",
                    severity=FindingSeverity.ERROR,
                )
            )
        elif result.exit_code != 0:
            lines = [line.strip() for line in diagnostic.splitlines() if line.strip()]
            for line in lines or ["Wokwi workspace lint failed"]:
                findings.append(
                    Finding(
                        code="WOKWI_LINT_ERROR",
                        message=line,
                        severity=FindingSeverity.ERROR,
                    )
                )
        valid = (
            not result.timed_out
            and result.exit_code == 0
            and not any(item.severity is FindingSeverity.ERROR for item in findings)
        )
        return ValidationResult(valid, tuple(findings), diagnostic)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        executable = self._require_executable()
        if not self._token:
            raise CircuitConfigurationError(
                code="WOKWI_CREDENTIAL_MISSING",
                message="Wokwi CLI credential is not configured",
            )
        firmware = self._firmware_elf_path
        if request.firmware_elf_bytes is None and (firmware is None or not firmware.is_file()):
            raise CircuitConfigurationError(
                code="FIRMWARE_ELF_MISSING",
                message="A readable firmware ELF is required for simulation",
            )
        files = dict(request.workspace.files)
        firmware_content = request.firmware_elf_bytes
        if firmware_content is None:
            assert firmware is not None
            firmware_content = firmware.read_bytes()
        files["firmware.elf"] = firmware_content
        simulation_timeout_seconds = max(
            0.1,
            min(float(request.timeout_seconds), WOKWI_MAX_SIMULATION_TIMEOUT_SECONDS),
        )
        simulation_timeout_ms = round(simulation_timeout_seconds * 1000)
        host_timeout_seconds = simulation_timeout_seconds + WOKWI_PROCESS_GRACE_SECONDS
        arguments: list[str] = [
            "{workspace}",
            "--elf",
            "firmware.elf",
            "--timeout",
            str(simulation_timeout_ms),
            "--serial-log-file",
            "serial.log",
        ]
        for expected in request.expect_text:
            if not expected or "\x00" in expected:
                raise CircuitExecutionError(
                    code="EXPECT_TEXT_INVALID",
                    message="Expected serial text must be non-empty and contain no null bytes",
                )
            arguments.extend(("--expect-text", expected))
        output_filenames = ["serial.log"]
        if request.capture_vcd:
            arguments.extend(("--vcd-file", "trace.vcd"))
            output_filenames.append("trace.vcd")
        if request.capture_screenshot:
            arguments.extend(("--screenshot", "screenshot.png"))
            output_filenames.append("screenshot.png")

        result = self._runner.run(
            RunnerRequest(
                executable=executable,
                arguments=tuple(arguments),
                files=files,
                output_filenames=tuple(output_filenames),
                timeout_seconds=host_timeout_seconds,
                token=self._token,
            )
        )
        outputs: list[ExecutionOutput] = []
        for name in sorted(result.outputs):
            content, truncated = self._bounded(self._redact(result.outputs[name]))
            outputs.append(
                ExecutionOutput(
                    name=name,
                    content=content,
                    truncated=truncated or name in result.truncated_outputs,
                )
            )
        for name, content in (("stdout", result.stdout), ("stderr", result.stderr)):
            if content:
                bounded, truncated = self._bounded(self._redact(content))
                outputs.append(
                    ExecutionOutput(
                        name=name,
                        content=bounded,
                        truncated=truncated or name in result.truncated_outputs,
                    )
                )
        findings = list(request.workspace.findings)
        if result.timed_out:
            findings.append(
                Finding(
                    code="SIMULATION_TIMEOUT",
                    message="Circuit simulation exceeded its bounded timeout",
                    severity=FindingSeverity.ERROR,
                )
            )
        elif result.exit_code != 0:
            findings.append(
                Finding(
                    code="SIMULATION_FAILED",
                    message="Circuit simulation exited unsuccessfully",
                    severity=FindingSeverity.ERROR,
                )
            )
        diagnostic = self._diagnostic(result.stdout, result.stderr)
        return ExecutionResult(
            succeeded=not result.timed_out and result.exit_code == 0,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            outputs=tuple(outputs),
            findings=tuple(findings),
            diagnostic=diagnostic,
        )

    def _resolve_executable(self) -> Path | None:
        configured = self._configured_executable
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.is_absolute():
                return (
                    candidate.resolve()
                    if candidate.is_file() and os.access(candidate, os.X_OK)
                    else None
                )
            located = shutil.which(configured)
        else:
            located = shutil.which("wokwi-cli")
        return Path(located).resolve() if located else None

    def _require_executable(self) -> Path:
        executable = self._resolve_executable()
        if executable is None:
            raise CircuitConfigurationError(
                code="WOKWI_CLI_MISSING",
                message="Wokwi CLI is not installed or configured",
            )
        return executable

    def _bounded(self, value: bytes) -> tuple[bytes, bool]:
        return (
            (value, False)
            if len(value) <= self._max_output_bytes
            else (value[: self._max_output_bytes], True)
        )

    def _redact(self, value: bytes) -> bytes:
        return value.replace(self._token.encode(), b"[REDACTED]") if self._token else value

    def _diagnostic(self, stdout: bytes, stderr: bytes) -> str:
        combined = stdout + (b"\n" if stdout and stderr else b"") + stderr
        bounded, _ = self._bounded(self._redact(combined))
        return sanitize_diagnostic(bounded, self._token)
