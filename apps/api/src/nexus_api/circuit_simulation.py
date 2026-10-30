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
from nexus_persistence.errors import ArtifactNotFoundError, PersistenceNotFoundError


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
                        "label": source_pin
                        if source_pin == target_pin
                        else f"{source_pin}→{target_pin}",
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


def approved_execution_plan(project_store: Any, project_id: str) -> dict[str, Any] | None:
    try:
        plan = project_store.get_artifact(project_id, "execution-plan")
    except ArtifactNotFoundError:
        return None
    return (
        plan if isinstance(plan, dict) and plan.get("approvalStatus") == "user-approved" else None
    )


def materialization_request(
    *,
    electrical_artifact: dict[str, Any],
    component_plan_artifact: dict[str, Any],
    execution_plan_artifact: dict[str, Any] | None = None,
) -> MaterializationRequest:
    if execution_plan_artifact and execution_plan_artifact.get("approvalStatus") == "user-approved":
        configuration = execution_plan_artifact["content"]["configuration"]
        pairs = {
            (item["componentRoleId"], item["candidateId"]) for item in configuration["components"]
        }
        role_ids = {role for role, _candidate in pairs}
        candidate_ids = {candidate for _role, candidate in pairs}
        plan = component_plan_artifact["content"]
        component_plan_artifact = {
            **component_plan_artifact,
            "content": {
                **plan,
                "componentRoles": [
                    item for item in plan["componentRoles"] if item["componentRoleId"] in role_ids
                ],
                "candidates": [
                    item for item in plan["candidates"] if item["candidateId"] in candidate_ids
                ],
                "selectionDecisions": [
                    item
                    for item in plan["selectionDecisions"]
                    if (item["componentRoleId"], item["selectedCandidateId"]) in pairs
                ],
            },
        }
        electrical = electrical_artifact["content"]
        electrical_artifact = {
            **electrical_artifact,
            "content": {
                **electrical,
                "nodes": [
                    item
                    for item in electrical["nodes"]
                    if item.get("componentCandidateId") in candidate_ids
                    or (
                        not item.get("componentCandidateId")
                        and role_ids.intersection(item.get("componentRoleIds", []))
                    )
                ],
                "connections": [
                    item
                    for item in electrical["connections"]
                    if item["connectionId"] == configuration["i2c"]["connectionId"]
                ],
            },
        }
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


class _CircuitSimulationTimeout(CircuitExecutionError, TimeoutError):
    """Domain error retaining the execution service's timeout classification."""

    partial_outputs: list[dict[str, Any]]


class CircuitSimulationExecutionAdapter:
    """Translate board execution requests into provider calls and normalized outputs."""

    def __init__(
        self,
        *,
        provider: CircuitSimulationProvider,
        project_store: Any,
        firmware_ready: bool = False,
        kernel_store: Any = None,
        file_store: Any = None,
    ) -> None:
        self._provider = provider
        self._projects = project_store
        self._firmware_ready = firmware_ready
        self._kernel = kernel_store
        self._files = file_store

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        snapshot = request.get("snapshot")
        if not isinstance(snapshot, dict) or snapshot.get("projectId") != request.get("projectId"):
            raise CircuitExecutionError(
                code="SIMULATION_SNAPSHOT_INVALID",
                message="Simulation snapshot must belong to the requested project",
            )
        content = snapshot.get("content")
        if not isinstance(content, dict) or not isinstance(content.get("structuredContent"), dict):
            raise CircuitExecutionError(
                code="SIMULATION_SNAPSHOT_INVALID",
                message="Simulation snapshot must contain structured electrical content",
            )
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
            execution_plan_artifact=approved_execution_plan(self._projects, request["projectId"]),
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
        options = request.get("options") or {}
        if options.get("executionMode", "simulate") not in {"simulate", "validate"}:
            raise CircuitExecutionError(
                code="SIMULATION_MODE_INVALID", message="Use simulate or validate"
            )
        firmware = None
        firmware_bytes = None
        if options.get("executionMode", "simulate") == "simulate":
            availability = self._provider.availability()
            if not availability.ready:
                raise CircuitExecutionError(
                    code=availability.status.value, message=availability.message
                )
            if availability.provider != "wokwi":
                raise CircuitExecutionError(
                    code="SIMULATOR_FIXTURE_REJECTED", message="Real simulation requires Wokwi"
                )
            firmware, firmware_bytes = self._resolve_firmware(request)
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
                min(float((request.get("maxDurationMs") or 5_000) / 1000), 300),
            )
            result = self._provider.execute(
                ExecutionRequest(
                    workspace=workspace,
                    firmware_elf_bytes=firmware_bytes,
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
                error = _CircuitSimulationTimeout(
                    code="SIMULATION_TIMEOUT",
                    message="Circuit simulation timed out",
                )
                max_bytes = max(1, min(int(options.get("maxOutputBytes") or 1_000_000), 10_000_000))
                error.partial_outputs = [
                    _execution_output(item.name, item.content[:max_bytes], True)
                    for item in result.outputs
                    if item.name == "serial.log"
                ]
                raise error
            if not result.succeeded:
                raise CircuitExecutionError(
                    code="SIMULATION_FAILED",
                    message=result.diagnostic or "Circuit simulation failed",
                )
            required = {"serial.log"}
            if "logic-trace" in (options.get("requestedOutputs") or []):
                required.add("trace.vcd")
            if "simulation-screenshot" in (options.get("requestedOutputs") or []):
                required.add("screenshot.png")
            observed = {
                item.name
                for item in result.outputs
                if item.content
                and not item.truncated
                and len(item.content) <= int(options.get("maxOutputBytes") or 1_000_000)
            }
            if not required <= observed:
                raise CircuitExecutionError(
                    code="SIMULATION_OBSERVATIONS_MISSING",
                    message="Declared observations missing, empty or truncated",
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
        if firmware is not None:
            for output in outputs:
                output["provenance"] = {
                    "schemaVersion": "1.0.0",
                    "sourceType": "external-provider",
                    "sourceReference": self._provider.availability().provider,
                    "derivedFromIds": [
                        firmware["outputId"],
                        firmware["executionRunId"],
                        request["snapshot"]["snapshotId"],
                    ],
                    "notes": "Surrogate simulation; fake providers are regression evidence only.",
                }
        return {
            "inputOutputReferences": [firmware["outputId"]] if firmware else [],
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

    def _resolve_firmware(self, request: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        output_id = (request.get("options") or {}).get("firmwareOutputId")
        if not output_id or self._kernel is None or self._files is None:
            raise CircuitExecutionError(
                code="FIRMWARE_ELF_REQUIRED", message="Name a compiled firmwareOutputId explicitly"
            )
        try:
            output = self._kernel.get_produced_output(output_id)
            run = self._kernel.get_execution_run(output["executionRunId"])
            workspace = self._kernel.get_workspace(output["workspaceId"])
            job = self._kernel.get_execution_job_by_run(run["executionRunId"])
            spec = (job or {}).get("commandSpec") or {}
            if (
                output["projectId"] != request["projectId"]
                or run["projectId"] != request["projectId"]
                or workspace["artifactType"] != "firmware"
                or output["name"] != ".pio/build/nexus/firmware.elf"
                or run["status"] != "completed"
                or output_id not in run["outputReferences"]
                or spec.get("executable") != "pio"
                or spec.get("arguments") != ["run", "-e", "nexus"]
            ):
                raise ValueError("Expected a successful project PlatformIO compile output")
            content = output["content"]
            data = (
                self._files.get(content["uri"])
                if content["kind"] == "storage-reference"
                else content["structuredResult"]["text"].encode()
            )
            if workspace.get("projectId", request["projectId"]) != request["projectId"]:
                raise ValueError("Firmware workspace belongs to another project")
            if not data.startswith(b"\x7fELF") or b"NEXUS_FIRMWARE_STUB" in data:
                raise ValueError("Expected non-fixture ELF bytes")
            if (
                content["kind"] == "storage-reference"
                and "sha256:" + hashlib.sha256(data).hexdigest() != output["contentDigest"]
            ):
                raise ValueError("Firmware digest mismatch")
            return output, data
        except (KeyError, ValueError, PersistenceNotFoundError) as exc:
            raise CircuitExecutionError(code="FIRMWARE_ELF_INVALID", message=str(exc)) from exc


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
