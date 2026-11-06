"""Offline HTTP contract coverage for repair rejection; no live evidence claims."""

from typing import Any

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_golden_lifecycle_http_api import AUTH, _actor
from test_repair_boundaries_http_api import _start_failed_repair
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401


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
