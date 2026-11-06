"""Offline HTTP contract coverage for repair rejection; no live evidence claims."""

from typing import Any

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_golden_lifecycle_http_api import (
    AUTH,
    _acquire_lease,
    _actor,
    _binding,
    _put_file,
    _wait_run,
)
from test_repair_boundaries_http_api import _start_failed_repair
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401
from test_w3_firmware import _approved


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
@pytest.mark.parametrize("feedback", ["Please keep the existing sampling rate.", None])
async def test_reject_review(monkeypatch: pytest.MonkeyPatch, feedback: str | None) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    gateway = FakeModelGateway()
    gateway.set_script(
        "firmware.patch-proposal",
        lambda _task, _payload, _schema: {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": "// fix\n"}
            ]
        },
    )
    monkeypatch.setattr(
        main._kernel.workspace_runtime,
        "_firmware_patch_generator",
        LiveFirmwarePatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
        ),
    )
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, state = await _start_failed_repair(client, user)
        route = f"/v1/projects/{pid}/repair"

        async def action(name: str, **extra: Any) -> Any:
            return await client.post(
                route,
                json={
                    "action": name,
                    "repairId": state["repairId"],
                    "revision": state["revision"],
                    "requestedBy": user,
                    "requireReal": True,
                    **extra,
                },
            )

        # Existing advance still diagnoses the failure and pauses for review.
        response = await action("advance")
        assert response.status_code == 200, response.text
        state = response.json()
        assert state["status"] == "review"
        stale = await action("reject", revision=state["revision"] - 1, feedback="Stale")
        assert stale.status_code == 409, stale.text
        assert stale.json()["error"]["code"] == "REPAIR_CONFLICT"
        before = (await client.get(f"{root}/runtime")).json()
        runs = (await client.get(f"/v1/projects/{pid}/executions")).json()
        response = await action(
            "reject", **({"feedback": feedback} if feedback is not None else {})
        )
        assert response.status_code == 200, response.text
        rejected = response.json()
        assert rejected["status"] == "rejected"
        assert rejected["revision"] == state["revision"] + 1
        expected = dict(state["attempts"][-1])
        if feedback is not None:
            expected["feedback"] = feedback
        assert rejected["attempts"] == [expected]
        proposal = await client.get(f"{root}/patch/{state['proposalId']}")
        assert proposal.status_code == 200, proposal.text
        assert proposal.json()["proposal"]["status"] == "discarded"
        assert proposal.json()["proposal"]["decidedBy"] == user
        assert (await client.get(f"{root}/runtime")).json() == before
        assert (await client.get(f"/v1/projects/{pid}/executions")).json() == runs
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.json() == rejected
        state = rejected
        for name in ("advance", "cancel"):
            response = await action(name)
            assert response.status_code == 200, response.text
            assert response.json() == rejected


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
@pytest.mark.parametrize(
    "extra,status,code",
    [
        ({"revision": 0}, 409, "REPAIR_CONFLICT"),
        ({}, 422, "COMMAND_VALIDATION_FAILED"),
        ({"action": "invalid"}, 422, "COMMAND_VALIDATION_FAILED"),
        ({"revision": "1"}, 422, "COMMAND_VALIDATION_FAILED"),
        ({"feedback": 123}, 422, "COMMAND_VALIDATION_FAILED"),
        ({"feedback": None}, 422, "COMMAND_VALIDATION_FAILED"),
    ],
)
async def test_reject_invalid_request(
    monkeypatch: pytest.MonkeyPatch, extra: dict[str, Any], status: int, code: str
) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, _root, state = await _start_failed_repair(client, user)
        assert state["status"] == "inspect"
        route = f"/v1/projects/{pid}/repair"
        body = {
            "action": "reject",
            "repairId": state["repairId"],
            "revision": state["revision"],
            "requestedBy": user,
            "requireReal": True,
        }
        response = await client.post(route, json={**body, **extra})
        assert response.status_code == status, response.text
        assert response.json()["error"]["code"] == code
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.json() == state
        response = await client.post(route, json={**body, "action": "cancel"})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "cancelled"
        assert response.json()["attempts"] == state["attempts"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_reject_analysis_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_ANALYSIS_USE_STUB", "0")
    gateway = FakeModelGateway()
    gateway.set_script(
        "analysis.patch-proposal",
        lambda _task, _payload, _schema: {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "analysis.py",
                    "content": "print('fix')\n",
                }
            ]
        },
    )
    monkeypatch.setattr(
        main._kernel.workspace_runtime,
        "_analysis_patch_generator",
        LiveAnalysisPatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
        ),
    )
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, _root, _runtime, _ = await _approved(client, user)
        root = f"/v1/projects/{pid}/artifacts/analysis/workspace"
        runtime = await _binding(client, pid, "analysis")
        await _acquire_lease(client, pid, runtime["binding"], user)
        await _put_file(
            client,
            pid,
            runtime["binding"],
            runtime["draft"]["draftVersion"],
            user,
            "analysis.py",
            b"raise RuntimeError('Offline analysis fault')\n",
        )
        run = await client.post(f"{root}/run", json={"requestedBy": user, "requireReal": False})
        assert run.status_code == 200, run.text
        run_id = run.json()["executionRun"]["executionRunId"]
        assert (await _wait_run(client, pid, run_id))["status"] == "failed"
        route = f"/v1/projects/{pid}/repair"
        response = await client.post(
            route,
            json={
                "action": "start",
                "executionRunId": run_id,
                "target": "analysis",
                "requireReal": False,
                "requestedBy": user,
            },
        )
        assert response.status_code == 200, response.text
        state = response.json()
        body = {"repairId": state["repairId"], "revision": state["revision"], "requestedBy": user}
        response = await client.post(route, json={**body, "action": "advance"})
        assert response.status_code == 200, response.text
        state = response.json()
        assert state["status"] == "review"
        assert state["target"] == "analysis"
        before = (await client.get(f"{root}/runtime")).json()
        runs = (await client.get(f"/v1/projects/{pid}/executions")).json()
        feedback = "Keep the existing analysis method."
        body["revision"] = state["revision"]
        response = await client.post(route, json={**body, "action": "reject", "feedback": feedback})
        assert response.status_code == 200, response.text
        rejected = response.json()
        assert rejected["status"] == "rejected"
        assert rejected["revision"] == state["revision"] + 1
        assert rejected["attempts"] == [{**state["attempts"][-1], "feedback": feedback}]
        proposal = await client.get(f"{root}/patch/{state['proposalId']}")
        assert proposal.status_code == 200, proposal.text
        assert proposal.json()["proposal"]["status"] == "discarded"
        assert proposal.json()["proposal"]["decidedBy"] == user
        assert (await client.get(f"{root}/runtime")).json() == before
        assert (await client.get(f"/v1/projects/{pid}/executions")).json() == runs
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == rejected
        for action in ("advance", "cancel"):
            response = await client.post(
                route, json={**body, "revision": rejected["revision"], "action": action}
            )
            assert response.status_code == 200, response.text
            assert response.json() == rejected


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_reject_already_applied_proposal_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    gateway = FakeModelGateway()
    gateway.set_script(
        "firmware.patch-proposal",
        lambda _task, _payload, _schema: {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": "// fix\n"}
            ]
        },
    )
    monkeypatch.setattr(
        main._kernel.workspace_runtime,
        "_firmware_patch_generator",
        LiveFirmwarePatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
        ),
    )
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, state = await _start_failed_repair(client, user)
        route = f"/v1/projects/{pid}/repair"
        body = {"repairId": state["repairId"], "revision": state["revision"], "requestedBy": user}
        response = await client.post(route, json={**body, "action": "advance"})
        assert response.status_code == 200, response.text
        state = response.json()
        assert state["status"] == "review"
        runtime = (await client.get(f"{root}/runtime")).json()
        project = (await client.get(f"/v1/projects/{pid}")).json()
        applied = await client.post(
            f"{root}/patch/apply",
            json={
                "proposalId": state["proposalId"],
                "requestedBy": user,
                "expectedDraftVersion": runtime["draft"]["draftVersion"],
                "baseArtifactVersion": runtime["binding"]["baseArtifactVersion"],
                "baseProjectStateVersion": project["project"]["currentStateVersion"],
            },
        )
        assert applied.status_code == 200, applied.text
        before = (await client.get(f"{root}/runtime")).json()
        response = await client.post(
            route,
            json={
                **body,
                "revision": state["revision"],
                "action": "reject",
                "feedback": "Too late",
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "REPAIR_CONFLICT"
        proposal = await client.get(f"{root}/patch/{state['proposalId']}")
        assert proposal.status_code == 200, proposal.text
        assert proposal.json()["proposal"]["status"] == "applied"
        assert (await client.get(f"{root}/runtime")).json() == before
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == state
