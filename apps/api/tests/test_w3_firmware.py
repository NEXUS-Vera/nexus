"""W3 regression evidence: scripted model replies are not live firmware evidence."""

from __future__ import annotations

import json
from pathlib import Path

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_actionable_execution_plan import _command, _propose, _setup
from test_golden_lifecycle_http_api import AUTH, _actor, _put_file


async def _approved(client, user):
    pid, config = await _setup(client, user)
    proposal = (await _propose(client, pid, user, config)).json()
    accepted = await _command(
        client,
        pid,
        user,
        "artifact.accept-revision",
        proposal["workspace"],
        {"proposalId": proposal["commandResult"]["proposalId"]},
    )
    assert accepted["status"] == "completed", accepted
    root = f"/v1/projects/{pid}/artifacts/firmware/workspace"
    runtime = (await client.get(f"{root}/runtime")).json()
    await _command(client, pid, user, "workspace.acquire-edit-lease", runtime["binding"], {})
    return pid, root, runtime, proposal["content"]


@pytest.mark.asyncio
async def test_scripted_approved_plan_review_denied_apply_and_stale_base(monkeypatch):
    user = _actor()
    gateway = FakeModelGateway()
    payloads = []
    golden = (
        Path(__file__).parents[3]
        / "packages/board/tests/golden/esp32_imu_vibration_monitor/main.cpp"
    ).read_text()

    def script(_task, payload, _schema):
        payloads.append(payload)
        return {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": golden}
            ]
        }

    gateway.set_script("firmware.patch-proposal", script)
    monkeypatch.setattr(
        main._kernel.workspace_runtime,
        "_firmware_patch_generator",
        LiveFirmwarePatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="fake-model")
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, runtime, plan = await _approved(client, user)
        binding = runtime["binding"]

        async def files():
            return (await client.get(f"{root}/files")).json()["files"]

        before = await files()
        response = await client.post(
            f"{root}/patch/propose",
            json={
                "requestedBy": user,
                "requestedChange": "Implement the approved vibration monitor firmware.",
            },
        )
        assert response.status_code == 200, response.text
        proposal = response.json()["proposal"]
        assert proposal["status"] == "proposed"
        assert proposal["generatorMetadata"]["mode"] == "regression"
        assert proposal["operations"][0]["content"] == golden
        assert await files() == before
        payload = payloads[0]
        assert payload["artifacts"]["execution-plan"] == plan
        assert "MPU6050" in json.dumps(payload["artifacts"]["component-plan"])
        state = (await client.get(f"/v1/projects/{pid}")).json()
        approved = next(a for a in state["artifacts"] if a["artifactType"] == "execution-plan")
        assert payload["inputArtifactReferences"][0:1] == [
            {
                "artifactType": "execution-plan",
                "artifactVersion": approved["artifactVersion"],
                "artifactId": approved["artifactId"],
            }
        ]
        assert len(payload["fileContents"]) <= 32
        assert all(len(v.encode()) <= 32768 for v in payload["fileContents"].values())
        assert "nexus/approved-plan.json" not in payload["fileContents"]
        assert len(json.dumps(payload["artifacts"]).encode()) < 131072
        current = (await client.get(f"{root}/runtime")).json()
        apply_body = {
            "proposalId": proposal["proposalId"],
            "expectedDraftVersion": current["draft"]["draftVersion"],
            "baseArtifactVersion": binding["baseArtifactVersion"],
            "baseProjectStateVersion": state["project"]["currentStateVersion"],
            "requestedBy": _actor(),
        }
        denied = await client.post(f"{root}/patch/apply", json=apply_body)
        assert denied.status_code == 422, denied.text
        assert denied.json()["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"
        assert await files() == before
        discarded = await client.post(
            f"{root}/patch/discard",
            json={"proposalId": proposal["proposalId"], "requestedBy": user},
        )
        assert discarded.status_code == 200, discarded.text
        assert await files() == before
        response = await client.post(
            f"{root}/patch/propose",
            json={"requestedBy": user, "requestedChange": "Implement the approved firmware."},
        )
        proposal = response.json()["proposal"]
        await _put_file(
            client,
            pid,
            binding,
            current["draft"]["draftVersion"],
            user,
            "src/main.cpp",
            b"// concurrent user edit\n",
        )
        edited = await files()
        current = (await client.get(f"{root}/runtime")).json()
        apply_body.update(
            proposalId=proposal["proposalId"],
            expectedDraftVersion=current["draft"]["draftVersion"],
            requestedBy=user,
        )
        stale = await client.post(f"{root}/patch/apply", json=apply_body)
        assert stale.status_code == 409, stale.text
        assert stale.json()["error"]["code"] == "FIRMWARE_PATCH_STALE"
        assert await files() == edited
        # A fresh, reviewed model proposal applies through the ordinary guarded path.
        response = await client.post(
            f"{root}/patch/propose",
            json={"requestedBy": user, "requestedChange": "Implement the approved firmware."},
        )
        apply_body["proposalId"] = response.json()["proposal"]["proposalId"]
        applied = await client.post(f"{root}/patch/apply", json=apply_body)
        assert applied.status_code == 200, applied.text
        read = await client.get(f"{root}/file", params={"path": "src/main.cpp"})
        assert read.json()["content"] == golden


@pytest.mark.asyncio
@pytest.mark.parametrize("stub,require_real", [(False, False), (True, True)])
async def test_missing_toolchain_and_fixture_cannot_satisfy_real_build(
    monkeypatch, stub, require_real
):
    monkeypatch.setattr("nexus_board.firmware.toolchain.shutil.which", lambda _: None)
    if stub:
        monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    else:
        monkeypatch.delenv("NEXUS_FIRMWARE_USE_STUB", raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, _runtime, _plan = await _approved(client, _actor())
        runs_before = (await client.get(f"/v1/projects/{pid}/executions")).json()
        outputs_before = (await client.get(f"/v1/projects/{pid}/outputs")).json()
        response = await client.post(f"{root}/compile", json={"requireReal": require_real})
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "FIRMWARE_TOOLCHAIN_UNAVAILABLE"
        assert (await client.get(f"/v1/projects/{pid}/executions")).json() == runs_before
        assert (await client.get(f"/v1/projects/{pid}/outputs")).json() == outputs_before


@pytest.mark.asyncio
async def test_missing_model_is_visible_without_canned_proposal(monkeypatch):
    monkeypatch.setattr(main._kernel.workspace_runtime, "_firmware_patch_generator", None)
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        _pid, root, _runtime, _plan = await _approved(client, _actor())
        before = (await client.get(f"{root}/files")).json()
        response = await client.post(
            f"{root}/patch/propose", json={"requestedChange": "Implement approved firmware"}
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "MODEL_PROVIDER_UNAVAILABLE"
        assert (await client.get(f"{root}/files")).json() == before
