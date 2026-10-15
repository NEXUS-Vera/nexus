from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from nexus_circuit_simulation import (
    AvailabilityStatus,
    CircuitSimulationCapability,
    CircuitSimulationProvider,
    ExecutionRequest,
    FakeCircuitSimulationProvider,
    MappingType,
    MaterializationRequest,
    RunnerRequest,
    RunnerResult,
    SafeSubprocessRunner,
    SupportStatus,
    WokwiProvider,
    find_mapping,
)


def simulation_request(
    *,
    source: str = "fixture",
    manufacturer: str = "Fixture Compute",
    part_number: str = "FX-MCU-32",
    include_imu: bool = True,
) -> MaterializationRequest:
    candidates = [
        {
            "candidateId": "cand_mcu",
            "componentRoleId": "role_mcu",
            "displayName": "Fixture MCU",
            "source": source,
            "manufacturer": manufacturer,
            "partNumber": part_number,
        }
    ]
    roles = [{"componentRoleId": "role_mcu", "name": "Controller"}]
    decisions = [
        {
            "selectionDecisionId": "sel_mcu",
            "componentRoleId": "role_mcu",
            "selectedCandidateId": "cand_mcu",
        }
    ]
    nodes = [
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
        }
    ]
    if include_imu:
        candidates.append(
            {
                "candidateId": "cand_imu",
                "componentRoleId": "role_imu",
                "displayName": "Fixture IMU",
                "source": "fixture",
                "manufacturer": "Fixture Motion",
                "partNumber": "FX-IMU-200",
            }
        )
        roles.append({"componentRoleId": "role_imu", "name": "Motion sensor"})
        decisions.append(
            {
                "selectionDecisionId": "sel_imu",
                "componentRoleId": "role_imu",
                "selectedCandidateId": "cand_imu",
            }
        )
        nodes.append(
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
            }
        )
    return MaterializationRequest(
        electrical_architecture={
            "artifactId": "art_electrical",
            "artifactType": "electrical-architecture",
            "artifactVersion": 1,
            "content": {
                "nodes": nodes,
                "connections": (
                    [
                        {
                            "connectionId": "econn_i2c",
                            "fromNodeId": "enode_mcu",
                            "toNodeId": "enode_imu",
                            "interfaceType": "i2c",
                        }
                    ]
                    if include_imu
                    else []
                ),
            },
        },
        component_plan={
            "artifactId": "art_components",
            "artifactType": "component-plan",
            "artifactVersion": 1,
            "content": {
                "componentRoles": roles,
                "candidates": candidates,
                "selectionDecisions": decisions,
            },
        },
        include_wokwi_toml=True,
    )


class RecordingRunner:
    def __init__(self, result: RunnerResult) -> None:
        self.result = result
        self.requests: list[RunnerRequest] = []

    def run(self, request: RunnerRequest) -> RunnerResult:
        self.requests.append(request)
        return self.result


def test_availability_checks_cli_before_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nexus_circuit_simulation.wokwi.shutil.which", lambda _: None)
    assert WokwiProvider().availability().status is AvailabilityStatus.WOKWI_CLI_MISSING

    provider = WokwiProvider(executable=sys.executable)
    assert provider.availability().status is AvailabilityStatus.WOKWI_CREDENTIAL_MISSING
    assert (
        WokwiProvider(token="secret", executable=sys.executable).availability().status
        is AvailabilityStatus.READY
    )


def test_mapping_registry_is_exact_and_surrogate() -> None:
    mapping = find_mapping(
        source="fixture",
        manufacturer="Fixture Compute",
        part_number="FX-MCU-32",
    )
    assert mapping is not None
    assert mapping.provider_part == "wokwi-esp32-devkit-v1"
    assert mapping.mapping_type is MappingType.SURROGATE
    assert (
        find_mapping(
            source="Fixture",
            manufacturer="Fixture Compute",
            part_number="FX-MCU-32",
        )
        is None
    )
    assert (
        find_mapping(
            source="fixture",
            manufacturer="fixture compute",
            part_number="FX-MCU-32",
        )
        is None
    )


def test_support_reports_surrogates_and_unsupported_components() -> None:
    provider = FakeCircuitSimulationProvider()
    assert provider.assess_support(simulation_request()).status is SupportStatus.SURROGATE_REQUIRED
    unsupported = provider.assess_support(
        simulation_request(manufacturer="Other", include_imu=False)
    )
    assert unsupported.status is SupportStatus.UNSUPPORTED
    assert [finding.code for finding in unsupported.findings] == ["COMPONENT_UNSUPPORTED"]


def test_support_rejects_missing_electrical_i2c_facts() -> None:
    request = simulation_request()
    electrical = dict(request.electrical_architecture)
    content_value = electrical["content"]
    assert isinstance(content_value, dict)
    content = dict(content_value)
    content["connections"] = []
    electrical["content"] = content
    assessment = FakeCircuitSimulationProvider().assess_support(
        MaterializationRequest(electrical, request.component_plan)
    )
    assert assessment.status is SupportStatus.PARTIALLY_SUPPORTED
    assert assessment.findings[-1].code == "ELECTRICAL_INTERFACE_MISMATCH"


@pytest.mark.parametrize("provider_kind", ["fake", "wokwi"])
def test_capability_orchestration_is_provider_independent(provider_kind: str) -> None:
    provider: CircuitSimulationProvider
    if provider_kind == "fake":
        provider = FakeCircuitSimulationProvider()
    else:
        provider = WokwiProvider(
            executable=sys.executable,
            runner=RecordingRunner(RunnerResult(exit_code=0, timed_out=False)),
        )
    capability = CircuitSimulationCapability(provider)
    prepared = capability.prepare(simulation_request())
    assert prepared.assessment.status is SupportStatus.SURROGATE_REQUIRED
    assert capability.validate(prepared).valid


def test_unselected_and_ambiguous_components_are_findings() -> None:
    request = simulation_request(include_imu=False)
    plan = dict(request.component_plan)
    content_object = plan["content"]
    assert isinstance(content_object, dict)
    content = dict(content_object)
    content["selectionDecisions"] = []
    plan["content"] = content
    unselected = FakeCircuitSimulationProvider().materialize(
        MaterializationRequest(request.electrical_architecture, plan)
    )
    assert [finding.code for finding in unselected.findings] == ["COMPONENT_UNSELECTED"]
    assert json.loads(unselected.text("diagram.json"))["parts"] == []

    content["selectionDecisions"] = [
        {
            "selectionDecisionId": "sel_a",
            "componentRoleId": "role_mcu",
            "selectedCandidateId": "cand_mcu",
        },
        {
            "selectionDecisionId": "sel_b",
            "componentRoleId": "role_mcu",
            "selectedCandidateId": "cand_mcu",
        },
    ]
    ambiguous = FakeCircuitSimulationProvider().materialize(
        MaterializationRequest(request.electrical_architecture, plan)
    )
    assert ambiguous.findings[0].code == "COMPONENT_SELECTION_AMBIGUOUS"


def test_translation_is_deterministic_and_uses_fixed_provider_coordinates() -> None:
    provider = FakeCircuitSimulationProvider()
    first = provider.materialize(simulation_request())
    second = provider.materialize(simulation_request())
    assert first.files == second.files
    diagram = json.loads(first.text("diagram.json"))
    assert diagram["parts"] == [
        {
            "attrs": {},
            "id": "imu1",
            "left": 320,
            "top": 0,
            "type": "wokwi-mpu6050",
        },
        {
            "attrs": {},
            "id": "mcu1",
            "left": 0,
            "top": 0,
            "type": "wokwi-esp32-devkit-v1",
        },
    ]
    assert diagram["connections"] == [
        ["mcu1:3V3", "imu1:VCC", "red", []],
        ["mcu1:GND.1", "imu1:GND", "black", []],
        ["mcu1:D21", "imu1:SDA", "green", []],
        ["mcu1:D22", "imu1:SCL", "blue", []],
        ["mcu1:TX0", "$serialMonitor:RX", "", []],
        ["mcu1:RX0", "$serialMonitor:TX", "", []],
    ]
    manifest = json.loads(first.text("mapping-manifest.json"))
    assert manifest["mappings"][0]["pinProfile"] == [
        {"providerPin": "3V3", "sourcePin": "3V3"},
        {"providerPin": "GND.1", "sourcePin": "GND"},
        {"providerPin": "D21", "sourcePin": "21"},
        {"providerPin": "D22", "sourcePin": "22"},
    ]
    assert set(manifest["mappings"][0]["sourceReferences"][0]) >= {
        "artifactId",
        "artifactType",
        "entityId",
        "entityType",
    }


def test_serial_output_request_materializes_esp32_serial_monitor_wiring() -> None:
    provider = FakeCircuitSimulationProvider()
    with_serial = provider.materialize(
        MaterializationRequest(
            simulation_request().electrical_architecture,
            simulation_request().component_plan,
            include_serial_monitor=True,
        )
    )
    without_serial = provider.materialize(
        MaterializationRequest(
            simulation_request().electrical_architecture,
            simulation_request().component_plan,
            include_serial_monitor=False,
        )
    )
    with_serial_connections = json.loads(with_serial.text("diagram.json"))["connections"]
    without_serial_connections = json.loads(without_serial.text("diagram.json"))["connections"]
    assert with_serial_connections[-2:] == [
        ["mcu1:TX0", "$serialMonitor:RX", "", []],
        ["mcu1:RX0", "$serialMonitor:TX", "", []],
    ]
    assert without_serial_connections == [
        ["mcu1:3V3", "imu1:VCC", "red", []],
        ["mcu1:GND.1", "imu1:GND", "black", []],
        ["mcu1:D21", "imu1:SDA", "green", []],
        ["mcu1:D22", "imu1:SCL", "blue", []],
    ]
    assert "$serialMonitor" not in json.dumps(without_serial_connections)


def test_wokwi_lint_is_normalized_without_requiring_token() -> None:
    runner = RecordingRunner(
        RunnerResult(
            exit_code=1,
            timed_out=False,
            stderr=b"diagram.json: invalid connection\n",
        )
    )
    provider = WokwiProvider(executable=sys.executable, runner=runner)
    workspace = provider.materialize(simulation_request())
    result = provider.validate(workspace)
    assert not result.valid
    assert result.findings[-1].code == "WOKWI_LINT_ERROR"
    assert runner.requests[0].arguments == ("lint", "{workspace}")
    assert runner.requests[0].token is None


def test_execute_builds_only_controlled_arguments_and_normalizes_outputs(
    tmp_path: Path,
) -> None:
    firmware = tmp_path / "application.elf"
    firmware.write_bytes(b"ELF")
    runner = RecordingRunner(
        RunnerResult(
            exit_code=0,
            timed_out=False,
            stdout=b"x" * 12,
            outputs={"serial.log": b"ready\n", "trace.vcd": b"trace"},
        )
    )
    provider = WokwiProvider(
        token="top-secret",
        executable=sys.executable,
        runner=runner,
        firmware_elf_path=firmware,
        max_output_bytes=8,
    )
    workspace = provider.materialize(simulation_request())
    result = provider.execute(
        ExecutionRequest(
            workspace,
            timeout_seconds=999,
            expect_text=("ready",),
            capture_vcd=True,
            capture_screenshot=True,
        )
    )
    recorded = runner.requests[0]
    assert recorded.timeout_seconds == 310
    assert recorded.files["firmware.elf"] == b"ELF"
    assert recorded.arguments == (
        "{workspace}",
        "--elf",
        "firmware.elf",
        "--timeout",
        "300000",
        "--serial-log-file",
        "serial.log",
        "--expect-text",
        "ready",
        "--vcd-file",
        "trace.vcd",
        "--screenshot",
        "screenshot.png",
    )
    assert recorded.output_filenames == (
        "serial.log",
        "trace.vcd",
        "screenshot.png",
    )
    stdout = next(output for output in result.outputs if output.name == "stdout")
    assert stdout.content == b"x" * 8
    assert stdout.truncated


@pytest.mark.parametrize(
    ("timeout_seconds", "expected_timeout_ms", "expected_host_timeout_seconds"),
    (
        (30.0, "30000", 40.0),
        (0.1, "100", 10.1),
        (300.0, "300000", 310.0),
    ),
)
def test_wokwi_timeout_converts_seconds_to_milliseconds(
    tmp_path: Path,
    timeout_seconds: float,
    expected_timeout_ms: str,
    expected_host_timeout_seconds: float,
) -> None:
    firmware = tmp_path / "firmware.elf"
    firmware.write_bytes(b"ELF")
    runner = RecordingRunner(RunnerResult(exit_code=0, timed_out=False))
    provider = WokwiProvider(
        token="token",
        executable=sys.executable,
        runner=runner,
        firmware_elf_path=firmware,
    )

    provider.execute(
        ExecutionRequest(
            provider.materialize(simulation_request()),
            timeout_seconds=timeout_seconds,
        )
    )

    recorded = runner.requests[0]
    timeout_index = recorded.arguments.index("--timeout")
    assert recorded.arguments[timeout_index + 1] == expected_timeout_ms
    assert recorded.timeout_seconds == expected_host_timeout_seconds


def test_timeout_diagnostics_do_not_expose_token(tmp_path: Path) -> None:
    firmware = tmp_path / "firmware.elf"
    firmware.write_bytes(b"ELF")
    runner = RecordingRunner(
        RunnerResult(
            exit_code=None,
            timed_out=True,
            stderr=b"credential secret-value rejected",
        )
    )
    provider = WokwiProvider(
        token="secret-value",
        executable=sys.executable,
        runner=runner,
        firmware_elf_path=firmware,
    )
    result = provider.execute(ExecutionRequest(provider.materialize(simulation_request())))
    assert result.timed_out
    assert "secret-value" not in result.diagnostic
    assert "[REDACTED]" in result.diagnostic
    assert result.findings[-1].code == "SIMULATION_TIMEOUT"


def test_safe_runner_clamps_timeout_and_truncates_output() -> None:
    runner = SafeSubprocessRunner(max_output_bytes=4)
    result = runner.run(
        RunnerRequest(
            executable=Path(sys.executable),
            arguments=("-c", "print('abcdefgh', end='')"),
            files={},
            timeout_seconds=999,
        )
    )
    assert result.stdout == b"abcd"
    assert "stdout" in result.truncated_outputs


def test_protocol_independent_orchestration() -> None:
    def orchestrate(provider: CircuitSimulationProvider) -> bool:
        request = simulation_request()
        workspace = provider.materialize(request)
        validation = provider.validate(workspace)
        if not validation.valid:
            return False
        return provider.execute(ExecutionRequest(workspace)).succeeded

    assert orchestrate(FakeCircuitSimulationProvider())
