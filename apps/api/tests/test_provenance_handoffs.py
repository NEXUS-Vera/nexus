"""W6 regression evidence: scripted compiler/simulator, real Python, HTTP traversal."""

import importlib
import os
import secrets
from dataclasses import replace

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
from nexus_circuit_simulation import RunnerResult, WokwiProvider
from test_golden_lifecycle_http_api import (
    AUTH,
    GOLDEN_DIR,
    GOLDEN_PROMPT,
    _acquire_lease,
    _actor,
    _binding,
    run_golden_lifecycle_over_http,
)


@pytest.mark.asyncio
async def test_http_provenance_handoffs_survive_sqlite_restart(monkeypatch, tmp_path):
    from nexus_board.execution import process_runtime

    pio = tmp_path / "pio"
    pio.write_text(
        "#!/usr/bin/env python3\nfrom pathlib import Path\n"
        "p = Path('.pio/build/nexus')\np.mkdir(parents=True, exist_ok=True)\n"
        "(p / 'firmware.elf').write_bytes(b'\\x7fELF\\x00REGRESSION')\n"
        "(p / 'firmware.bin').write_bytes(b'REGRESSION')\n"
    )
    pio.chmod(0o755)
    environment = process_runtime.build_sandbox_environment

    def regression_environment(entries):
        env = environment(entries)
        env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
        return env

    monkeypatch.setattr(process_runtime, "build_sandbox_environment", regression_environment)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    original = main.settings
    monkeypatch.setattr(
        "nexus_api.config.settings",
        replace(
            original,
            file_store_root=str(tmp_path / "files"),
            storage_backend="sqlite",
            database_url=f"sqlite:///{tmp_path / 'w6.db'}",
        ),
    )
    telemetry = b"NEXUS_MPU_READY\n" + b"".join(
        b"TEL," + line + b"\n"
        for line in (GOLDEN_DIR / "stationary_imu.csv").read_bytes().splitlines()[1:]
    )
    consumed = []

    class Runner:
        def run(self, request):
            if request.arguments[0] == "lint":
                return RunnerResult(exit_code=0, timed_out=False)
            consumed.append(request.files["firmware.elf"])
            return RunnerResult(exit_code=0, timed_out=False, outputs={"serial.log": telemetry})

    async def simulate(client, pid, actor, outputs):
        elf = next(o for o in outputs if o["name"].endswith("firmware.elf"))
        provider = WokwiProvider(executable=pio, token="regression-only", runner=Runner())
        main._kernel.executions._capability_executors["circuit-simulation"] = (
            CircuitSimulationExecutionAdapter(
                provider=provider,
                project_store=main._store,
                kernel_store=main._kernel_store,
                file_store=main._file_store,
            )
        )
        monkeypatch.setitem(
            main._capabilities._capabilities,
            "circuit-simulation",
            {
                "schemaVersion": "1.0.0",
                "capabilityId": "circuit-simulation",
                "displayName": "Regression simulator",
                "providerId": "wokwi",
                "available": True,
            },
        )
        binding = (await _binding(client, pid, "electrical-architecture"))["binding"]
        await _acquire_lease(client, pid, binding, actor)

        async def command(kind, data):
            response = await client.post(
                f"/v1/projects/{pid}/artifact-commands",
                json={
                    "schemaVersion": "1.0.0",
                    "commandId": f"cmd_{secrets.token_hex(16)}",
                    "commandType": kind,
                    "projectId": pid,
                    **{
                        k: binding[k]
                        for k in (
                            "artifactId",
                            "workspaceId",
                            "baseArtifactVersion",
                            "baseProjectStateVersion",
                        )
                    },
                    "requestedBy": actor,
                    "requestedAt": "2026-10-23T00:00:00Z",
                    "input": data,
                },
            )
            assert response.status_code == 200, response.text
            return response.json()

        snapshot = await command("workspace.create-snapshot", {"reason": "before-simulation"})
        result = await command(
            "artifact.execute",
            {
                "snapshotId": snapshot["snapshotId"],
                "capability": "circuit-simulation",
                "firmwareOutputId": elf["outputId"],
            },
        )
        assert result["status"] in {"completed", "completed-with-warnings"}, result
        assert consumed == [b"\x7fELF\x00REGRESSION"]
        items = (await client.get(f"/v1/projects/{pid}/outputs")).json()["items"]
        serial = next(o for o in items if o["name"] == "serial.log")
        assert serial["content"]["structuredResult"]["text"].encode() == telemetry
        assert elf["outputId"] in serial["provenance"]["derivedFromIds"]
        return serial

    async def capture(pid):
        prefix = f"/v1/projects/{pid}"
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client:
            result = {}
            for route in (
                "artifacts/requirement-set",
                "artifacts/electrical-architecture",
                "artifacts/test-plan",
                "outputs",
                "verify/evidence-chain",
            ):
                response = await client.get(f"{prefix}/{route}")
                assert response.status_code == 200, response.text
                result[route] = response.json()
            outputs = result["outputs"]["items"]
            run_ids = {o["executionRunId"] for o in outputs}
            for rid in sorted(run_ids):
                response = await client.get(f"{prefix}/executions/{rid}")
                assert response.status_code == 200, response.text
                run = response.json()["executionRun"]
                result[rid] = run
            for kind in ("firmware", "analysis"):
                route = f"artifacts/{kind}/workspace/snapshots"
                response = await client.get(f"{prefix}/{route}")
                assert response.status_code == 200, response.text
                result[route] = response.json()
            for kind, path in (
                ("firmware", "src/main.cpp"),
                ("analysis", "data/serial.log"),
                ("analysis", "analysis.py"),
            ):
                run = next(
                    result[rid]
                    for rid in run_ids
                    if any(
                        o["executionRunId"] == rid
                        and o["name"]
                        == (
                            ".pio/build/nexus/firmware.elf"
                            if kind == "firmware"
                            else "outputs/summary.json"
                        )
                        for o in outputs
                    )
                )
                response = await client.get(
                    f"{prefix}/artifacts/{kind}/workspace/snapshots/{run['inputSnapshotId']}/file",
                    params={"path": path},
                )
                assert response.status_code == 200, response.text
                result[path] = response.json()
            case = next(
                c
                for c in result["artifacts/test-plan"]["content"]["testCases"]
                if c["displayId"] == "T7"
            )
            assert case["assessment"] == "PASS"
            assert case["applicability"]["state"] == "CURRENT"
            deps = case["verificationBasis"]["dependencies"]
            assert {
                "firmware",
                "electrical-architecture",
                "analysis",
                "requirement-set",
                "test-plan",
            } <= {d["artifactType"] for d in deps}
            for kind in ("firmware", "electrical-architecture", "analysis"):
                assert any(
                    d["artifactType"] == kind and d.get("snapshotId") and d["contentHash"]
                    for d in deps
                )
            assert result["data/serial.log"]["content"].encode() == telemetry
            summary = next(o for o in outputs if o["name"] == "outputs/summary.json")
            preview = await client.get(
                f"{prefix}/artifacts/analysis/workspace/outputs/{summary['outputId']}/preview"
            )
            assert preview.status_code == 200, preview.text
            import hashlib
            import json

            assert (
                json.loads(preview.json()["text"])["inputSha256"]
                == hashlib.sha256(telemetry).hexdigest()
            )
            result["summary"] = preview.json()
            elf = next(o for o in outputs if o["name"].endswith("firmware.elf"))
            preview = await client.get(
                f"{prefix}/artifacts/analysis/workspace/outputs/{elf['outputId']}/preview"
            )
            assert preview.status_code == 200, preview.text
            assert preview.json()["text"].encode() == consumed[0]
            assert not preview.json()["truncated"]
            result["elf"] = preview.json()
            return result

    try:
        importlib.reload(main)
        pid = await run_golden_lifecycle_over_http(monkeypatch, simulation_handoff=simulate)
        before = await capture(pid)
        # Foreign-project output import is rejected through the ordinary HTTP endpoint.
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client:
            other = await client.post(
                "/v1/projects/initialize",
                json={"message": GOLDEN_PROMPT, "autonomyMode": "collaborate"},
            )
            other_pid = other.json()["project"]["projectId"]
            serial = next(o for o in before["outputs"]["items"] if o["name"] == "serial.log")
            response = await client.post(
                f"/v1/projects/{other_pid}/artifacts/analysis/workspace/inputs/import-produced-output",
                json={
                    "outputId": serial["outputId"],
                    "path": "data/serial.log",
                    "requestedBy": _actor(),
                    "expectedDraftVersion": 1,
                    "baseArtifactVersion": 1,
                    "baseProjectStateVersion": 1,
                },
            )
            assert response.status_code in {404, 422}, response.text
            assert response.json()["error"]["code"] == "OUTPUT_NOT_FOUND"
        main._kernel.jobs.shutdown()
        importlib.reload(main)
        assert await capture(pid) == before
    finally:
        main._kernel.jobs.shutdown()
        monkeypatch.setattr("nexus_api.config.settings", original)
        importlib.reload(main)
