"""Repair scope HTTP regressions; fixture builds are not live product evidence."""

import asyncio
import copy
from collections.abc import AsyncIterator
from typing import Any, NoReturn

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_golden_lifecycle_http_api import AUTH, _actor, _put_file, _wait_run
from test_w3_firmware import _approved


@pytest.fixture(autouse=True)
async def keep_event_loop_active() -> AsyncIterator[None]:
    # Restricted runners may not wake the loop for worker-thread completion.
    async def tick() -> None:
        while True:
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(tick())
    try:
        yield
    finally:
        ticker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await ticker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope,target,expected_status",
    [
        ("build", "firmware", 200),
        (None, "firmware", 200),
        ("build", "analysis", 422),
        ("invalid", "firmware", 422),
    ],
)
async def test_repair_scope_over_http(
    monkeypatch: pytest.MonkeyPatch, scope: str | None, target: str, expected_status: int
) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, root, runtime, _ = await _approved(client, user)
        await _put_file(
            client,
            pid,
            runtime["binding"],
            runtime["draft"]["draftVersion"],
            user,
            "src/main.cpp",
            b"// User-injected compile fault (offline regression)\nNEXUS_COMPILE_ERROR\n",
        )
        compiled = await client.post(
            f"{root}/compile", json={"requireReal": False, "requestedBy": user}
        )
        assert compiled.status_code == 200, compiled.text
        failed_id = compiled.json()["executionRun"]["executionRunId"]
        assert (await _wait_run(client, pid, failed_id))["status"] == "failed"
        route = f"/v1/projects/{pid}/repair"
        body: dict[str, Any] = {
            "action": "start",
            "executionRunId": failed_id,
            "target": target,
            "requireReal": False,
            "requestedBy": user,
        }
        if scope is not None:
            body["scope"] = scope
        response = await client.post(route, json=body)
        assert response.status_code == expected_status, response.text
        if expected_status == 422:
            assert response.json()["error"]["code"] == "COMMAND_VALIDATION_FAILED"
            return
        state = response.json()
        assert state["scope"] == (scope or "full")
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == state
        if scope != "build":
            return

        # Script only the model reply; diagnosis, review/apply and jobs use normal routes.
        gateway = FakeModelGateway()
        gateway.set_script(
            "firmware.patch-proposal",
            lambda _task, _payload, _schema: {
                "operations": [
                    {
                        "operationType": "replace-file",
                        "path": "src/main.cpp",
                        "content": "#include <Arduino.h>\nvoid setup() {}\nvoid loop() {}\n",
                    }
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
        before_plan = copy.deepcopy(main._kernel.project_store.get_artifact(pid, "test-plan"))
        before_runs = (await client.get(f"/v1/projects/{pid}/executions")).json()

        def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
            pytest.fail("Build-only repair must not run analysis or promote evidence")

        monkeypatch.setattr(main._kernel.workspace_runtime, "run_analysis", forbidden)
        monkeypatch.setattr(main._kernel.verification, "promote_execution_evidence", forbidden)
        execute = main._kernel.executions.execute

        def compile_only(**kwargs: Any) -> Any:
            assert kwargs["artifact_type"] == "firmware"
            return execute(**kwargs)

        monkeypatch.setattr(main._kernel.executions, "execute", compile_only)

        async def advance(progress: dict[str, Any]) -> dict[str, Any]:
            result = await client.post(
                route,
                json={
                    "action": "advance",
                    "repairId": progress["repairId"],
                    "revision": progress["revision"],
                    "requestedBy": user,
                },
            )
            assert result.status_code == 200, result.text
            return dict(result.json())

        state = await advance(state)
        assert state["status"] == "review"
        current = (await client.get(f"{root}/runtime")).json()
        project = (await client.get(f"/v1/projects/{pid}")).json()
        applied = await client.post(
            f"{root}/patch/apply",
            json={
                "proposalId": state["proposalId"],
                "requestedBy": user,
                "expectedDraftVersion": current["draft"]["draftVersion"],
                "baseArtifactVersion": current["binding"]["baseArtifactVersion"],
                "baseProjectStateVersion": project["project"]["currentStateVersion"],
            },
        )
        assert applied.status_code == 200, applied.text
        state = await advance(state)
        assert state["status"] == "running" and state["stage"] == "compile"
        assert (await _wait_run(client, pid, state["runId"]))["status"] == "completed"
        state = await advance(state)
        assert state["status"] == "completed" and state["stage"] == "compile"
        assert state["scope"] == "build"
        assert "Build-only repair" in state["explanation"]
        assert len(state["attempts"]) == 2
        assert state["attempts"][1]["runIds"] == [state["runId"]]
        assert main._kernel.project_store.get_artifact(pid, "test-plan") == before_plan
        after_runs = (await client.get(f"/v1/projects/{pid}/executions")).json()
        assert len(after_runs["items"]) == len(before_runs["items"]) + 1
