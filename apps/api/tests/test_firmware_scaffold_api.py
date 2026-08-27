"""Phase 15B firmware scaffold API tests."""

from __future__ import annotations

import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app
from nexus_board.firmware.scaffold import MAIN_CPP_PATH, PLATFORMIO_INI_PATH

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
async def test_firmware_scaffold_api_generate_and_conflict() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200
        project_id = created.json()["project"]["projectId"]
        actor = _actor()

        binding_resp = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/runtime"
        )
        assert binding_resp.status_code == 200
        binding_body = binding_resp.json()
        binding = binding_body["binding"]
        draft_version = binding_body["draft"]["draftVersion"]

        lease = await client.post(
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
        assert lease.status_code == 200, lease.text

        generated = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/scaffold",
            json={
                "expectedDraftVersion": draft_version,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert generated.status_code == 200, generated.text
        body = generated.json()
        assert body["status"] == "generated"
        assert {f["path"] for f in body["generatedFiles"]} == {
            PLATFORMIO_INI_PATH,
            MAIN_CPP_PATH,
        }
        assert "event" not in body

        files = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/files"
        )
        assert files.status_code == 200
        assert {f["path"] for f in files.json()["files"]} == {
            PLATFORMIO_INI_PATH,
            MAIN_CPP_PATH,
        }

        main = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            params={"path": MAIN_CPP_PATH},
        )
        assert main.status_code == 200
        assert "Serial.begin(115200)" in main.json()["content"]

        # Exact re-run → already-generated.
        again = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/scaffold",
            json={
                "expectedDraftVersion": body["draft"]["draftVersion"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert again.status_code == 200
        assert again.json()["status"] == "already-generated"

        # Non-firmware type denied.
        denied = await client.post(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/scaffold",
            json={
                "expectedDraftVersion": 1,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": actor,
            },
        )
        assert denied.status_code == 422
        assert denied.json()["error"]["code"] == "WORKSPACE_RUNTIME_CAPABILITY_DENIED"
