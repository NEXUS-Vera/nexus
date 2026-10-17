"""Golden ESP32 IMU vibration monitor lifecycle driven over HTTP only.

The in-process golden test (packages/board/tests/test_phase16i_golden_e2e.py)
drives ProjectKernel directly. This module drives the same G1 path the way an
external agent would: only public API routes, no ``_kernel`` access. Firmware
compile uses the deterministic stub; analysis.py really runs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import time
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

GOLDEN_DIR = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "board"
    / "tests"
    / "golden"
    / "esp32_imu_vibration_monitor"
)
GOLDEN_PROMPT = (
    "Build an ESP32-based vibration monitor using an MPU6050. "
    "It should stream acceleration telemetry and analyze stationary sensor noise "
    "to verify that accel_x RMS noise stays below 0.10 g."
)
ANALYSIS_OUTPUTS = ("outputs/summary.json", "outputs/processed.csv", "outputs/accel_plot.png")
TERMINAL = {"completed", "failed", "cancelled", "timed_out"}
AUTH = {"Authorization": "Bearer nexus-dev-session-token"}


def _actor() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "actorId": f"actor_{secrets.token_hex(8)}",
        "actorType": "user",
        "displayName": "User",
    }


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def _binding(client: AsyncClient, project_id: str, artifact_type: str) -> dict[str, Any]:
    resp = await client.get(
        f"/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/runtime"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _acquire_lease(
    client: AsyncClient, project_id: str, binding: dict[str, Any], actor: dict[str, Any]
) -> None:
    resp = await client.post(
        f"/v1/projects/{project_id}/artifact-commands",
        json={
            "schemaVersion": "1.0.0",
            "commandId": f"cmd_{secrets.token_hex(16)}",
            "commandType": "workspace.acquire-edit-lease",
            "projectId": project_id,
            "artifactId": binding["artifactId"],
            "workspaceId": binding["workspaceId"],
            "baseArtifactVersion": binding["baseArtifactVersion"],
            "baseProjectStateVersion": binding["baseProjectStateVersion"],
            "requestedBy": actor,
            "requestedAt": "2026-10-17T00:00:00Z",
            "input": {},
        },
    )
    assert resp.status_code == 200, resp.text


def _versions(binding: dict[str, Any], draft_version: int) -> dict[str, int]:
    return {
        "expectedDraftVersion": draft_version,
        "baseArtifactVersion": binding["baseArtifactVersion"],
        "baseProjectStateVersion": binding["baseProjectStateVersion"],
    }


async def _put_file(
    client: AsyncClient,
    project_id: str,
    binding: dict[str, Any],
    draft_version: int,
    actor: dict[str, Any],
    path: str,
    content: bytes,
) -> int:
    resp = await client.put(
        f"/v1/projects/{project_id}/workspaces/{binding['workspaceId']}/file",
        json={
            "path": path,
            "contentBase64": _b64(content),
            "requestedBy": actor,
            "origin": "USER",
            "writePolicy": "USER_EDITABLE",
            **_versions(binding, draft_version),
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["draft"]["draftVersion"])


async def _wait_run(client: AsyncClient, project_id: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30.0
    run: dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = await client.get(f"/v1/projects/{project_id}/executions/{run_id}")
        assert resp.status_code == 200, resp.text
        run = resp.json()["executionRun"]
        if run["status"] in TERMINAL:
            return run
        await asyncio.sleep(0.05)
    return run


@pytest.mark.asyncio
async def test_golden_lifecycle_over_http_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    firmware_src = (GOLDEN_DIR / "main.cpp").read_bytes()
    analysis_src = (GOLDEN_DIR / "analysis.py").read_bytes()
    dataset = (GOLDEN_DIR / "stationary_imu.csv").read_bytes()
    actor = _actor()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        # 1. Initialize the golden project.
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GOLDEN_PROMPT, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200, created.text
        project_id = created.json()["project"]["projectId"]
        ensured = await client.post(
            f"/v1/projects/{project_id}/ensure-layered-architecture",
            json={"requestedBy": actor},
        )
        assert ensured.status_code == 200, ensured.text
        artifacts = await client.get(f"/v1/projects/{project_id}/artifacts")
        assert artifacts.status_code == 200, artifacts.text
        # initialize already materialized the layered architecture, so this is a no-op.
        assert ensured.json()["createdArtifactTypes"] == []
        types = {a["artifactType"] for a in artifacts.json()["artifacts"]}
        for required_type in (
            "requirement-set",
            "component-plan",
            "electrical-architecture",
            "test-plan",
        ):
            assert required_type in types, types

        # 2. Firmware: lease, scaffold, golden source, compile (stub).
        fw_body = await _binding(client, project_id, "firmware")
        fw = fw_body["binding"]
        await _acquire_lease(client, project_id, fw, actor)
        scaffold = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/scaffold",
            json={"requestedBy": actor, **_versions(fw, fw_body["draft"]["draftVersion"])},
        )
        assert scaffold.status_code == 200, scaffold.text
        draft = int(scaffold.json()["draft"]["draftVersion"])
        draft = await _put_file(client, project_id, fw, draft, actor, "src/main.cpp", firmware_src)
        await _put_file(
            client,
            project_id,
            fw,
            draft,
            actor,
            "platformio.ini",
            (GOLDEN_DIR / "platformio.ini").read_bytes(),
        )
        compiled = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/compile",
            json={"requestedBy": actor},
        )
        assert compiled.status_code == 200, compiled.text
        fw_run = await _wait_run(
            client, project_id, compiled.json()["executionRun"]["executionRunId"]
        )
        assert fw_run["status"] == "completed", fw_run
        fw_outputs = await client.get(
            f"/v1/projects/{project_id}/outputs",
        )
        assert fw_outputs.status_code == 200, fw_outputs.text
        fw_names = {
            o["name"]
            for o in fw_outputs.json()["items"]
            if o["executionRunId"] == fw_run["executionRunId"]
        }
        assert any("firmware.elf" in n for n in fw_names), fw_names

        # 3. Analysis: lease, scaffold, investigation, dataset upload, golden script.
        an_body = await _binding(client, project_id, "analysis")
        an = an_body["binding"]
        await _acquire_lease(client, project_id, an, actor)
        scaffold = await client.post(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/scaffold",
            json={"requestedBy": actor, **_versions(an, an_body["draft"]["draftVersion"])},
        )
        assert scaffold.status_code == 200, scaffold.text
        assert "analysis.py" in {f["path"] for f in scaffold.json()["generatedFiles"]}
        draft = int(scaffold.json()["draft"]["draftVersion"])
        uploaded = await client.post(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/inputs/upload",
            json={
                "path": "data/stationary_imu.csv",
                "contentBase64": _b64(dataset),
                "mediaType": "text/csv",
                "requestedBy": actor,
                **_versions(an, draft),
            },
        )
        assert uploaded.status_code == 200, uploaded.text
        draft = int(uploaded.json()["draft"]["draftVersion"])
        draft = await _put_file(client, project_id, an, draft, actor, "analysis.py", analysis_src)

        # 4. Run analysis.py for real and wait for it.
        started = await client.post(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/run",
            json={"requestedBy": actor},
        )
        assert started.status_code == 200, started.text
        an_run = await _wait_run(
            client, project_id, started.json()["executionRun"]["executionRunId"]
        )
        assert an_run["status"] == "completed", an_run
        outs = await client.get(f"/v1/projects/{project_id}/outputs")
        run_outputs = [
            o for o in outs.json()["items"] if o["executionRunId"] == an_run["executionRunId"]
        ]
        names = {o["name"] for o in run_outputs}
        for required in ANALYSIS_OUTPUTS:
            assert required in names, names
        summary_out = next(o for o in run_outputs if o["name"] == "outputs/summary.json")
        preview = await client.get(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/outputs/"
            f"{summary_out['outputId']}/preview"
        )
        assert preview.status_code == 200, preview.text
        summary = json.loads(preview.json()["text"])
        assert summary["assessment"] == "PASS"
        assert summary["authority"] == "deterministic-code"
        assert summary["requirementId"] == "R7"
        assert summary["accel_x_rms_noise_g"] == pytest.approx(0.015676464092948383)

        # M3: the run traces to the exact immutable inputs, readable over HTTP.
        assert an_run["baseArtifactVersion"] == an["baseArtifactVersion"]
        assert an_run["baseProjectStateVersion"] == an["baseProjectStateVersion"]
        snapshot_url = (
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/snapshots/"
            f"{an_run['inputSnapshotId']}/file"
        )
        snap_csv = await client.get(snapshot_url, params={"path": "data/stationary_imu.csv"})
        assert snap_csv.status_code == 200, snap_csv.text
        assert snap_csv.json()["content"].encode() == dataset
        snap_py = await client.get(snapshot_url, params={"path": "analysis.py"})
        assert snap_py.status_code == 200, snap_py.text
        assert snap_py.json()["content"].encode() == analysis_src

        # 5. Promote the execution as evidence into an accepted Test Plan revision.
        before = await client.get(f"/v1/projects/{project_id}/artifacts/test-plan")
        assert before.status_code == 200, before.text
        promote_body = {
            "executionRunId": an_run["executionRunId"],
            "requestedBy": actor,
            "accept": True,
        }
        promoted = await client.post(
            f"/v1/projects/{project_id}/verify/promote-execution", json=promote_body
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["changed"] is True
        assert promoted.json()["accepted"] is True
        # K6 stays open (monitoring) without physical evidence.
        risks = promoted.json()["riskMitigationAnnotations"]
        assert next(r for r in risks if r["displayId"] == "K6")["status"] == "monitoring"
        after = await client.get(f"/v1/projects/{project_id}/artifacts/test-plan")
        assert after.status_code == 200, after.text
        assert after.json()["artifactVersion"] > before.json()["artifactVersion"]

        # 6. Evidence chain: R7/R8 VERIFIED, PASS by deterministic code, traced to the run.
        chain_resp = await client.get(f"/v1/projects/{project_id}/verify/evidence-chain")
        assert chain_resp.status_code == 200, chain_resp.text
        rows = {r["displayId"]: r for r in chain_resp.json()["requirementVerification"]}
        assert rows["R7"]["verificationState"] == "VERIFIED"
        assert rows["R8"]["verificationState"] == "VERIFIED"
        chain = chain_resp.json()["chains"]
        r7 = next(r for r in chain if r["requirementId"] == "R7")
        assert r7["testId"] == "T7"
        assert r7["assessment"] == "PASS"
        assert r7["assessmentAuthority"] == "deterministic-code"
        assert r7["criterion"]["metricId"] == "accel_x_rms_noise_g"
        assert r7["criterion"]["operator"] == "<"
        assert r7["criterion"]["expectedValue"] == 0.10
        assert r7["executionRunId"] == an_run["executionRunId"]
        for requirement_id in ("R7", "R8"):
            evidence = next(r for r in chain if r["requirementId"] == requirement_id)
            assert evidence["assessment"] == "PASS"
            assert any(
                ref["sourceId"] == an_run["executionRunId"]
                for ref in evidence["evidenceReferences"]
            )

        # Promoting the same run again is idempotent.
        again = await client.post(
            f"/v1/projects/{project_id}/verify/promote-execution", json=promote_body
        )
        assert again.status_code == 200, again.text
        assert again.json()["idempotent"] is True
        assert again.json()["changed"] is False
