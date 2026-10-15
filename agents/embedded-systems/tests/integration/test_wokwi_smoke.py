from __future__ import annotations

import importlib
import json
import os
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

READY_TEXT = "NEXUS_WOKWI_READY"
FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "wokwi"


class _SmokeKernelStore:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.run: dict[str, Any] = {}
        self.outputs: list[dict[str, Any]] = []
        self.workspace = {
            "workspaceId": snapshot["workspaceId"],
            "externalWorkspaceReferences": [],
        }

    def create_execution_run(self, run: dict[str, Any]) -> None:
        self.run = dict(run)

    def update_execution_status(self, _run_id: str, run: dict[str, Any]) -> None:
        self.run = dict(run)

    def get_execution_run(self, _run_id: str) -> dict[str, Any]:
        return dict(self.run)

    def list_execution_runs(
        self, _project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        del limit, cursor
        return ([dict(self.run)] if self.run else []), None

    def create_produced_output(self, output: dict[str, Any]) -> None:
        self.outputs.append(dict(output))

    def get_produced_output(self, output_id: str) -> dict[str, Any]:
        return next(item for item in self.outputs if item["outputId"] == output_id)

    def list_produced_outputs(self, _project_id: str) -> list[dict[str, Any]]:
        return list(self.outputs)

    def get_snapshot(self, _snapshot_id: str) -> dict[str, Any]:
        return dict(self.snapshot)

    def get_workspace(self, _workspace_id: str) -> dict[str, Any]:
        return dict(self.workspace)

    def update_workspace(self, workspace: dict[str, Any]) -> None:
        self.workspace = dict(workspace)


class _SmokeProjectStore:
    def __init__(
        self,
        electrical_artifact: dict[str, Any],
        component_plan: dict[str, Any],
    ) -> None:
        self.artifacts = {
            "electrical-architecture": electrical_artifact,
            "component-plan": component_plan,
        }

    def get_project(self, project_id: str) -> dict[str, Any]:
        return {"projectId": project_id, "currentStateVersion": 1}

    def get_artifact(
        self,
        _project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        del version
        return self.artifacts[artifact_type]


class _SmokeArtifactTypes:
    def get(self, _artifact_type: str) -> dict[str, Any]:
        return {"requiredCapabilities": ["circuit-simulation"]}


class _SmokeLedger:
    def append(self, **_kwargs: Any) -> dict[str, Any]:
        return {}


class _SmokeProjection:
    def update_after_write(self, _project_id: str) -> None:
        return None


def _integration_prerequisites() -> tuple[ModuleType, str, str, Path]:
    if os.environ.get("RUN_WOKWI_INTEGRATION") != "1":
        pytest.skip("set RUN_WOKWI_INTEGRATION=1 to run the Wokwi smoke test")

    token = os.environ.get("WOKWI_CLI_TOKEN")
    if not token:
        pytest.skip("WOKWI_CLI_TOKEN is required for the Wokwi smoke test")

    executable = shutil.which("wokwi-cli")
    if executable is None:
        pytest.skip("wokwi-cli is required for the Wokwi smoke test")

    firmware_value = os.environ.get("NEXUS_WOKWI_FIRMWARE_ELF")
    if not firmware_value:
        pytest.skip("NEXUS_WOKWI_FIRMWARE_ELF is required for the Wokwi smoke test")
    firmware = Path(firmware_value).expanduser()
    if firmware.suffix.lower() != ".elf" or not firmware.is_file():
        pytest.skip("NEXUS_WOKWI_FIRMWARE_ELF must point to an existing .elf file")

    try:
        simulation = importlib.import_module("nexus_circuit_simulation")
    except ModuleNotFoundError:
        pytest.skip("nexus_circuit_simulation is not importable")
    return simulation, token, executable, firmware


def _golden_request(simulation: ModuleType) -> object:
    return simulation.MaterializationRequest(
        electrical_architecture={
            "artifactId": "art_electrical",
            "artifactType": "electrical-architecture",
            "artifactVersion": 1,
            "content": {
                "nodes": [
                    {
                        "nodeId": "enode_mcu",
                        "name": "Controller",
                        "componentCandidateId": "cand_mcu",
                        "componentRoleIds": ["role_mcu"],
                        "interfaces": [
                            {
                                "interfaceId": "eiface_mcu_i2c",
                                "interfaceType": "i2c",
                            }
                        ],
                    },
                    {
                        "nodeId": "enode_imu",
                        "name": "Motion sensor",
                        "componentCandidateId": "cand_imu",
                        "componentRoleIds": ["role_imu"],
                        "interfaces": [
                            {
                                "interfaceId": "eiface_imu_i2c",
                                "interfaceType": "i2c",
                            }
                        ],
                    },
                ],
                "connections": [
                    {
                        "connectionId": "econn_i2c",
                        "fromNodeId": "enode_mcu",
                        "toNodeId": "enode_imu",
                        "interfaceType": "i2c",
                    }
                ],
            },
        },
        component_plan={
            "artifactId": "art_components",
            "artifactType": "component-plan",
            "artifactVersion": 1,
            "content": {
                "componentRoles": [
                    {"componentRoleId": "role_mcu", "name": "Controller"},
                    {"componentRoleId": "role_imu", "name": "Motion sensor"},
                ],
                "candidates": [
                    {
                        "candidateId": "cand_mcu",
                        "componentRoleId": "role_mcu",
                        "displayName": "Fixture MCU",
                        "source": "fixture",
                        "manufacturer": "Fixture Compute",
                        "partNumber": "FX-MCU-32",
                    },
                    {
                        "candidateId": "cand_imu",
                        "componentRoleId": "role_imu",
                        "displayName": "Fixture IMU",
                        "source": "fixture",
                        "manufacturer": "Fixture Motion",
                        "partNumber": "FX-IMU-200",
                    },
                ],
                "selectionDecisions": [
                    {
                        "selectionDecisionId": "sel_mcu",
                        "componentRoleId": "role_mcu",
                        "selectedCandidateId": "cand_mcu",
                    },
                    {
                        "selectionDecisionId": "sel_imu",
                        "componentRoleId": "role_imu",
                        "selectedCandidateId": "cand_imu",
                    },
                ],
            },
        },
        include_wokwi_toml=True,
    )


def test_wokwi_golden_esp32_mpu6050_smoke() -> None:
    simulation, token, executable, firmware = _integration_prerequisites()
    api_simulation = importlib.import_module("nexus_api.circuit_simulation")
    runtime_capabilities = importlib.import_module("nexus_board.registries.runtime_capabilities")
    execution_service = importlib.import_module("nexus_board.services.execution_service")
    source = (FIXTURE_DIR / "sketch.ino").read_text(encoding="utf-8")
    assert "Wire.begin(kSdaPin, kSclPin);" in source
    assert 'Serial.println("NEXUS_WOKWI_READY");' in source

    provider = simulation.WokwiProvider(
        token=token,
        executable=executable,
        firmware_elf_path=firmware,
    )
    request = _golden_request(simulation)
    assessment = provider.assess_support(request)
    assert assessment.status is simulation.SupportStatus.SURROGATE_REQUIRED
    assert len(assessment.mappings) == 2
    assert all(
        mapping.mapping_type is simulation.MappingType.SURROGATE for mapping in assessment.mappings
    )

    workspace = provider.materialize(request)
    assert workspace.files == provider.materialize(request).files
    assert set(workspace.files) == {
        "diagram.json",
        "mapping-manifest.json",
        "wokwi.toml",
    }
    diagram = json.loads(workspace.text("diagram.json"))
    assert diagram["connections"] == [
        ["mcu1:3V3", "imu1:VCC", "red", []],
        ["mcu1:GND.1", "imu1:GND", "black", []],
        ["mcu1:D21", "imu1:SDA", "green", []],
        ["mcu1:D22", "imu1:SCL", "blue", []],
        ["mcu1:TX0", "$serialMonitor:RX", "", []],
        ["mcu1:RX0", "$serialMonitor:TX", "", []],
    ]
    assert {part["type"] for part in diagram["parts"]} == {
        "wokwi-esp32-devkit-v1",
        "wokwi-mpu6050",
    }
    manifest = json.loads(workspace.text("mapping-manifest.json"))
    assert {mapping["mappingType"] for mapping in manifest["mappings"]} == {"surrogate"}
    expected_pin_profile = [
        {"providerPin": "3V3", "sourcePin": "3V3"},
        {"providerPin": "GND.1", "sourcePin": "GND"},
        {"providerPin": "D21", "sourcePin": "21"},
        {"providerPin": "D22", "sourcePin": "22"},
    ]
    assert all(mapping["pinProfile"] == expected_pin_profile for mapping in manifest["mappings"])

    validation = provider.validate(workspace)
    assert validation.valid, validation.diagnostic
    materialization = cast(Any, request)
    electrical_artifact = dict(materialization.electrical_architecture)
    component_plan = dict(materialization.component_plan)
    project_id = "proj_WOKWISMOKETEST0001"
    artifact_id = "art_WOKWISMOKETEST00001"
    workspace_id = "ws_WOKWISMOKETEST000001"
    snapshot_id = "snap_WOKWISMOKETEST0001"
    electrical_artifact.update(
        {
            "projectId": project_id,
            "artifactId": artifact_id,
            "artifactVersion": 1,
        }
    )
    component_plan.update({"projectId": project_id, "artifactVersion": 1})
    snapshot = {
        "snapshotId": snapshot_id,
        "workspaceId": workspace_id,
        "projectId": project_id,
        "artifactId": artifact_id,
        "createdAt": "2026-08-08T00:00:00Z",
        "content": {
            "kind": "structured",
            "structuredContent": electrical_artifact["content"],
        },
    }
    kernel_store = _SmokeKernelStore(snapshot)
    project_store = _SmokeProjectStore(electrical_artifact, component_plan)
    capabilities = runtime_capabilities.RuntimeCapabilityRegistry()
    capabilities.register(
        {
            "capabilityId": "circuit-simulation",
            "providerId": "wokwi",
            "available": True,
        }
    )
    adapter = api_simulation.CircuitSimulationExecutionAdapter(
        provider=provider,
        project_store=project_store,
        firmware_ready=True,
    )
    service = execution_service.ExecutionService(
        kernel_store,
        project_store,
        _SmokeArtifactTypes(),
        capabilities,
        cast(Any, _SmokeLedger()),
        cast(Any, _SmokeProjection()),
        {"circuit-simulation": adapter},
    )
    captured = service.execute(
        project_id=project_id,
        artifact_id=artifact_id,
        artifact_type="electrical-architecture",
        workspace_id=workspace_id,
        snapshot_id=snapshot_id,
        capability="circuit-simulation",
        actor={
            "schemaVersion": "1.0.0",
            "actorId": "actor_WOKWISMOKETEST0001",
            "actorType": "system",
        },
        base_artifact_version=1,
        base_project_state_version=1,
        max_duration_ms=30_000,
        options={
            "executionMode": "simulate",
            "expectedText": READY_TEXT,
            "requestedOutputs": ["serial-log", "provider-workspace"],
            "maxOutputBytes": 1_048_576,
        },
    )
    assert captured["executionRun"]["status"] in {
        "completed",
        "completed-with-warnings",
    }
    serial_outputs = [output for output in captured["outputs"] if output["outputType"] == "log"]
    assert any(
        READY_TEXT in output["content"]["structuredResult"].get("text", "")
        for output in serial_outputs
    )
    assert any(output.get("entityReferences") for output in captured["outputs"])
    assert all(output["evidenceStatus"] == "unverified" for output in captured["outputs"])
    assert any(output["name"] == "provider-workspace-manifest" for output in captured["outputs"])
    print(
        "Wokwi smoke passed: simulation executed with surrogate hardware; "
        "real component compatibility remains unverified."
    )
