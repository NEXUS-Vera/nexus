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
from nexus_board.firmware import toolchain
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
    await _build_fault_repair_http(monkeypatch, "F2", sampling_hz)


@pytest.mark.asyncio
async def test_scripted_offline_full_scope_f1_repair_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ticking_http_loop: None
) -> None:
    # Extend only this test's subprocess stub: fail on the actual missing header,
    # then delegate successful builds to the existing offline compiler.
    stub = tmp_path / "platformio_f1_stub.py"
    stub.write_text(
        "import runpy, sys\n"
        "from pathlib import Path\n"
        "source = Path('src/main.cpp').read_text()\n"
        "if sys.argv[1] == 'run' and '#include <Wire.h>' not in source.splitlines():\n"
        "    print(\"src/main.cpp:1:1: error: 'Wire' was not declared in this scope\", "
        "file=sys.stderr)\n"
        "    sys.exit(1)\n"
        f"runpy.run_path({str(toolchain._STUB_SCRIPT)!r}, run_name='__main__')\n"
    )
    monkeypatch.setattr(toolchain, "_STUB_SCRIPT", stub)
    await _build_fault_repair_http(monkeypatch, "F1", 50)


async def _build_fault_repair_http(
    monkeypatch: pytest.MonkeyPatch, fault: str, sampling_hz: int
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
        assert payload["fileContents"]["src/main.cpp"] == faulty
        if fault == "F1":
            assert "#include <Wire.h>" not in faulty.splitlines()
            assert "'Wire' was not declared" in payload["requestedChange"]
        else:
            assert "Wire.begn(" in faulty
            assert "NEXUS_COMPILE_ERROR" in faulty
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
        # Faults enter through the normal user file route, never the model stub.
        original = (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ]
        assert "Wire.begin(" in original
        if fault == "F1":
            assert "#include <Wire.h>\n" in original
            faulty = original.replace("#include <Wire.h>\n", "", 1)
            faulty += "\n// F1 user fault injection: remove the Wire header include\n"
            assert "NEXUS_COMPILE_ERROR" not in faulty
        else:
            # The existing F2 stub needs its documented error marker.
            faulty = original.replace("Wire.begin(", "Wire.begn(", 1)
            faulty += (
                "\n// F2 user fault injection: Wire.begin -> Wire.begn\n// NEXUS_COMPILE_ERROR\n"
            )
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
        assert (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ] == faulty
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


@pytest.mark.asyncio
async def test_scripted_offline_full_scope_f4_simulation_repair_http(
    monkeypatch: pytest.MonkeyPatch, ticking_http_loop: None
) -> None:
    await _runtime_fault_repair_http(monkeypatch, "F4")


@pytest.mark.asyncio
async def test_scripted_offline_full_scope_f5_analysis_criteria_repair_http(
    monkeypatch: pytest.MonkeyPatch, ticking_http_loop: None
) -> None:
    await _runtime_fault_repair_http(monkeypatch, "F5")


async def _runtime_fault_repair_http(monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    """Fixture compiler/simulator, real seeded analysis, explicit promotion and approval."""
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    kernel = main._kernel
    user = _actor()
    # The fixture ELF does not encode source. Resolve its immutable compile
    # snapshot at the simulator boundary, never mutate source in the model stub.
    firmware = {"content": ""}
    simulated_sources: list[str] = []
    serial_outputs: list[bytes] = []

    class Runner:
        def run(self, request: Any) -> RunnerResult:
            if request.arguments[0] == "lint":
                return RunnerResult(exit_code=0, timed_out=False)
            assert request.files["firmware.elf"] == b"\x7fELF\x01NEXUS_FIRMWARE_STUB"
            source = firmware["content"]
            simulated_sources.append(source)
            rate = 25 if "SAMPLE_INTERVAL_MS = 40;" in source else 50
            telemetry = (
                b"NEXUS_MPU_INIT_FAIL\n"
                if "MPU_ADDR = 0x69;" in source
                else (
                    b"NEXUS_MPU_READY\ntime_s,accel_x_g,accel_y_g,accel_z_g\n"
                    + b"".join(
                        (
                            f"TEL,{i / rate:.3f},{0.01 if i % 2 else -0.01:.5f},0.00000,1.00000\n"
                        ).encode()
                        for i in range(100)
                    )
                )
            )
            serial_outputs.append(telemetry)
            return RunnerResult(exit_code=0, timed_out=False, outputs={"serial.log": telemetry})

    adapter = CircuitSimulationExecutionAdapter(
        provider=WokwiProvider(executable=sys.executable, token="regression-only", runner=Runner()),
        project_store=kernel.project_store,
        kernel_store=kernel.kernel_store,
        file_store=kernel.filesystem.file_store,
    )

    def resolve_fixture_firmware(request: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        output_id = request["options"]["firmwareOutputId"]
        output = kernel.workspace_runtime.get_output(
            project_id=request["projectId"], output_id=output_id
        )
        run = kernel.executions.get_run(output["executionRunId"])
        assert run["status"] == "completed"
        assert output_id in run["outputReferences"]
        assert output["name"] == ".pio/build/nexus/firmware.elf"
        firmware["content"] = kernel.workspace_runtime.read_firmware_snapshot_file(
            project_id=request["projectId"],
            artifact_type="firmware",
            snapshot_id=run["inputSnapshotId"],
            path="src/main.cpp",
        )["content"]
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
    monkeypatch.setitem(
        capabilities._capabilities,
        "circuit-simulation",
        {**capabilities.get("circuit-simulation"), "available": True},
    )
    gateway = FakeModelGateway()
    requests: list[Any] = []

    def correction(_task: Any, payload: Any, _schema: Any) -> dict[str, Any]:
        requests.append(payload)
        assert payload["serialContract"] == IMU_SERIAL_CONTRACT
        assert payload["fileContents"]["src/main.cpp"] == faulty
        assert failed_run["executionRunId"] in payload["requestedChange"]
        assert failed_case["testId"] in payload["requestedChange"]
        assert "FAIL" in payload["requestedChange"]
        assert ("NEXUS_MPU_INIT_FAIL" if fault == "F4" else "sampling_hz") in payload[
            "requestedChange"
        ]
        return {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": original}
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
        analysis_root = f"{prefix}/artifacts/analysis/workspace"

        async def post(url: str, body: dict[str, Any]) -> dict[str, Any]:
            response = await client.post(url, json={"requestedBy": user, **body})
            assert response.status_code == 200, response.text
            return dict(response.json())

        async def cases() -> dict[str, Any]:
            response = await client.get(f"{prefix}/artifacts/test-plan")
            assert response.status_code == 200, response.text
            return {c["displayId"]: c for c in response.json()["content"]["testCases"]}

        for kind in ("analysis", "electrical-architecture"):
            response = await client.get(f"{prefix}/artifacts/{kind}/workspace/runtime")
            assert response.status_code == 200, response.text
            await _command(
                client, pid, user, "workspace.acquire-edit-lease", response.json()["binding"], {}
            )
        seeded = (await client.get(f"{analysis_root}/file", params={"path": "analysis.py"})).json()[
            "content"
        ]
        # Approved-plan materialization supplies a skeleton. Author the golden
        # sensor implementation through the same user workspace route first.
        original = (
            Path(__file__).parents[3]
            / "packages/board/tests/golden/esp32_imu_vibration_monitor/main.cpp"
        ).read_text()
        draft_version = await _put_file(
            client,
            pid,
            runtime["binding"],
            runtime["draft"]["draftVersion"],
            user,
            "src/main.cpp",
            original.encode(),
        )
        before, after = (
            ("MPU_ADDR = 0x68;", "MPU_ADDR = 0x69;")
            if fault == "F4"
            else ("SAMPLE_INTERVAL_MS = 20;", "SAMPLE_INTERVAL_MS = 40;")
        )
        assert before in original
        label = (
            "wrong MPU6050 I2C address (0x69 instead of 0x68)"
            if fault == "F4"
            else "slow sampling interval 40 ms (25 Hz instead of 50 Hz)"
        )
        faulty = (
            original.replace(before, after, 1) + f"\n// {fault} user fault injection: {label}\n"
        )
        await _put_file(
            client,
            pid,
            runtime["binding"],
            draft_version,
            user,
            "src/main.cpp",
            faulty.encode(),
        )
        compiled = await post(f"{root}/compile", {"requireReal": False})
        assert compiled["toolchainProfile"]["executionMode"] == "fixture"
        compile_run = await _wait_run(client, pid, compiled["executionRun"]["executionRunId"])
        assert compile_run["status"] == "completed"
        outputs = (await client.get(f"{prefix}/outputs")).json()["items"]
        elf = next(
            o
            for o in outputs
            if o["name"] == ".pio/build/nexus/firmware.elf"
            and o["executionRunId"] == compile_run["executionRunId"]
        )
        sim_root = f"{prefix}/artifacts/electrical-architecture/workspace"
        binding = (await client.get(f"{sim_root}/runtime")).json()["binding"]
        snapshot = await _command(
            client, pid, user, "workspace.create-snapshot", binding, {"reason": "before-execution"}
        )
        sim = await _command(
            client,
            pid,
            user,
            "artifact.execute",
            binding,
            {
                "snapshotId": snapshot["snapshotId"],
                "capability": "circuit-simulation",
                "firmwareOutputId": elf["outputId"],
            },
        )
        sim_run = await _wait_run(client, pid, sim["executionRunId"])
        assert sim_run["status"] == "completed"
        assert sim_run["inputOutputReferences"] == [elf["outputId"]]
        # G1: completed runs require explicit evidence promotion before repair.
        await post(
            f"{prefix}/verify/promote-execution",
            {"executionRunId": sim_run["executionRunId"], "accept": True},
        )
        simulation_cases = await cases()
        for cid in ("T1", "T4", "T5"):
            assert simulation_cases[cid]["assessment"] == ("FAIL" if fault == "F4" else "PASS")
        failed_run = sim_run
        if fault == "F5":
            outputs = (await client.get(f"{prefix}/outputs")).json()["items"]
            serial = next(
                o
                for o in outputs
                if o["name"] == "serial.log" and o["executionRunId"] == sim_run["executionRunId"]
            )
            current = (await client.get(f"{analysis_root}/runtime")).json()
            project = (await client.get(prefix)).json()
            await post(
                f"{analysis_root}/inputs/import-produced-output",
                {
                    "path": "data/serial.log",
                    "outputId": serial["outputId"],
                    "expectedDraftVersion": current["draft"]["draftVersion"],
                    "baseArtifactVersion": current["binding"]["baseArtifactVersion"],
                    "baseProjectStateVersion": project["project"]["currentStateVersion"],
                },
            )
            analyzed = await post(f"{analysis_root}/run", {"requireReal": False})
            failed_run = await _wait_run(client, pid, analyzed["executionRun"]["executionRunId"])
            assert failed_run["status"] == "completed"
            await post(
                f"{prefix}/verify/promote-execution",
                {"executionRunId": failed_run["executionRunId"], "accept": True},
            )
        failed_case = (await cases())["T1" if fault == "F4" else "T6"]
        assert failed_case["assessment"] == "FAIL"
        assert failed_case["status"] == "failed"
        if fault == "F5":
            assert float(failed_case["actualResult"].split()[0]) == pytest.approx(25)
        state = await post(
            f"{prefix}/repair",
            {
                "action": "start",
                "executionRunId": failed_run["executionRunId"],
                "target": "firmware",
                "requireReal": False,
            },
        )
        assert (state["status"], state["stage"]) == (
            "inspect",
            "simulate" if fault == "F4" else "analyze",
        )

        async def advance() -> dict[str, Any]:
            return await post(
                f"{prefix}/repair",
                {"action": "advance", "repairId": state["repairId"], "revision": state["revision"]},
            )

        state = await advance()
        assert state["status"] == "review", state
        diagnostics = state["attempts"][0]["diagnostics"]
        assert any(
            c["testId"] == failed_case["testId"] and c["assessment"] == "FAIL"
            for c in diagnostics["testCases"]
        )
        if fault == "F4":
            assert diagnostics["logExcerpt"] == ""  # Synchronous simulation has no execution job.
            assert "NEXUS_MPU_INIT_FAIL" in diagnostics["testCases"][0]["actualResult"]
        assert await advance() == state
        assert (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ] == faulty
        current = (await client.get(f"{root}/runtime")).json()
        project = (await client.get(prefix)).json()
        await post(
            f"{root}/patch/apply",
            {
                "proposalId": state["proposalId"],
                "expectedDraftVersion": current["draft"]["draftVersion"],
                "baseArtifactVersion": current["binding"]["baseArtifactVersion"],
                "baseProjectStateVersion": project["project"]["currentStateVersion"],
            },
        )
        assert (await client.get(f"{root}/file", params={"path": "src/main.cpp"})).json()[
            "content"
        ] == original
        for stage in ("compile", "simulate", "analyze"):
            state = await advance()
            assert (state["status"], state["stage"]) == ("running", stage), state
            run = await _wait_run(client, pid, state["runId"])
            assert run["status"] in {"completed", "completed-with-warnings"}, run
            if stage == "simulate":
                assert run["inputOutputReferences"] == [state["firmwareOutputId"]]
        state = await advance()
        assert state["status"] == "completed", state
        assert state["evidenceMode"] == "regression"
        assert len(requests) == 1
        assert simulated_sources == [faulty, original]
        final_cases = await cases()
        for cid in ("T1", "T4", "T5", "T6", "T7", "T8"):
            assert final_cases[cid]["assessment"] == "PASS", final_cases[cid]
            assert final_cases[cid]["status"] == "passed"
            assert final_cases[cid]["assessmentAuthority"] == "deterministic-code"
        outputs = (await client.get(f"{prefix}/outputs")).json()["items"]
        summary_output = next(
            o
            for o in outputs
            if o["name"] == "outputs/summary.json" and o["executionRunId"] == state["runId"]
        )
        preview = await client.get(f"{analysis_root}/outputs/{summary_output['outputId']}/preview")
        assert preview.status_code == 200, preview.text
        summary = json.loads(preview.json()["text"])
        assert summary["sampling_hz"] == pytest.approx(50)
        assert summary["inputSha256"] == hashlib.sha256(serial_outputs[-1]).hexdigest()
        assert (await client.get(f"{analysis_root}/file", params={"path": "analysis.py"})).json()[
            "content"
        ] == seeded
