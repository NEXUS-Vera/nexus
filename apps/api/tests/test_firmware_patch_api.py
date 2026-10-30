"""Phase 15C firmware patch API tests."""

from __future__ import annotations

import secrets
from typing import Any

import pytest
from helpers import seed_approved_firmware_plan
from httpx import ASGITransport, AsyncClient
from nexus_api import main as api_main
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
        seed_approved_firmware_plan(api_main._kernel.workspace_runtime._projects, project_id)
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
        seed_approved_firmware_plan(api_main._kernel.workspace_runtime._projects, project_id)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("approval", [None, "proposed", "rejected"])
async def test_firmware_patch_requires_approved_plan(
    approval: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    from test_golden_lifecycle_http_api import AUTH

    runtime = api_main._kernel.workspace_runtime
    generator = Mock()
    monkeypatch.setattr(runtime, "_firmware_patch_generator", generator)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        project_id = created.json()["project"]["projectId"]
        if approval is not None:
            seed_approved_firmware_plan(runtime._projects, project_id)
            get_artifact = runtime._projects.get_artifact

            def get_unapproved(
                pid: str, kind: str, *, version: int | None = None
            ) -> dict[str, Any]:
                artifact = get_artifact(pid, kind, version=version)
                if kind == "execution-plan":
                    artifact["approvalStatus"] = approval
                return artifact

            monkeypatch.setattr(runtime._projects, "get_artifact", get_unapproved)
        snapshot = Mock(side_effect=AssertionError("No snapshot before approval"))
        monkeypatch.setattr(runtime, "create_snapshot", snapshot)
        response = await client.post(
            f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch/propose",
            json={"requestedChange": "Implement firmware", "allowFixture": True},
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "FIRMWARE_EXECUTION_PLAN_APPROVAL_REQUIRED"
        assert "Approve an execution plan first" in response.json()["error"]["message"]
        generator.generate.assert_not_called()
        snapshot.assert_not_called()


async def _create_patch_workspace(client: AsyncClient) -> tuple[str, dict, dict, int]:
    created = await client.post(
        "/v1/projects/initialize",
        json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["projectId"]
    seed_approved_firmware_plan(api_main._kernel.workspace_runtime._projects, project_id)
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

    return project_id, binding, actor, draft_version


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["proposed", "applied", "discarded"])
async def test_get_firmware_patch_proposal(status: str, monkeypatch: pytest.MonkeyPatch) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        project_id, binding, actor, draft_version = await _create_patch_workspace(client)
        root = f"/v1/projects/{project_id}/artifacts/firmware/workspace"
        proposed = await client.post(
            f"{root}/patch/propose",
            json={
                "allowFixture": True,
                "requestedChange": "Change serial baud to 9600.",
                "requestedBy": actor,
            },
        )
        assert proposed.status_code == 200, proposed.text
        proposal = proposed.json()["proposal"]
        proposal_id = proposal["proposalId"]
        if status != "proposed":
            decided = await client.post(
                f"{root}/patch/{'apply' if status == 'applied' else 'discard'}",
                json={
                    "proposalId": proposal_id,
                    "requestedBy": actor,
                    "expectedDraftVersion": draft_version,
                    "baseArtifactVersion": binding["baseArtifactVersion"],
                    "baseProjectStateVersion": binding["baseProjectStateVersion"],
                },
            )
            assert decided.status_code == 200, decided.text
        runtime = api_main._kernel.workspace_runtime
        stored = runtime._kernel.get_firmware_patch_proposal(proposal_id)
        before_runtime = (await client.get(f"{root}/runtime")).json()
        events_url = f"/v1/projects/{project_id}/events"
        before_events = (await client.get(events_url)).json()
        before_files = (await client.get(f"{root}/files")).json()

        # Reading must not use the binding resolver that can create/bind state.
        def deny_binding(**kwargs: Any) -> Any:
            raise AssertionError("GET must not resolve a mutable binding")

        monkeypatch.setattr(runtime, "resolve_binding", deny_binding)
        response = await client.get(f"{root}/patch/{proposal_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["schemaVersion"] == "1.0.0"
        assert body["status"] == status
        assert body["proposal"] == stored
        assert body["binding"] == before_runtime["binding"]
        assert body["baseSnapshotId"] == stored["baseSnapshotId"]
        assert stored["requestedChange"] == "Change serial baud to 9600."
        assert "generatorMetadata" in stored
        assert stored["operations"]
        for operation in stored["operations"]:
            assert {
                "operationType",
                "path",
                "content",
                "expectedBaseHash",
                "contentHash",
            } <= operation.keys()
        assert runtime._kernel.get_firmware_patch_proposal(proposal_id) == stored
        monkeypatch.undo()
        assert (await client.get(f"{root}/runtime")).json() == before_runtime
        assert (await client.get(f"{root}/files")).json() == before_files
        assert (await client.get(events_url)).json() == before_events


@pytest.mark.asyncio
async def test_get_firmware_patch_proposal_scoping() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        project_id, binding, actor, _ = await _create_patch_workspace(client)
        root = f"/v1/projects/{project_id}/artifacts/firmware/workspace/patch"
        proposed = await client.post(
            f"{root}/propose",
            json={
                "allowFixture": True,
                "requestedChange": "Change serial baud to 9600.",
                "requestedBy": actor,
            },
        )
        assert proposed.status_code == 200, proposed.text
        proposal = proposed.json()["proposal"]
        other = await client.post("/v1/projects/initialize", json={"message": GREENHOUSE})
        assert other.status_code == 200, other.text
        other_id = other.json()["project"]["projectId"]
        cross = await client.get(
            f"/v1/projects/{other_id}/artifacts/firmware/workspace/patch/{proposal['proposalId']}"
        )
        assert cross.status_code == 404
        assert cross.json()["error"]["code"] == "FIRMWARE_PATCH_NOT_FOUND"
        missing = await client.get(f"{root}/fwpatch_missing")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "FIRMWARE_PATCH_NOT_FOUND"
        cross_type = await client.get(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/patch/{proposal['proposalId']}"
        )
        assert cross_type.status_code == 422
        assert cross_type.json()["error"]["code"] == "FIRMWARE_PATCH_VALIDATION_FAILED"
        store = api_main._kernel.workspace_runtime._kernel
        store.update_firmware_patch_proposal(
            proposal["proposalId"], {**proposal, "workspaceId": "ws_other"}
        )
        cross_workspace = await client.get(f"{root}/{proposal['proposalId']}")
        assert cross_workspace.status_code == 422
        assert cross_workspace.json()["error"]["code"] == "FIRMWARE_PATCH_VALIDATION_FAILED"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get(f"{root}/{proposal['proposalId']}")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"
