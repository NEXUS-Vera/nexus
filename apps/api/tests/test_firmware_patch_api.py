"""Phase 15C firmware patch API tests."""

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
async def test_firmware_patch_propose_apply_and_stale() -> None:
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

        scaffold = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/scaffold",
            json={
                "expectedDraftVersion": draft_version,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert scaffold.status_code == 200, scaffold.text
        draft_version = scaffold.json()["draft"]["draftVersion"]

        before = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            params={"path": PLATFORMIO_INI_PATH},
        )
        assert before.status_code == 200
        before_content = before.json()["content"]

        proposed = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/propose",
            json={
                "allowFixture": True,
                "requestedChange": "Change serial baud to 9600.",
                "requestedBy": actor,
            },
        )
        assert proposed.status_code == 200, proposed.text
        proposal_body = proposed.json()
        assert proposal_body["status"] == "proposed"
        proposal = proposal_body["proposal"]
        assert proposal["baseSnapshotId"].startswith("snap_")
        assert len(proposal["operations"]) >= 1

        unchanged = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            params={"path": PLATFORMIO_INI_PATH},
        )
        assert unchanged.json()["content"] == before_content

        applied = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/apply",
            json={
                "proposalId": proposal["proposalId"],
                "expectedDraftVersion": draft_version,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["status"] == "applied"
        assert applied.json()["applySemantics"] == "sequential-non-atomic"

        after = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            params={"path": PLATFORMIO_INI_PATH},
        )
        assert "9600" in after.json()["content"]

        # Stale apply after manual edit.
        proposed2 = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/propose",
            json={
                "allowFixture": True,
                "requestedChange": "Change serial baud to 9600.",
                "requestedBy": actor,
            },
        )
        assert proposed2.status_code == 200
        proposal2 = proposed2.json()["proposal"]
        draft_version = proposed2.json().get("draft", {}).get("draftVersion", draft_version)

        manual = await client.put(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            json={
                "path": PLATFORMIO_INI_PATH,
                "content": after.json()["content"] + "# edited\n",
                "encoding": "utf-8",
                "expectedDraftVersion": applied.json()["draft"]["draftVersion"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
                "origin": "USER",
                "writePolicy": "USER_EDITABLE",
            },
        )
        assert manual.status_code == 200, manual.text

        stale = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/apply",
            json={
                "proposalId": proposal2["proposalId"],
                "expectedDraftVersion": manual.json()["draft"]["draftVersion"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "FIRMWARE_PATCH_STALE"


@pytest.mark.asyncio
async def test_firmware_patch_discard() -> None:
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
        draft_version = binding_resp.json()["draft"]["draftVersion"]
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
                "expectedDraftVersion": draft_version,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        proposed = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/propose",
            json={
                "allowFixture": True,
                "requestedChange": "Change serial baud to 9600.",
                "requestedBy": actor,
            },
        )
        proposal = proposed.json()["proposal"]
        discarded = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/discard",
            json={"proposalId": proposal["proposalId"], "requestedBy": actor},
        )
        assert discarded.status_code == 200
        assert discarded.json()["status"] == "discarded"

        main = await client.get(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/file",
            params={"path": MAIN_CPP_PATH},
        )
        assert "Serial.begin(115200)" in main.json()["content"]
