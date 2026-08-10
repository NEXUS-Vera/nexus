"""Application composition for the provider-neutral circuit-simulation capability."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from nexus_circuit_simulation import (
    CircuitExecutionError,
    CircuitSimulationProvider,
    ExecutionRequest,
    Finding,
    MappingType,
    MaterializationRequest,
    ProviderWorkspace,
    SupportAssessment,
    SupportStatus,
)


def _finding(value: Finding) -> dict[str, Any]:
    result: dict[str, Any] = {
        "findingId": f"finding_{value.code}",
        "reasonCode": value.code,
        "message": value.message,
        "mappingType": ("unsupported" if value.severity.value == "error" else "surrogate"),
    }
    if value.references:
        result["entityReference"] = value.references[0].as_dict()
    return result


def serialize_support_assessment(
    assessment: SupportAssessment,
    *,
    firmware_ready: bool,
    provider_id: str,
) -> dict[str, Any]:
    status = assessment.status
    if status not in {SupportStatus.UNSUPPORTED, SupportStatus.PARTIALLY_SUPPORTED} and (
        not firmware_ready
    ):
        status = SupportStatus.FIRMWARE_REQUIRED
    return {
        "schemaVersion": "1.0.0",
        "capabilityId": "circuit-simulation",
        "providerId": provider_id,
        "status": status.value,
        "firmwareRequired": not firmware_ready,
        "surrogateUsed": any(
            mapping.mapping_type is MappingType.SURROGATE for mapping in assessment.mappings
        ),
        "findings": [_finding(item) for item in assessment.findings],
    }


def serialize_availability(
    provider: CircuitSimulationProvider,
    *,
    firmware_ready: bool,
) -> dict[str, Any]:
    availability = provider.availability()
    return {
        "providerId": availability.provider,
        "status": availability.status.value,
        "available": availability.ready and firmware_ready,
        "lintAvailable": availability.status.value != "WOKWI_CLI_MISSING",
        "firmwareReady": firmware_ready,
        "message": availability.message,
    }


def serialize_validation(result: Any, workspace: ProviderWorkspace) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "ok": bool(result.valid),
        "findings": [_finding(item) for item in result.findings],
        "diagnostic": str(result.diagnostic),
        "workspaceDigest": workspace_digest(workspace),
        "representationOnly": True,
    }


def serialize_provider_preview(
    *,
    assessment: SupportAssessment,
    workspace: ProviderWorkspace,
    provider_id: str,
) -> dict[str, Any]:
    """Normalized provider-preview DTO for Simulation mode (not raw diagram.json)."""

    mappings = workspace.manifest.get("mappings")
    mapping_list = mappings if isinstance(mappings, list) else []
    connections: list[dict[str, object]] = []
    diagram_raw = workspace.files.get("diagram.json")
    if diagram_raw:
        try:
            diagram = json.loads(diagram_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            diagram = {}
        raw_connections = diagram.get("connections") if isinstance(diagram, dict) else None
        if isinstance(raw_connections, list):
            for index, item in enumerate(raw_connections):
                if not isinstance(item, list) or len(item) < 2:
                    continue
                left = str(item[0])
                right = str(item[1])
                if ":" not in left or ":" not in right:
                    continue
                source_part, source_pin = left.split(":", 1)
                target_part, target_pin = right.split(":", 1)
                if source_part.startswith("$") or target_part.startswith("$"):
                    continue
                connections.append(
                    {
                        "id": f"preview_conn_{index}",
                        "sourcePartId": source_part,
                        "targetPartId": target_part,
                        "sourcePin": source_pin,
                        "targetPin": target_pin,
                        "label": source_pin if source_pin == target_pin else f"{source_pin}→{target_pin}",
                    }
                )
    return {
        "schemaVersion": "1.0.0",
        "providerId": provider_id,
        "status": assessment.status.value,
        "surrogateUsed": any(
            mapping.mapping_type is MappingType.SURROGATE for mapping in assessment.mappings
        ),
        "workspaceDigest": workspace_digest(workspace),
        "mappings": [item for item in mapping_list if isinstance(item, dict)],
        "connections": connections,
        "findings": [_finding(item) for item in assessment.findings],
    }


def materialization_request(
    *,
    electrical_artifact: dict[str, Any],
    component_plan_artifact: dict[str, Any],
) -> MaterializationRequest:
    return MaterializationRequest(
        electrical_architecture=electrical_artifact,
        component_plan=component_plan_artifact,
        include_wokwi_toml=True,
    )


def workspace_digest(workspace: ProviderWorkspace) -> str:
    digest = hashlib.sha256()
    for name in sorted(workspace.files):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(workspace.files[name])
        digest.update(b"\0")
    return digest.hexdigest()


class CircuitSimulationExecutionAdapter:
    """Translate board execution requests into provider calls and normalized outputs."""

    def __init__(
        self,
        *,
        provider: CircuitSimulationProvider,
        project_store: Any,
        firmware_ready: bool,
    ) -> None:
        self._provider = provider
        self._projects = project_store
        self._firmware_ready = firmware_ready

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        snapshot = request["snapshot"]
        electrical_artifact = {
            "artifactId": request["artifactId"],
            "artifactType": request["artifactType"],
            "artifactVersion": request["artifactVersion"],
            "content": snapshot["content"]["structuredContent"],
        }
        component_plan = self._projects.get_artifact(request["projectId"], "component-plan")
        materialization = materialization_request(
            electrical_artifact=electrical_artifact,
            component_plan_artifact=component_plan,
        )
        assessment = self._provider.assess_support(materialization)
        if assessment.status in {
            SupportStatus.UNSUPPORTED,
            SupportStatus.PARTIALLY_SUPPORTED,
        }:
            raise CircuitExecutionError(
                code="ARCHITECTURE_UNSUPPORTED",
                message="Electrical Architecture is not supported by the configured provider",
            )
        workspace = self._provider.materialize(materialization)
        validation = self._provider.validate(workspace)
        outputs = [
            {
                "outputType": "validation-report",
                "name": "circuit-simulation-validation",
                "mediaType": "application/json",
                "structuredResult": {
                    "valid": validation.valid,
                    "findings": [_finding(item) for item in validation.findings],
                    "diagnostic": validation.diagnostic,
                    "representationOnly": True,
                },
                "entityReferences": _entity_references(workspace),
                "evidenceStatus": "unverified",
            }
        ]
        if not validation.valid:
            raise CircuitExecutionError(
                code="PROVIDER_VALIDATION_FAILED",
                message="Provider representation validation failed",
            )

        options = request.get("options") or {}
        mode = options.get("executionMode", "simulate")
        if mode == "simulate":
            timeout_seconds = max(
                0.1,
                min(float((request.get("maxDurationMs") or 30_000) / 1000), 300),
            )
            result = self._provider.execute(
                ExecutionRequest(
                    workspace=workspace,
                    timeout_seconds=timeout_seconds,
                    expect_text=(
                        (str(options["expectedText"]),) if options.get("expectedText") else ()
                    ),
                    capture_vcd="logic-trace" in (options.get("requestedOutputs") or []),
                    capture_screenshot="simulation-screenshot"
                    in (options.get("requestedOutputs") or []),
                )
            )
            if result.timed_out:
                raise TimeoutError("Circuit simulation timed out")
            if not result.succeeded:
                raise CircuitExecutionError(
                    code="SIMULATION_FAILED",
                    message=result.diagnostic or "Circuit simulation failed",
                )
            max_bytes = max(1, min(int(options.get("maxOutputBytes") or 1_000_000), 10_000_000))
            outputs.extend(
                _execution_output(output.name, output.content[:max_bytes], output.truncated)
                for output in result.outputs
            )
            outputs.append(
                {
                    "outputType": "structured-result",
                    "name": "circuit-simulation-result",
                    "mediaType": "application/json",
                    "structuredResult": {
                        "succeeded": result.succeeded,
                        "exitCode": result.exit_code,
                        "findings": [_finding(item) for item in result.findings],
                        "surrogate": True,
                        "realComponentCompatibilityVerified": False,
                    },
                    "entityReferences": _entity_references(workspace),
                    "evidenceStatus": "unverified",
                }
            )

        if "provider-workspace" in (options.get("requestedOutputs") or []):
            outputs.append(
                {
                    "outputType": "file-reference",
                    "name": "provider-workspace-manifest",
                    "mediaType": "application/json",
                    "structuredResult": {
                        "workspaceDigest": workspace_digest(workspace),
                        "manifest": workspace.manifest,
                        "files": {
                            name: content.decode("utf-8")
                            for name, content in workspace.files.items()
                            if name
                            in {
                                "diagram.json",
                                "mapping-manifest.json",
                                "wokwi.toml",
                            }
                        },
                    },
                    "entityReferences": _entity_references(workspace),
                    "evidenceStatus": "unverified",
                }
            )
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        digest = workspace_digest(workspace)
        return {
            "providerId": self._provider.availability().provider,
            "status": ("completed-with-warnings" if workspace.findings else "completed"),
            "outputs": outputs,
            "externalWorkspaceReference": {
                "schemaVersion": "1.0.0",
                "providerId": self._provider.availability().provider,
                "externalReferenceId": f"workspace:{digest}",
                "displayLabel": "Generated circuit-simulation workspace",
                "syncStatus": "bound",
                "lastSyncedAt": now,
                "createdAt": now,
                "updatedAt": now,
            },
        }


def _entity_references(workspace: ProviderWorkspace) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    mappings = workspace.manifest.get("mappings")
    if not isinstance(mappings, list):
        return references
    for mapping in mappings:
        if isinstance(mapping, dict):
            source_references = mapping.get("sourceReferences")
            if not isinstance(source_references, list):
                continue
            for reference in source_references:
                if isinstance(reference, dict) and reference not in references:
                    references.append(reference)
    return references


def _execution_output(name: str, content: bytes, truncated: bool) -> dict[str, Any]:
    if name in {"serial.log", "stdout", "stderr"}:
        structured = {
            "text": content.decode("utf-8", errors="replace"),
            "truncated": truncated,
        }
        output_type = "log"
        media_type = "text/plain"
    else:
        structured = {
            "base64": base64.b64encode(content).decode("ascii"),
            "truncated": truncated,
        }
        output_type = "binary-reference"
        media_type = "image/png" if name.endswith(".png") else "application/octet-stream"
    return {
        "outputType": output_type,
        "name": name,
        "mediaType": media_type,
        "structuredResult": structured,
        "evidenceStatus": "unverified",
    }
