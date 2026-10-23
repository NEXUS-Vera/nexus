"""Typed public models for circuit simulation providers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class AvailabilityStatus(StrEnum):
    READY = "READY"
    WOKWI_CLI_MISSING = "WOKWI_CLI_MISSING"
    WOKWI_CREDENTIAL_MISSING = "WOKWI_CREDENTIAL_MISSING"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class SupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    SURROGATE_REQUIRED = "SURROGATE_REQUIRED"
    FIRMWARE_REQUIRED = "FIRMWARE_REQUIRED"


class MappingType(StrEnum):
    EXACT = "exact"
    EQUIVALENT = "equivalent"
    SURROGATE = "surrogate"
    UNSUPPORTED = "unsupported"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ArtifactEntityReference:
    artifact_id: str
    artifact_type: str
    entity_type: str
    entity_id: str
    artifact_version: int | None = None
    display_label: str | None = None

    def as_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "schemaVersion": "1.0.0",
            "artifactId": self.artifact_id,
            "artifactType": self.artifact_type,
            "entityType": self.entity_type,
            "entityId": self.entity_id,
        }
        if self.artifact_version is not None:
            value["artifactVersion"] = self.artifact_version
        if self.display_label:
            value["displayLabel"] = self.display_label
        return value


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    severity: FindingSeverity
    references: tuple[ArtifactEntityReference, ...] = ()


@dataclass(frozen=True)
class ProviderAvailability:
    status: AvailabilityStatus
    provider: str
    message: str

    @property
    def ready(self) -> bool:
        return self.status is AvailabilityStatus.READY


@dataclass(frozen=True)
class PinMapping:
    source_pin: str
    provider_pin: str


@dataclass(frozen=True)
class ComponentMapping:
    source: str
    manufacturer: str
    part_number: str
    provider_part: str | None
    mapping_type: MappingType
    pins: tuple[PinMapping, ...] = ()


@dataclass(frozen=True)
class SupportAssessment:
    status: SupportStatus
    mappings: tuple[ComponentMapping, ...] = ()
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class MaterializationRequest:
    electrical_architecture: Mapping[str, object]
    component_plan: Mapping[str, object]
    include_wokwi_toml: bool = False
    # Provider-workspace flag: when True, ESP32 materialization includes Wokwi
    # `$serialMonitor` UART wiring. Validation/lint uses the same default so the
    # workspace validated for simulation matches the workspace executed later.
    include_serial_monitor: bool = True


@dataclass(frozen=True)
class ProviderWorkspace:
    files: Mapping[str, bytes]
    manifest: Mapping[str, object]
    findings: tuple[Finding, ...] = ()

    def text(self, filename: str) -> str:
        return self.files[filename].decode("utf-8")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    findings: tuple[Finding, ...] = ()
    diagnostic: str = ""


@dataclass(frozen=True)
class ExecutionRequest:
    workspace: ProviderWorkspace
    timeout_seconds: float = 30.0
    expect_text: tuple[str, ...] = ()
    firmware_elf_bytes: bytes | None = None
    capture_vcd: bool = False
    capture_screenshot: bool = False


@dataclass(frozen=True)
class ExecutionOutput:
    name: str
    content: bytes
    truncated: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    succeeded: bool
    exit_code: int | None
    timed_out: bool
    outputs: tuple[ExecutionOutput, ...] = ()
    findings: tuple[Finding, ...] = ()
    diagnostic: str = ""


@dataclass(frozen=True)
class RunnerResult:
    exit_code: int | None
    timed_out: bool
    stdout: bytes = b""
    stderr: bytes = b""
    outputs: Mapping[str, bytes] = field(default_factory=dict)
    truncated_outputs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RunnerRequest:
    executable: Path
    arguments: tuple[str, ...]
    files: Mapping[str, bytes]
    output_filenames: tuple[str, ...] = ()
    timeout_seconds: float = 30.0
    token: str | None = None
