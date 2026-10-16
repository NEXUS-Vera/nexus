"""Phase 15E firmware compile/test API tests."""

from __future__ import annotations

import asyncio
import secrets
import time

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

GREENHOUSE = (
    "I want to build a greenhouse monitoring node that measures temperature, "
    "humidity, soil moisture, and light, and reports the readings remotely."
)


def _cmd_id() -> str:
    return f"cmd_{secrets.token_hex(16)}"


def _actor() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "actorId": f"actor_{secrets.token_hex(8)}",
        "actorType": "user",
        "displayName": "User",
    }


@pytest.mark.asyncio
async def test_firmware_compile_api_with_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        project_id = created.json()["project"]["projectId"]
        actor = _actor()
        binding_resp = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/runtime"
        )
        binding = binding_resp.json()["binding"]
        await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": binding["artifactId"],
                "workspaceId": binding["workspaceId"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
                "requestedAt": "2026-08-11T00:00:00Z",
                "input": {},
            },
        )
        await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/scaffold",
            json={
                "expectedDraftVersion": binding_resp.json()["draft"]["draftVersion"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        compiled = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/compile",
            json={"requestedBy": actor},
        )
        assert compiled.status_code == 200, compiled.text
        body = compiled.json()
        assert body["operation"] == "firmware.compile"
        run_id = body["executionRun"]["executionRunId"]
        deadline = time.monotonic() + 8.0
        status = "queued"
        while time.monotonic() < deadline:
            detail = await client.get(f"/v1/projects/{project_id}/executions/{run_id}")
            status = detail.json()["executionRun"]["status"]
            if status not in {"queued", "starting", "running"}:
                break
            await asyncio.sleep(0.05)
        assert status == "completed"
        logs = await client.get(
            f"/v1/projects/{project_id}/executions/{run_id}/logs",
            params={"after": 0},
        )
        assert "SUCCESS" in logs.text


@pytest.mark.asyncio
async def test_firmware_history_api() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        project_id = created.json()["project"]["projectId"]
        actor = _actor()
        binding = (
            await client.get(f"/v1/projects/{project_id}/artifacts/firmware/workspace/runtime")
        ).json()["binding"]
        await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": binding["artifactId"],
                "workspaceId": binding["workspaceId"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
                "requestedAt": "2026-08-11T00:00:00Z",
                "input": {},
            },
        )
        snap = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/snapshots",
            json={"reason": "manual", "requestedBy": actor},
        )
        assert snap.status_code == 200
        listed = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/snapshots"
        )
        assert len(listed.json()["snapshots"]) >= 1
