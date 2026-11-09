"""Offline HTTP repair boundary regressions; never live acceptance evidence."""

from typing import Any

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_board.firmware.live_patch_generator import LiveFirmwarePatchGenerator
from nexus_model_gateway import FakeModelGateway, ModelPolicy
from test_actionable_execution_plan import _command
from test_golden_lifecycle_http_api import AUTH, _actor, _put_file, _wait_run
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401
from test_w3_firmware import _approved


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_http_repair_cancellation(
    monkeypatch: pytest.MonkeyPatch,
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
            b"// Offline compile fault\nNEXUS_COMPILE_ERROR\n",
        )
        compiled = await client.post(
            f"{root}/compile", json={"requireReal": False, "requestedBy": user}
        )
        assert compiled.status_code == 200, compiled.text
        run_id = compiled.json()["executionRun"]["executionRunId"]
        assert (await _wait_run(client, pid, run_id))["status"] == "failed"
        route = f"/v1/projects/{pid}/repair"
        started = await client.post(
            route,
            json={
                "action": "start",
                "executionRunId": run_id,
                "target": "firmware",
                "requireReal": True,
                "requestedBy": user,
            },
        )
        assert started.status_code == 200, started.text
        state = started.json()
        cancelled = await client.post(
            route,
            json={
                "action": "cancel",
                "repairId": state["repairId"],
                "revision": state["revision"],
                "requireReal": True,
                "requestedBy": user,
            },
        )
        assert cancelled.status_code == 200, cancelled.text
        state = cancelled.json()
        assert state["status"] == "cancelled"
        assert state["attempts"] == started.json()["attempts"]
        try:
            rejected = await client.post(
                route,
                json={
                    "action": "advance",
                    "repairId": state["repairId"],
                    "revision": state["revision"],
                    "requireReal": True,
                    "requestedBy": user,
                },
            )
            assert rejected.status_code == 200 or 400 <= rejected.status_code < 500, rejected.text
            if rejected.status_code == 200:
                assert rejected.json()["status"] == "cancelled"
                assert rejected.json()["attempts"] == state["attempts"]
            persisted = await client.post(
                route, json={"action": "get", "repairId": state["repairId"]}
            )
            assert persisted.status_code == 200, persisted.text
            assert persisted.json() == state
        finally:
            released = await _command(
                client, pid, user, "workspace.release-edit-lease", runtime["binding"], {}
            )
            assert released["status"] == "completed", released


async def _start_failed_repair(
    client: AsyncClient, user: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    pid, root, runtime, _ = await _approved(client, user)
    await _put_file(
        client,
        pid,
        runtime["binding"],
        runtime["draft"]["draftVersion"],
        user,
        "src/main.cpp",
        b"// Offline compile fault\nNEXUS_COMPILE_ERROR\n",
    )
    compiled = await client.post(
        f"{root}/compile", json={"requireReal": False, "requestedBy": user}
    )
    assert compiled.status_code == 200, compiled.text
    run_id = compiled.json()["executionRun"]["executionRunId"]
    assert (await _wait_run(client, pid, run_id))["status"] == "failed"
    route = f"/v1/projects/{pid}/repair"
    started = await client.post(
        route,
        json={
            "action": "start",
            "executionRunId": run_id,
            "target": "firmware",
            "scope": "build",
            "maxAttempts": 3,
            "requireReal": False,
            "requestedBy": user,
        },
    )
    assert started.status_code == 200, started.text
    return pid, root, started.json()


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_http_repair_attempt_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    gateway = FakeModelGateway()
    proposal_count = 0

    def non_viable_patch(_task: Any, _payload: Any, _schema: Any) -> dict[str, Any]:
        nonlocal proposal_count
        proposal_count += 1
        return {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "src/main.cpp",
                    "content": f"// Failed correction {proposal_count}\nNEXUS_COMPILE_ERROR\n",
                }
            ]
        }

    gateway.set_script("firmware.patch-proposal", non_viable_patch)
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
        run_ids = [state["runId"]]
        diagnostics = []

        async def advance() -> dict[str, Any]:
            response = await client.post(
                route,
                json={
                    "action": "advance",
                    "repairId": state["repairId"],
                    "revision": state["revision"],
                    "requestedBy": user,
                },
            )
            assert response.status_code == 200, response.text
            return dict(response.json())

        for attempt in range(3):
            assert state["status"] == "inspect", state
            state = await advance()
            assert state["status"] == ("exhausted" if attempt == 2 else "review"), state
            diagnostic = state["attempts"][-1]["diagnostics"]
            assert diagnostic["executionRunId"] == run_ids[-1]
            assert diagnostic["snapshotId"]
            assert diagnostic["logExcerpt"]
            diagnostics.append(diagnostic)
            if attempt == 2:
                break
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
            state = await advance()
            assert (state["status"], state["stage"]) == ("running", "compile")
            run_ids.append(state["runId"])
            assert (await _wait_run(client, pid, run_ids[-1]))["status"] == "failed"
            state = await advance()

        assert len(state["attempts"]) == state["maxAttempts"] == 3
        assert proposal_count == 2
        assert len(set(run_ids)) == 3
        assert [a["runIds"] for a in state["attempts"]] == [[rid] for rid in run_ids]
        assert [a["diagnostics"] for a in state["attempts"]] == diagnostics
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == state
        response = await client.post(
            route,
            json={
                "action": "advance",
                "repairId": state["repairId"],
                "revision": state["revision"],
                "requestedBy": user,
            },
        )
        assert response.status_code == 200 or 400 <= response.status_code < 500, response.text
        if response.status_code == 200:
            assert response.json()["status"] == "exhausted"
            assert response.json()["attempts"] == state["attempts"]
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == state


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_http_repair_stale_revision_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, _root, state = await _start_failed_repair(client, user)
        route = f"/v1/projects/{pid}/repair"
        cancelled = await client.post(
            route,
            json={
                "action": "cancel",
                "repairId": state["repairId"],
                "revision": state["revision"],
                "requireReal": True,
                "requestedBy": user,
            },
        )
        assert cancelled.status_code == 200, cancelled.text
        current = cancelled.json()
        assert current["revision"] > state["revision"]
        response = await client.post(
            route,
            json={
                "action": "advance",
                "repairId": state["repairId"],
                "revision": state["revision"],
                "requestedBy": user,
            },
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "REPAIR_CONFLICT"
        # The existing conflict envelope has no revision field; fetch current state.
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == current


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
@pytest.mark.parametrize("criterion_size", [40, 6000], ids=["many-cases", "oversized-case"])
async def test_http_repair_verbose_failing_cases_reach_review(
    monkeypatch: pytest.MonkeyPatch, criterion_size: int
) -> None:
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "1")
    kernel = main._kernel
    gateway = FakeModelGateway()
    requests = []

    def correction(_task: Any, payload: Any, _schema: Any) -> dict[str, Any]:
        requests.append(payload["requestedChange"])
        return {
            "operations": [
                {"operationType": "replace-file", "path": "src/main.cpp", "content": "// fix\n"}
            ]
        }

    gateway.set_script("firmware.patch-proposal", correction)
    monkeypatch.setattr(
        kernel.workspace_runtime,
        "_firmware_patch_generator",
        LiveFirmwarePatchGenerator(
            gateway=gateway, model_policy=ModelPolicy(provider="fake", model="regression")
        ),
    )
    user = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, _root, initial = await _start_failed_repair(client, user)
        # Seed retained simulation evidence at the offline provider boundary.
        run = kernel.kernel_store.get_execution_run(initial["runId"])
        run.update(executionRunId=f"exec_verbose_{criterion_size}", capability="circuit-simulation")
        kernel.kernel_store.create_execution_run(run)
        run_id = run["executionRunId"]
        artifact = kernel.project_store.get_artifact(pid, "test-plan")
        template = artifact["content"]["testCases"][0]
        cases = [
            {
                **template,
                "testId": f"test_verbose_{i}",
                "executionRunId": run_id,
                "criterion": "C" * criterion_size,
                "actualResult": f"Case {i}: " + "verbose failure 雪\n" * 60,
                "assessment": "FAIL",
                "status": "failed",
            }
            for i in range(10)
        ]
        artifact["content"]["testCases"] = cases
        project = kernel.project_store.get_project(pid)
        kernel.project_store.apply_accepted_artifact_revision(
            project_id=pid,
            new_artifact=artifact,
            next_state_version=project["currentStateVersion"] + 1,
            updated_at=artifact["updatedAt"],
        )
        route = f"/v1/projects/{pid}/repair"
        started = await client.post(
            route,
            json={
                "action": "start",
                "executionRunId": run_id,
                "target": "firmware",
                "requireReal": False,
                "requestedBy": user,
            },
        )
        assert started.status_code == 200, started.text
        state = started.json()
        response = await client.post(
            route,
            json={
                "action": "advance",
                "repairId": state["repairId"],
                "revision": state["revision"],
                "requestedBy": user,
            },
        )
        assert response.status_code == 200, response.text
        state = response.json()
        assert state["status"] == "review", state.get("explanation", state)
        assert len(requests) == 1
        assert len(requests[0]) <= 4096
        diagnostics = state["attempts"][0]["diagnostics"]
        assert diagnostics["logExcerptLimited"] is True
        if criterion_size > 4096:
            assert diagnostics["testCasesLimited"] is True
            assert diagnostics["testCases"] == []
        else:
            assert len(diagnostics["testCases"]) == len(cases)
        assert all(len(c["actualResult"]) <= 100 for c in diagnostics["testCases"])
        assert kernel.kernel_store.get_execution_run(run_id) == run
        assert kernel.project_store.get_artifact(pid, "test-plan")["content"]["testCases"] == cases
        persisted = await client.post(route, json={"action": "get", "repairId": state["repairId"]})
        assert persisted.status_code == 200, persisted.text
        assert persisted.json() == state
