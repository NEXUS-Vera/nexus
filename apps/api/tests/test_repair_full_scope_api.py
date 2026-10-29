"""Scripted offline full-loop HTTP regressions; never live acceptance evidence."""

import asyncio
import hashlib
import json
import sys
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
from nexus_board.firmware.live_patch_generator import (
    IMU_SERIAL_CONTRACT,
    LiveFirmwarePatchGenerator,
)
from nexus_circuit_simulation import RunnerResult, WokwiProvider
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_actionable_execution_plan import _command
from test_golden_lifecycle_http_api import AUTH, _actor, _put_file, _wait_run
from test_w3_firmware import _approved


@pytest.fixture
async def ticking_http_loop() -> AsyncIterator[None]:
    # As in test_http_repair_revision_and_validation, keep the loop ticking
    # where the managed runner restricts cross-thread socket wakeups.
    async def tick() -> None:
        while True:
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(tick())
    try:
        yield
    finally:
        ticker.cancel()
        with suppress(asyncio.CancelledError):
            await ticker


@pytest.mark.asyncio
@pytest.mark.parametrize("sampling_hz", [50, 25], ids=["completed", "inspect-slow-telemetry"])
async def test_scripted_offline_full_scope_f2_repair_http(
    monkeypatch: pytest.MonkeyPatch, sampling_hz: int, ticking_http_loop: None
) -> None:
    """Fake model/compiler/simulator, real seeded Python and deterministic assessments."""
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    kernel = main._kernel
    user = _actor()
    source = (
        Path(__file__).parents[3]
        / "packages/board/tests/golden/esp32_imu_vibration_monitor/main.cpp"
    ).read_text()
    telemetry = b"NEXUS_MPU_READY\ntime_s,accel_x_g,accel_y_g,accel_z_g\n" + b"".join(
        f"TEL,{i / sampling_hz:.3f},{0.01 if i % 2 else -0.01:.5f},0.00000,1.00000\n".encode()
        for i in range(100)
    )
    consumed = []

    class Runner:
        def run(self, request: Any) -> RunnerResult:
            if request.arguments[0] == "lint":
                return RunnerResult(exit_code=0, timed_out=False)
            assert request.files["firmware.elf"] == b"\x7fELF\x01NEXUS_FIRMWARE_STUB"
            consumed.append(request.files["firmware.elf"])
            return RunnerResult(exit_code=0, timed_out=False, outputs={"serial.log": telemetry})

    adapter = CircuitSimulationExecutionAdapter(
        provider=WokwiProvider(executable=sys.executable, token="regression-only", runner=Runner()),
        project_store=kernel.project_store,
        kernel_store=kernel.kernel_store,
        file_store=kernel.filesystem.file_store,
    )

    def resolve_fixture_firmware(request: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        # The production adapter deliberately rejects stub ELF/compile jobs. This
        # test-only simulator boundary accepts the exact linked stub output; no
        # production fixture guard is relaxed and this is not Wokwi/live evidence.
        output_id = request["options"]["firmwareOutputId"]
        output = kernel.workspace_runtime.get_output(
            project_id=request["projectId"], output_id=output_id
        )
        run = kernel.executions.get_run(output["executionRunId"])
        assert run["status"] == "completed"
        assert output_id in run["outputReferences"]
        assert output["name"] == ".pio/build/nexus/firmware.elf"
        content = output["content"]
        data = (
            kernel.filesystem.file_store.get(content["uri"])
            if content["kind"] == "storage-reference"
            else content["structuredResult"]["text"].encode()
        )
        if content["kind"] == "storage-reference":
            assert output["contentDigest"] == "sha256:" + hashlib.sha256(data).hexdigest()
        return output, data

    monkeypatch.setattr(adapter, "_resolve_firmware", resolve_fixture_firmware)
    monkeypatch.setitem(kernel.executions._capability_executors, "circuit-simulation", adapter)
    capabilities = kernel.executions._capabilities
    simulation = capabilities.get("circuit-simulation")
    monkeypatch.setitem(
        capabilities._capabilities, "circuit-simulation", {**simulation, "available": True}
    )
    gateway = FakeModelGateway()
    requests = []

    def correction(_task: Any, payload: Any, _schema: Any) -> dict[str, Any]:
        requests.append(payload)
        assert payload["serialContract"] == IMU_SERIAL_CONTRACT
        assert "Wire.begn(" in payload["fileContents"]["src/main.cpp"]
        assert "NEXUS_COMPILE_ERROR" in payload["fileContents"]["src/main.cpp"]
        assert failed["executionRunId"] in payload["requestedChange"]
        return {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": source}
            ]
        }

    gateway.set_script("firmware.patch-proposal", correction)
    monkeypatch.setattr(
        kernel.workspace_runtime,
        "_firmware_patch_generator",
        LiveFirmwarePatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, runtime, _plan = await _approved(client, user)
        prefix = f"/v1/projects/{pid}"
        for kind in ("analysis", "electrical-architecture"):
            response = await client.get(f"{prefix}/artifacts/{kind}/workspace/runtime")
            assert response.status_code == 200, response.text
            await _command(
                client, pid, user, "workspace.acquire-edit-lease", response.json()["binding"], {}
            )
        analysis_root = f"{prefix}/artifacts/analysis/workspace"
        seeded = (await client.get(f"{analysis_root}/file", params={"path": "analysis.py"})).json()[
            "content"
        ]
        assert "sampling_hz" in seeded
        # F2 is a labeled USER edit. The stub does not parse C++; its documented
        # error marker is needed in addition to Wire.begin -> Wire.begn.
        original = (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ]
        assert "Wire.begin(" in original
        faulty = original.replace("Wire.begin(", "Wire.begn(", 1)
        faulty += "\n// F2 user fault injection: Wire.begin -> Wire.begn\n// NEXUS_COMPILE_ERROR\n"
        await _put_file(
            client,
            pid,
            runtime["binding"],
            runtime["draft"]["draftVersion"],
            user,
            "src/main.cpp",
            faulty.encode(),
        )
        response = await client.post(
            f"{root}/compile", json={"requestedBy": user, "requireReal": False}
        )
        assert response.status_code == 200, response.text
        assert response.json()["toolchainProfile"]["executionMode"] == "fixture"
        failed = await _wait_run(client, pid, response.json()["executionRun"]["executionRunId"])
        assert failed["status"] == "failed", failed

        async def repair(**body: Any) -> dict[str, Any]:
            response = await client.post(f"{prefix}/repair", json={"requestedBy": user, **body})
            assert response.status_code == 200, response.text
            return dict(response.json())

        # This checkout predates the scope selector: full is already the default
        # workflow and unknown request fields are ignored. Assert its actual
        # compile/simulate/analyze sequence rather than trusting the scope field.
        state = await repair(
            action="start",
            executionRunId=failed["executionRunId"],
            target="firmware",
            scope="full",
            requireReal=False,
        )

        async def advance() -> dict[str, Any]:
            return await repair(
                action="advance", repairId=state["repairId"], revision=state["revision"]
            )

        state = await advance()
        assert state["status"] == "review", state
        assert len(requests) == 1
        assert "error:" in state["attempts"][0]["diagnostics"]["logExcerpt"]
        assert await advance() == state  # Repair never approves its own patch.
        current = (await client.get(f"{root}/runtime")).json()
        project = (await client.get(prefix)).json()
        response = await client.post(
            f"{root}/patch/apply",
            json={
                "proposalId": state["proposalId"],
                "requestedBy": user,
                "expectedDraftVersion": current["draft"]["draftVersion"],
                "baseArtifactVersion": current["binding"]["baseArtifactVersion"],
                "baseProjectStateVersion": project["project"]["currentStateVersion"],
            },
        )
        assert response.status_code == 200, response.text
        assert (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ] == source
        for stage in ("compile", "simulate", "analyze"):
            state = await advance()
            assert (state["status"], state["stage"]) == ("running", stage), json.dumps(state)
            run = await _wait_run(client, pid, state["runId"])
            assert run["status"] in {"completed", "completed-with-warnings"}, run
            if stage == "simulate":
                assert run["inputOutputReferences"] == [state["firmwareOutputId"]]
        state = await advance()
        assert state["status"] == ("completed" if sampling_hz == 50 else "inspect"), state
        assert state["evidenceMode"] == "regression"
        assert await repair(action="get", repairId=state["repairId"]) == state
        assert len(state["attempts"]) == 2
        assert len(state["attempts"][-1]["runIds"]) == 3
        assert len(consumed) == 1
        assert len(requests) == 1
        outputs = (await client.get(f"{prefix}/outputs")).json()["items"]
        summary_output = next(
            o
            for o in outputs
            if o["name"] == "outputs/summary.json" and o["executionRunId"] == state["runId"]
        )
        preview = await client.get(f"{analysis_root}/outputs/{summary_output['outputId']}/preview")
        assert preview.status_code == 200, preview.text
        summary = json.loads(preview.json()["text"])
        assert summary["inputPath"] == "data/serial.log"
        assert summary["inputSha256"] == hashlib.sha256(telemetry).hexdigest()
        assert summary["sampling_hz"] == pytest.approx(sampling_hz)
        assert summary["accel_x_rms_noise_g"] == pytest.approx(0.01)
        assert (await client.get(f"{analysis_root}/file", params={"path": "analysis.py"})).json()[
            "content"
        ] == seeded
        project = (await client.get(prefix)).json()
        requirements = next(
            a["content"]["requirements"]
            for a in project["artifacts"]
            if a["artifactType"] == "requirement-set"
        )
        ids = {r["requirementId"]: r["displayId"] for r in requirements}
        cases = next(
            a["content"]["testCases"]
            for a in project["artifacts"]
            if a["artifactType"] == "test-plan"
        )
        by_requirement = {
            ids.get(c["linkedRequirementIds"][0], c["linkedRequirementIds"][0]): c for c in cases
        }
        for rid in ("R1", "R4", "R5", "R6", "R7", "R8"):
            case = by_requirement[rid]
            expected = "FAIL" if rid == "R6" and sampling_hz == 25 else "PASS"
            assert case["assessment"] == expected, case
            assert case["status"] == ("passed" if expected == "PASS" else "failed"), case
            assert case["assessmentAuthority"] == "deterministic-code"
        # R2/R3 are inspection cases left ready/unassessed. Whether they must
        # block full-loop completion remains an open product question.
        for rid in ("R2", "R3"):
            assert by_requirement[rid]["verificationMethod"] == "inspection"
            assert by_requirement[rid]["status"] == "ready"
            assert "assessment" not in by_requirement[rid]
