"""Offline API coverage for provider-neutral circuit-simulation surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.config import settings
from nexus_api.main import _kernel_store, app
from nexus_board.ids import new_id, utc_now_iso


@pytest.mark.asyncio
async def test_support_health_and_controlled_export_without_provider_call() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {settings.session_token}"},
    ) as client:
        initialized = await client.post(
            "/v1/projects/initialize",
            json={
                "message": (
                    "I want to build a device that records machine vibration "
                    "using a microcontroller and motion sensor."
                ),
                "autonomyMode": "collaborate",
            },
        )
        assert initialized.status_code == 200, initialized.text
        project_id = initialized.json()["project"]["projectId"]

        support = await client.get(
            f"/v1/projects/{project_id}/artifacts/"
            "electrical-architecture/circuit-simulation/support"
        )
        assert support.status_code == 200, support.text
        payload = support.json()
        assert payload["providerAvailability"]["providerId"] == "wokwi"
        assert payload["providerAvailability"]["status"] in {
            "READY",
            "WOKWI_CLI_MISSING",
            "WOKWI_CREDENTIAL_MISSING",
        }
        assert payload["assessment"]["capabilityId"] == "circuit-simulation"
        assert payload["assessment"]["providerId"] == "wokwi"

        outputs = await client.get(f"/v1/projects/{project_id}/outputs")
        assert outputs.status_code == 200
        assert outputs.json()["items"] == []

        export = await client.get(
            f"/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/export"
        )
        assert export.status_code == 404
        assert export.json()["error"]["code"] == "SIMULATION_EXPORT_NOT_FOUND"

        preview = await client.get(
            f"/v1/projects/{project_id}/artifacts/"
            "electrical-architecture/circuit-simulation/preview"
        )
        assert preview.status_code == 200, preview.text
        preview_payload = preview.json()
        assert preview_payload["providerId"] == "wokwi"
        assert "mappings" in preview_payload
        assert "connections" in preview_payload
        assert "diagram.json" not in preview_payload

        electrical = next(
            artifact
            for artifact in initialized.json()["artifacts"]
            if artifact["artifactType"] == "electrical-architecture"
        )
        now = utc_now_iso()
        _kernel_store.create_produced_output(
            {
                "schemaVersion": "1.0.0",
                "outputId": new_id("out"),
                "projectId": project_id,
                "artifactId": electrical["artifactId"],
                "workspaceId": new_id("ws"),
                "executionRunId": new_id("exec"),
                "outputType": "file-reference",
                "name": "provider-workspace-manifest",
                "mediaType": "application/json",
                "content": {
                    "kind": "inline-structured",
                    "structuredResult": {
                        "workspaceDigest": "sha256-test",
                        "manifest": {"providerId": "wokwi"},
                        "files": {"diagram.json": "{}\n"},
                    },
                },
                "contentDigest": "sha256-test",
                "createdAt": now,
                "evidenceStatus": "unverified",
                "supports": [
                    {
                        "supportKind": "artifact",
                        "targetId": electrical["artifactId"],
                    }
                ],
            }
        )
        persisted_export = await client.get(
            f"/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/export"
        )
        assert persisted_export.status_code == 200
        assert persisted_export.json()["files"] == {"diagram.json": "{}\n"}
        assert "attachment;" in persisted_export.headers["content-disposition"]


@pytest.mark.parametrize(
    "snapshot",
    [
        {"projectId": "other", "content": {"structuredContent": {}}},
        {"projectId": "proj_test", "content": {}},
        {"projectId": "proj_test", "content": {"structuredContent": None}},
        {"projectId": "proj_test", "content": {"structuredContent": []}},
    ],
)
def test_adapter_rejects_invalid_snapshot(snapshot: dict) -> None:
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError

    provider, store = Mock(), Mock()
    adapter = CircuitSimulationExecutionAdapter(
        provider=provider, project_store=store, firmware_ready=True
    )
    with pytest.raises(CircuitExecutionError):
        adapter.execute(
            {
                "projectId": "proj_test",
                "artifactId": "art_test",
                "artifactType": "electrical-architecture",
                "artifactVersion": 1,
                "snapshot": snapshot,
            }
        )
    provider.assess_support.assert_not_called()
    store.get_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_validate_endpoint_does_not_block_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import threading

    from nexus_api import main
    from nexus_circuit_simulation import FakeCircuitSimulationProvider

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class SlowProvider(FakeCircuitSimulationProvider):
        def validate(self, workspace):
            entered.set()
            release.wait(3)
            finished.set()
            return super().validate(workspace)

    monkeypatch.setattr(main, "_wokwi_provider", SlowProvider())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {settings.session_token}"},
    ) as client:
        initialized = await client.post(
            "/v1/projects/initialize",
            json={
                "message": (
                    "I want to build a device that records machine vibration "
                    "using a microcontroller and motion sensor."
                ),
                "autonomyMode": "collaborate",
            },
        )
        assert initialized.status_code == 200
        pid = initialized.json()["project"]["projectId"]

        async def health_during_validation():
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            assert not release.is_set()
            assert not finished.is_set(), "validation blocked the event loop until it finished"
            response = await client.get("/healthz")
            assert response.status_code == 200
            release.set()

        task = asyncio.create_task(
            client.post(
                f"/v1/projects/{pid}/artifacts/electrical-architecture/circuit-simulation/validate"
            )
        )
        try:
            await health_during_validation()
            for _ in range(200):
                if task.done():
                    break
                await asyncio.sleep(0.01)
            response = await asyncio.wait_for(task, 1)
            assert response.status_code == 200, response.text
        finally:
            release.set()
            await asyncio.wait_for(task, 3)


def test_adapter_raises_typed_circuit_execution_error_on_timeout() -> None:
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import (
        CircuitExecutionError,
        ExecutionOutput,
        ExecutionResult,
        SupportStatus,
    )

    provider, store = Mock(), Mock()
    store.get_artifact.return_value = {"content": {}}
    provider.assess_support.return_value.status = SupportStatus.SURROGATE_REQUIRED
    provider.materialize.return_value.manifest = {"mappings": []}
    provider.validate.return_value.valid = True
    provider.validate.return_value.findings = ()
    provider.availability.return_value.ready = True
    provider.availability.return_value.provider = "wokwi"
    provider.execute.return_value = ExecutionResult(
        succeeded=False,
        exit_code=None,
        timed_out=True,
        outputs=(ExecutionOutput("serial.log", b"TEL,0,0,0,1"),),
    )
    adapter = CircuitSimulationExecutionAdapter(
        provider=provider, project_store=store, firmware_ready=True
    )
    adapter._resolve_firmware = Mock(return_value=({"outputId": "out_test"}, b"\x7fELF"))
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(
            {
                "projectId": "proj_test",
                "artifactId": "art_test",
                "artifactType": "electrical-architecture",
                "artifactVersion": 1,
                "snapshot": {"projectId": "proj_test", "content": {"structuredContent": {}}},
            }
        )
    assert provider.execute.call_args.args[0].timeout_seconds == 5
    partial_outputs = getattr(error.value, "partial_outputs", [])
    assert partial_outputs[0]["structuredResult"]["truncated"] is True
    assert partial_outputs[0]["evidenceStatus"] == "unverified"
    assert error.value.code == "SIMULATION_TIMEOUT"
    # Preserve the execution service's timed-out status classification.
    assert isinstance(error.value, TimeoutError)


@pytest.mark.parametrize("status", ["WOKWI_CLI_MISSING", "WOKWI_CREDENTIAL_MISSING"])
def test_simulation_unavailable_is_explicit(status):
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import (
        AvailabilityStatus,
        CircuitExecutionError,
        FakeCircuitSimulationProvider,
        ProviderAvailability,
    )

    provider = FakeCircuitSimulationProvider(
        availability_result=ProviderAvailability(AvailabilityStatus(status), "wokwi", "Unavailable")
    )
    # A supported materialization is tested by the end-to-end regression. Isolate the gate here.
    provider.assess_support = Mock(return_value=Mock(status="SUPPORTED"))
    adapter = CircuitSimulationExecutionAdapter(provider=provider, project_store=Mock())
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(_w4_request())
    assert error.value.code == status
    assert not any(call[0] == "execute" for call in provider.calls)


def _w4_request():
    return {
        "projectId": "proj_test",
        "artifactId": "art_test",
        "artifactType": "electrical-architecture",
        "artifactVersion": 1,
        "snapshot": {
            "projectId": "proj_test",
            "snapshotId": "snap_test",
            "content": {"structuredContent": {}},
        },
    }


def test_fixture_provider_cannot_satisfy_real_simulation():
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError, FakeCircuitSimulationProvider

    provider = FakeCircuitSimulationProvider()
    provider.assess_support = Mock(return_value=Mock(status="SUPPORTED"))
    adapter = CircuitSimulationExecutionAdapter(provider=provider, project_store=Mock())
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(_w4_request())
    assert error.value.code == "SIMULATOR_FIXTURE_REJECTED"
    assert not any(call[0] == "execute" for call in provider.calls)


@pytest.mark.parametrize("invalid", ["missing", "project", "fixture", "failed", "name", "digest"])
def test_explicit_firmware_output_validation(invalid):
    import hashlib
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError

    kernel, files = Mock(), Mock()
    data = b"\x7fELF\x00test"
    output = {
        "projectId": "proj_test",
        "outputId": "out_test",
        "executionRunId": "exec_test",
        "workspaceId": "ws_test",
        "name": ".pio/build/nexus/firmware.elf",
        "content": {"kind": "storage-reference", "uri": "hash"},
        "contentDigest": "sha256:" + hashlib.sha256(data).hexdigest(),
    }
    run = {
        "projectId": "proj_test",
        "executionRunId": "exec_test",
        "status": "completed",
        "outputReferences": ["out_test"],
    }
    spec = {"executable": "pio", "arguments": ["run", "-e", "nexus"]}
    if invalid == "project":
        output["projectId"] = "proj_other"
    if invalid == "fixture":
        spec["executable"] = "python3"
    if invalid == "failed":
        run["status"] = "failed"
    if invalid == "name":
        output["name"] = "firmware.bin"
    if invalid == "digest":
        output["contentDigest"] = "wrong"
    kernel.get_produced_output.return_value = output
    kernel.get_execution_run.return_value = run
    kernel.get_workspace.return_value = {"artifactType": "firmware"}
    kernel.get_execution_job_by_run.return_value = {"commandSpec": spec}
    files.get.return_value = data
    adapter = CircuitSimulationExecutionAdapter(
        provider=Mock(), project_store=Mock(), kernel_store=kernel, file_store=files
    )
    request = _w4_request()
    if invalid != "missing":
        request["options"] = {"firmwareOutputId": "out_test"}
    with pytest.raises(CircuitExecutionError) as error:
        adapter._resolve_firmware(request)
    assert error.value.code in {"FIRMWARE_ELF_REQUIRED", "FIRMWARE_ELF_INVALID"}


@pytest.mark.parametrize("scenario", ["empty", "truncated", "failed"])
def test_simulation_requires_successful_complete_observations(scenario):
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError, ExecutionOutput, ExecutionResult

    provider = Mock()
    provider.availability.return_value.ready = True
    provider.availability.return_value.provider = "wokwi"
    provider.assess_support.return_value.status = "SUPPORTED"
    provider.validate.return_value.valid = True
    provider.validate.return_value.findings = ()
    observations = (
        ()
        if scenario == "empty"
        else (ExecutionOutput("serial.log", b"TEL,0,0,0,1", truncated=True),)
    )
    provider.execute.return_value = ExecutionResult(
        succeeded=scenario != "failed",
        exit_code=1 if scenario == "failed" else 0,
        timed_out=False,
        outputs=observations,
    )
    adapter = CircuitSimulationExecutionAdapter(provider=provider, project_store=Mock())
    adapter._resolve_firmware = Mock(return_value=({"outputId": "out_test"}, b"\x7fELF"))
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(_w4_request())
    assert error.value.code == (
        "SIMULATION_FAILED" if scenario == "failed" else "SIMULATION_OBSERVATIONS_MISSING"
    )


def _live_simulation_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Four reviewed roles, only two approved for materialization."""
    components: dict[str, Any] = {"componentRoles": [], "candidates": [], "selectionDecisions": []}
    electrical: dict[str, Any] = {"nodes": [], "connections": []}
    for role, manufacturer, part in (
        ("mcu", "Espressif", "ESP32-DEVKIT-V1"),
        ("imu", "InvenSense", "MPU6050"),
        ("power", "Fixture Power", "FX-REG-33"),
        ("serial", "Espressif", "ESP32-DEVKIT-V1"),
    ):
        components["componentRoles"].append({"componentRoleId": role, "name": role})
        components["candidates"].append(
            {
                "candidateId": f"cand_{role}",
                "componentRoleId": role,
                "source": "fixture" if role == "power" else "agent-inference",
                "manufacturer": manufacturer,
                "partNumber": part,
            }
        )
        components["selectionDecisions"].append(
            {
                "selectionDecisionId": f"sel_{role}",
                "componentRoleId": role,
                "selectedCandidateId": f"cand_{role}",
            }
        )
        electrical["nodes"].append(
            {
                "nodeId": role,
                "componentCandidateId": f"cand_{role}",
                "componentRoleIds": [role],
                "interfaces": [{"interfaceType": "i2c"}],
            }
        )
    electrical["connections"] = [
        {
            "connectionId": "approved_i2c",
            "fromNodeId": "mcu",
            "toNodeId": "imu",
            "interfaceType": "i2c",
        },
        {
            "connectionId": "debug",
            "fromNodeId": "serial",
            "toNodeId": "mcu",
            "interfaceType": "uart",
        },
    ]
    approved = {
        "approvalStatus": "user-approved",
        "content": {
            "configuration": {
                "components": [
                    {"componentRoleId": role, "candidateId": f"cand_{role}"}
                    for role in ("mcu", "imu")
                ],
                "i2c": {"connectionId": "approved_i2c", "sdaPin": 21, "sclPin": 22},
            }
        },
    }
    return {"content": electrical}, {"content": components}, approved


def test_materialization_scopes_approved_configuration_without_mutating_review_plan() -> None:
    import copy
    import json

    from nexus_api.circuit_simulation import materialization_request
    from nexus_circuit_simulation import SupportStatus, WokwiProvider

    electrical, components, approved = _live_simulation_inputs()
    original = copy.deepcopy((electrical, components, approved))
    provider = WokwiProvider()
    full = materialization_request(
        electrical_artifact=electrical, component_plan_artifact=components
    )
    assert provider.assess_support(full).status == SupportStatus.PARTIALLY_SUPPORTED
    scoped = materialization_request(
        electrical_artifact=electrical,
        component_plan_artifact=components,
        execution_plan_artifact=approved,
    )
    assert provider.assess_support(scoped).status == SupportStatus.SUPPORTED
    assert [
        c["connectionId"]
        for c in cast(dict[str, Any], scoped.electrical_architecture["content"])["connections"]
    ] == ["approved_i2c"]
    diagram = json.loads(provider.materialize(scoped).files["diagram.json"])
    assert [(p["id"], p["type"]) for p in diagram["parts"]] == [
        ("imu1", "wokwi-mpu6050"),
        ("mcu1", "wokwi-esp32-devkit-v1"),
    ]
    assert diagram["connections"][:4] == [
        ["mcu1:3V3", "imu1:VCC", "red", []],
        ["mcu1:GND.1", "imu1:GND", "black", []],
        ["mcu1:D21", "imu1:SDA", "green", []],
        ["mcu1:D22", "imu1:SCL", "blue", []],
    ]
    assert (electrical, components, approved) == original
    approved["approvalStatus"] = "proposed"
    unapproved = materialization_request(
        electrical_artifact=electrical,
        component_plan_artifact=components,
        execution_plan_artifact=approved,
    )
    assert unapproved == full


def test_approved_unmapped_component_still_fails_architecture_support() -> None:
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError, WokwiProvider

    electrical, components, approved = _live_simulation_inputs()
    components["content"]["candidates"][1]["partNumber"] = "UNMAPPED-IMU"
    store = Mock()
    store.get_artifact.side_effect = lambda _pid, kind: (
        approved if kind == "execution-plan" else components
    )
    adapter = CircuitSimulationExecutionAdapter(provider=WokwiProvider(), project_store=store)
    request = _w4_request()
    request["snapshot"]["content"]["structuredContent"] = electrical["content"]
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(request)
    assert error.value.code == "ARCHITECTURE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_simulate_approved_pair_with_unapproved_fixture_roles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import copy
    import json
    from unittest.mock import Mock

    from nexus_api import main
    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import RunnerRequest, RunnerResult, WokwiProvider
    from test_actionable_execution_plan import _command, _propose, _setup
    from test_golden_lifecycle_http_api import AUTH, _acquire_lease, _actor, _binding

    actor = _actor()
    captured: list[dict[str, Any]] = []

    class Runner:
        def run(self, request: RunnerRequest) -> RunnerResult:
            if request.arguments[0] == "lint":
                return RunnerResult(exit_code=0, timed_out=False)
            captured.append(json.loads(request.files["diagram.json"]))
            return RunnerResult(
                exit_code=0, timed_out=False, outputs={"serial.log": b"TEL,0,0,0,1\n"}
            )

    executable = tmp_path / "wokwi-cli"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    provider = WokwiProvider(executable=executable, token="regression-only", runner=Runner())
    monkeypatch.setattr(main, "_wokwi_provider", provider)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, configuration = await _setup(client, actor)
        proposal = (await _propose(client, pid, actor, configuration)).json()
        accepted = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            proposal["workspace"],
            {"proposalId": proposal["commandResult"]["proposalId"]},
        )
        assert accepted["status"] == "completed", accepted
        original_get = main._store.get_artifact
        components = copy.deepcopy(original_get(pid, "component-plan"))
        for candidate in components["content"]["candidates"]:
            candidate["manufacturer"] = (
                "Espressif" if candidate["partNumber"] == "ESP32-DEVKIT-V1" else "InvenSense"
            )
        _, extras, _ = _live_simulation_inputs()
        for key in ("componentRoles", "candidates", "selectionDecisions"):
            components["content"][key].extend(extras["content"][key][2:])

        def get_artifact(project_id: str, kind: str, **kwargs: Any) -> dict[str, Any]:
            if project_id == pid and kind == "component-plan":
                return cast(dict[str, Any], components)
            return cast(dict[str, Any], original_get(project_id, kind, **kwargs))

        monkeypatch.setattr(main._store, "get_artifact", get_artifact)
        support = await client.get(
            f"/v1/projects/{pid}/artifacts/electrical-architecture/circuit-simulation/support"
        )
        assert support.status_code == 200, support.text
        assert support.json()["assessment"]["status"] == "FIRMWARE_REQUIRED"
        adapter = CircuitSimulationExecutionAdapter(provider=provider, project_store=main._store)
        monkeypatch.setattr(
            adapter,
            "_resolve_firmware",
            Mock(
                return_value=(
                    {"outputId": "out_regression", "executionRunId": "exec_regression"},
                    b"\x7fELF\x00REGRESSION",
                )
            ),
        )
        monkeypatch.setitem(
            main._kernel.executions._capability_executors, "circuit-simulation", adapter
        )
        binding = (await _binding(client, pid, "electrical-architecture"))["binding"]
        await _acquire_lease(client, pid, binding, actor)
        snapshot = await _command(
            client,
            pid,
            actor,
            "workspace.create-snapshot",
            binding,
            {"reason": "before-simulation"},
        )
        result = await _command(
            client,
            pid,
            actor,
            "artifact.execute",
            binding,
            {
                "snapshotId": snapshot["snapshotId"],
                "capability": "circuit-simulation",
                "executionMode": "simulate",
            },
        )
        assert result["status"] in {"completed", "completed-with-warnings"}, result
        assert len(captured) == 1
        assert {p["type"] for p in captured[0]["parts"]} == {
            "wokwi-esp32-devkit-v1",
            "wokwi-mpu6050",
        }
        assert len(captured[0]["parts"]) == 2
        assert [wire[:2] for wire in captured[0]["connections"][:4]] == [
            ["mcu1:3V3", "imu1:VCC"],
            ["mcu1:GND.1", "imu1:GND"],
            ["mcu1:D21", "imu1:SDA"],
            ["mcu1:D22", "imu1:SCL"],
        ]
