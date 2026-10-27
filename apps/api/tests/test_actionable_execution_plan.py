"""W2/P1 HTTP regression evidence only: fixture intent and scripted user review.

No live model, real toolchain, or agent-authored firmware acceptance is claimed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from test_golden_lifecycle_http_api import AUTH, GOLDEN_PROMPT, _actor


def _id() -> str:
    return f"cmd_{secrets.token_hex(16)}"


async def _command(
    client: AsyncClient,
    pid: str,
    actor: dict[str, Any],
    kind: str,
    workspace: dict[str, Any],
    data: dict[str, Any],
    expected_status: int = 200,
) -> dict[str, Any]:
    state = (await client.get(f"/v1/projects/{pid}")).json()
    response = await client.post(
        f"/v1/projects/{pid}/artifact-commands",
        json={
            "schemaVersion": "1.0.0",
            "commandId": _id(),
            "commandType": kind,
            "projectId": pid,
            "workspaceId": workspace["workspaceId"],
            "artifactId": workspace["artifactId"],
            "baseArtifactVersion": workspace["baseArtifactVersion"],
            "baseProjectStateVersion": state["project"]["currentStateVersion"],
            "requestedBy": actor,
            "requestedAt": "2026-10-22T00:00:00Z",
            "input": data,
        },
    )
    assert response.status_code == expected_status, response.text
    return response.json()


async def _revise_candidates(
    client: AsyncClient,
    pid: str,
    actor: dict[str, Any],
    sda_pin: int = 21,
    overrides: dict[str, Any] | None = None,
) -> None:
    """Explicit user component edit over normal API; never pretend fixture parts are real."""
    state = (await client.get(f"/v1/projects/{pid}")).json()
    component = next(a for a in state["artifacts"] if a["artifactType"] == "component-plan")
    content = copy.deepcopy(component["content"])
    for candidate in content["candidates"]:
        if candidate["candidateCategory"] == "compute":
            candidate.update(partNumber="ESP32-DEVKIT-V1", displayName="ESP32 DevKit V1")
            for spec in candidate["specifications"]:
                if spec["specKey"] == "gpio-sda":
                    spec["value"] = sda_pin
        else:
            candidate.update(partNumber="MPU6050", displayName="MPU6050")
    if overrides:
        content["candidates"][0].update(overrides)
    result = await _command(
        client,
        pid,
        actor,
        "workspace.create",
        {
            "workspaceId": "unused",
            "artifactId": component["artifactId"],
            "baseArtifactVersion": component["artifactVersion"],
        },
        {"artifactType": "component-plan", "initialContent": content},
    )
    workspace = (await client.get(f"/v1/projects/{pid}/artifacts/component-plan/workspace")).json()[
        "workspace"
    ]
    assert result["status"] == "completed"
    await _command(client, pid, actor, "workspace.acquire-edit-lease", workspace, {})
    draft = (await client.get(f"/v1/projects/{pid}/artifacts/component-plan/workspace")).json()[
        "draft"
    ]
    await _command(
        client,
        pid,
        actor,
        "workspace.update-draft",
        workspace,
        {"content": content, "expectedDraftVersion": draft["draftVersion"]},
    )
    snap = await _command(
        client, pid, actor, "workspace.create-snapshot", workspace, {"reason": "manual"}
    )
    proposed = await _command(
        client,
        pid,
        actor,
        "artifact.propose-revision",
        workspace,
        {"snapshotId": snap["snapshotId"], "consequenceLevel": "high"},
    )
    accepted = await _command(
        client,
        pid,
        actor,
        "artifact.accept-revision",
        workspace,
        {"proposalId": proposed["proposalId"]},
    )
    assert accepted["status"] == "completed", accepted


async def _setup(
    client: AsyncClient, actor: dict[str, Any], *, fixture: bool = False
) -> tuple[str, dict[str, Any]]:
    created = await client.post("/v1/projects/initialize", json={"message": GOLDEN_PROMPT})
    assert created.status_code == 200, created.text
    pid = created.json()["project"]["projectId"]
    if not fixture:
        await _revise_candidates(client, pid, actor)
    state = (await client.get(f"/v1/projects/{pid}")).json()
    cp = next(a["content"] for a in state["artifacts"] if a["artifactType"] == "component-plan")
    electrical = next(
        a["content"] for a in state["artifacts"] if a["artifactType"] == "electrical-architecture"
    )
    i2c = next(c for c in electrical["connections"] if c["interfaceType"] == "i2c")
    return pid, {
        "buildProfileId": "platformio-arduino-esp32-v1",
        "analysisProfileId": "python-analysis-v1",
        "components": [
            {"componentRoleId": c["componentRoleId"], "candidateId": c["candidateId"]}
            for c in cp["candidates"]
        ],
        "i2c": {"connectionId": i2c["connectionId"], "sdaPin": 21, "sclPin": 22},
    }


async def _propose(
    client: AsyncClient, pid: str, actor: dict[str, Any], config: dict[str, Any], **extra: Any
) -> Any:
    state = (await client.get(f"/v1/projects/{pid}")).json()
    return await client.post(
        f"/v1/projects/{pid}/execution-plan/propose",
        json={
            "requestedBy": actor,
            "baseProjectStateVersion": state["project"]["currentStateVersion"],
            "basePlanVersion": 0,
            "configuration": config,
            **extra,
        },
    )


@pytest.mark.asyncio
async def test_plan_reject_revise_approve_materializes_consistent_workspaces() -> None:
    from nexus_api.main import app

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        before = (await client.get(f"/v1/projects/{pid}")).json()
        proposed = await _propose(client, pid, actor, config)
        assert proposed.status_code == 200, proposed.text
        proposal = proposed.json()
        result = proposal["commandResult"]
        assert result["status"] in {"completed", "completed-with-warnings"}, result
        rejected = await _command(
            client,
            pid,
            actor,
            "artifact.reject-revision",
            proposal["workspace"],
            {"proposalId": result["proposalId"], "reason": "Review the sequence"},
        )
        assert rejected["status"] == "completed", rejected
        after = (await client.get(f"/v1/projects/{pid}")).json()
        assert after["project"] == before["project"]
        assert after["artifacts"] == before["artifacts"]
        # Reading runtime creates an empty workspace; rejection must leave it empty.
        for kind in ("firmware", "analysis"):
            binding = (
                await client.get(f"/v1/projects/{pid}/artifacts/{kind}/workspace/runtime")
            ).json()
            assert binding["draft"]["draftVersion"] == 1
        # A consequential revision: explicitly change the component pin choice,
        # then review a fresh plan against that accepted component revision.
        await _revise_candidates(client, pid, actor, sda_pin=25)
        config["i2c"]["sdaPin"] = 25
        revised = await _propose(client, pid, actor, config)
        assert revised.status_code == 200, revised.text
        reviewed = revised.json()
        revised_plan = reviewed["content"]["plan"]
        accepted = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            reviewed["workspace"],
            {"proposalId": reviewed["commandResult"]["proposalId"]},
        )
        assert accepted["status"] == "completed", accepted
        state = (await client.get(f"/v1/projects/{pid}")).json()
        plan_art = next(a for a in state["artifacts"] if a["artifactType"] == "execution-plan")
        assert plan_art["approvalStatus"] == "user-approved"
        assert plan_art["content"] == reviewed["content"]
        assert (
            plan_art["content"]["plan"]["verificationObjectives"]
            == revised_plan["verificationObjectives"]
        )
        for kind in ("firmware", "analysis"):
            binding = (
                await client.get(f"/v1/projects/{pid}/artifacts/{kind}/workspace/runtime")
            ).json()
            assert "binding" in binding, binding
            response = await client.get(
                f"/v1/projects/{pid}/workspaces/{binding['binding']['workspaceId']}/file",
                params={"path": "nexus/approved-plan.json"},
            )
            assert response.status_code == 200, response.text
            assert json.loads(response.json()["content"]) == plan_art["content"]
        firmware = (
            await client.get(f"/v1/projects/{pid}/artifacts/firmware/workspace/runtime")
        ).json()

        async def read(path: str) -> str:
            response = await client.get(
                f"/v1/projects/{pid}/workspaces/{firmware['binding']['workspaceId']}/file",
                params={"path": path},
            )
            assert response.status_code == 200, response.text
            return response.json()["content"]

        assert "board = esp32dev" in await read("platformio.ini")
        assert "NEXUS_SDA_PIN = 25" in await read("include/nexus_plan.h")
        assert "NEXUS_SCL_PIN = 22" in await read("include/nexus_plan.h")
        assert "Wire.begin(NEXUS_SDA_PIN, NEXUS_SCL_PIN)" in await read("src/main.cpp")
        retry = await client.post(
            f"/v1/projects/{pid}/execution-plan/materialize",
            json={
                "requestedBy": actor,
                "planArtifactId": plan_art["artifactId"],
                "baseProjectStateVersion": state["project"]["currentStateVersion"],
            },
        )
        assert retry.status_code == 200, retry.text
        stale = await _propose(client, pid, actor, config)
        assert stale.status_code == 409


@pytest.mark.asyncio
async def test_stale_plan_and_base_versions_rejected() -> None:
    from nexus_api.main import app

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        proposed = await _propose(client, pid, actor, config)
        assert proposed.status_code == 200, proposed.text
        old = proposed.json()
        await _revise_candidates(client, pid, actor)
        stale = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            old["workspace"],
            {"proposalId": old["commandResult"]["proposalId"]},
            expected_status=409,
        )
        assert stale["error"]["code"] == "PROJECT_STATE_CONFLICT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "duplicate-pin",
        "dangling-candidate",
        "unsupported-build",
        "pins-disagree",
        "wrong-objective",
        "unsupported-version",
        "stale-basis",
    ],
)
async def test_invalid_plan_is_rejected_before_workspace_changes(change: str) -> None:
    from nexus_api.main import app

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        valid = await _propose(client, pid, actor, config)
        assert valid.status_code == 200, valid.text
        plan = valid.json()["content"]["plan"]
        before = (await client.get(f"/v1/projects/{pid}")).json()
        if change == "duplicate-pin":
            config["i2c"]["sclPin"] = 21
        elif change == "dangling-candidate":
            config["components"][0]["candidateId"] = "missing"
        elif change == "unsupported-build":
            config["buildProfileId"] = "another-board"
        elif change == "pins-disagree":
            config["i2c"]["sdaPin"] = 25
        elif change == "wrong-objective":
            plan["verificationObjectives"][0]["acceptanceCriteria"] = ["invented criterion"]
        elif change == "unsupported-version":
            plan["schemaVersion"] = "2.0.0"
        else:
            plan["basisProjectStateVersion"] -= 1
        response = await _propose(client, pid, actor, config, plan=plan)
        assert response.status_code == (409 if change == "stale-basis" else 422), response.text
        after = (await client.get(f"/v1/projects/{pid}")).json()
        assert before["project"] == after["project"]
        assert before["artifacts"] == after["artifacts"]


@pytest.mark.asyncio
async def test_approved_plan_files_survive_sqlite_restart(monkeypatch, tmp_path) -> None:
    import nexus_api.main as main
    from nexus_board import build_project_kernel
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        ExecutionPlanWorkflow,
    )
    from nexus_persistence import LocalFileStore, build_stores

    def restart() -> None:
        store, kernel_store = build_stores(
            backend="sqlite", database_url=f"sqlite:///{tmp_path / 'actionable.db'}"
        )
        kernel = build_project_kernel(
            kernel_store, project_store=store, file_store=LocalFileStore(str(tmp_path / "files"))
        )
        workflow = ExecutionPlanWorkflow(kernel)
        kernel.commands.revision_validator = workflow.validate_revision
        kernel.commands.revision_materializer = workflow.materialize
        for name, value in {
            "_store": store,
            "_kernel_store": kernel_store,
            "_kernel": kernel,
            "_plan_workflow": workflow,
        }.items():
            monkeypatch.setattr(main, name, value)
        monkeypatch.setattr(main, "_init_service", main._build_init_service())

    actor = _actor()
    restart()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor, fixture=True)
        proposed = (await _propose(client, pid, actor, config)).json()
        accepted = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            proposed["workspace"],
            {"proposalId": proposed["commandResult"]["proposalId"]},
        )
        assert accepted["status"] == "completed", accepted
        before = (await client.get(f"/v1/projects/{pid}")).json()
        files = {}
        for kind in ("firmware", "analysis"):
            binding = (
                await client.get(f"/v1/projects/{pid}/artifacts/{kind}/workspace/runtime")
            ).json()["binding"]
            files[kind] = (
                await client.get(f"/v1/projects/{pid}/workspaces/{binding['workspaceId']}/files")
            ).json()
    restart()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        after = (await client.get(f"/v1/projects/{pid}")).json()
        assert after == before
        for kind, expected in files.items():
            binding = (
                await client.get(f"/v1/projects/{pid}/artifacts/{kind}/workspace/runtime")
            ).json()["binding"]
            actual = (
                await client.get(f"/v1/projects/{pid}/workspaces/{binding['workspaceId']}/files")
            ).json()
            assert actual == expected
            content = await client.get(
                f"/v1/projects/{pid}/workspaces/{binding['workspaceId']}/file",
                params={"path": "nexus/approved-plan.json"},
            )
            assert content.status_code == 200
            assert json.loads(content.json()["content"]) == proposed["content"]


@pytest.mark.asyncio
async def test_opt_in_real_build_of_approved_scaffold(monkeypatch) -> None:
    import os

    if os.environ.get("NEXUS_W2_REAL_BUILD") != "1":
        pytest.skip("opt-in actual PlatformIO build; fixture intent remains regression evidence")
    from nexus_api.main import _file_store, app
    from test_golden_lifecycle_http_api import _wait_run

    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        proposed = (await _propose(client, pid, actor, config)).json()
        accepted = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            proposed["workspace"],
            {"proposalId": proposed["commandResult"]["proposalId"]},
        )
        assert accepted["status"] == "completed", accepted
        binding = (
            await client.get(f"/v1/projects/{pid}/artifacts/firmware/workspace/runtime")
        ).json()["binding"]
        await _command(client, pid, actor, "workspace.acquire-edit-lease", binding, {})
        compiled = await client.post(
            f"/v1/projects/{pid}/artifacts/firmware/workspace/compile", json={"requestedBy": actor}
        )
        assert compiled.status_code == 200, compiled.text
        assert compiled.json()["toolchainProfile"]["executionMode"] == "platformio"
        run = await _wait_run(client, pid, compiled.json()["executionRun"]["executionRunId"])
        logs = (
            await client.get(f"/v1/projects/{pid}/executions/{run['executionRunId']}/logs")
        ).json()
        assert run["status"] == "completed", json.dumps({"run": run, "logs": logs})
        outputs = (await client.get(f"/v1/projects/{pid}/outputs")).json()["items"]
        built = [o for o in outputs if o["executionRunId"] == run["executionRunId"]]
        assert {o["name"] for o in built} >= {
            ".pio/build/nexus/firmware.elf",
            ".pio/build/nexus/firmware.bin",
        }
        for output in built:
            assert output["content"]["kind"] == "storage-reference"
            assert output["content"]["storageKind"] == "file-store"
            data = _file_store.get(output["content"]["uri"])
            assert len(data) > 0, output["name"]
            assert output["contentDigest"] == "sha256:" + hashlib.sha256(data).hexdigest()


@pytest.mark.asyncio
async def test_existing_files_block_approval_without_overwrite() -> None:
    from nexus_api.main import app
    from test_golden_lifecycle_http_api import _put_file

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        proposed = (await _propose(client, pid, actor, config)).json()
        binding = (
            await client.get(f"/v1/projects/{pid}/artifacts/firmware/workspace/runtime")
        ).json()
        await _command(client, pid, actor, "workspace.acquire-edit-lease", binding["binding"], {})
        await _put_file(
            client,
            pid,
            binding["binding"],
            binding["draft"]["draftVersion"],
            actor,
            "src/main.cpp",
            b"// user code must survive\n",
        )
        before = (await client.get(f"/v1/projects/{pid}")).json()
        result = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            proposed["workspace"],
            {"proposalId": proposed["commandResult"]["proposalId"]},
        )
        assert result["status"] == "failed", result
        assert result["error"]["code"] == "COMMAND_VALIDATION_FAILED"
        after = (await client.get(f"/v1/projects/{pid}")).json()
        assert after == before
        read = await client.get(
            f"/v1/projects/{pid}/workspaces/{binding['binding']['workspaceId']}/file",
            params={"path": "src/main.cpp"},
        )
        assert read.json()["content"] == "// user code must survive\n"


@pytest.mark.asyncio
async def test_interrupted_materialization_retains_approval_and_can_retry(monkeypatch) -> None:
    import nexus_api.main as main
    from nexus_board.errors import BoardError

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor)
        proposed = (await _propose(client, pid, actor, config)).json()
        original = main._kernel.filesystem.write_file
        calls = 0

        def interrupted(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise BoardError("Controlled storage interruption")
            return original(**kwargs)

        monkeypatch.setattr(main._kernel.filesystem, "write_file", interrupted)
        result = await _command(
            client,
            pid,
            actor,
            "artifact.accept-revision",
            proposed["workspace"],
            {"proposalId": proposed["commandResult"]["proposalId"]},
        )
        assert result["status"] == "failed", result
        state = (await client.get(f"/v1/projects/{pid}")).json()
        approved = next(a for a in state["artifacts"] if a["artifactType"] == "execution-plan")
        assert approved["approvalStatus"] == "user-approved"
        monkeypatch.setattr(main._kernel.filesystem, "write_file", original)
        retry = await client.post(
            f"/v1/projects/{pid}/execution-plan/materialize",
            json={
                "requestedBy": actor,
                "planArtifactId": approved["artifactId"],
                "baseProjectStateVersion": state["project"]["currentStateVersion"],
            },
        )
        assert retry.status_code == 200, retry.text
        for kind in ("firmware", "analysis"):
            binding = (
                await client.get(f"/v1/projects/{pid}/artifacts/{kind}/workspace/runtime")
            ).json()["binding"]
            context = await client.get(
                f"/v1/projects/{pid}/workspaces/{binding['workspaceId']}/file",
                params={"path": "nexus/approved-plan.json"},
            )
            assert json.loads(context.json()["content"]) == approved["content"]


@pytest.mark.asyncio
async def test_agent_proposal_requires_user_approval() -> None:
    from nexus_api.main import app

    user = _actor()
    agent = {**_actor(), "actorType": "agent", "displayName": "Embedded agent"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, user)
        proposed = await _propose(client, pid, agent, config)
        assert proposed.status_code == 200, proposed.text
        proposal = proposed.json()
        assert proposal["commandResult"]["status"] == "completed-with-warnings"
        denied = await _command(
            client,
            pid,
            agent,
            "artifact.accept-revision",
            proposal["workspace"],
            {"proposalId": proposal["commandResult"]["proposalId"]},
            expected_status=403,
        )
        # Non-user acceptance is a governance denial, matching the existing M4/M9 contract.
        assert denied["error"]["code"] == "GOVERNANCE_REJECTED"
        state = (await client.get(f"/v1/projects/{pid}")).json()
        assert not any(a["artifactType"] == "execution-plan" for a in state["artifacts"])


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", ["valid", "unresolved", "ambiguous"])
async def test_default_configuration_with_eight_architecture_roles(binding: str) -> None:
    from nexus_api.main import _store, app
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        derive_default_configuration,
    )

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, expected = await _setup(client, actor)
        state = _store.get_current_state(pid)
        component = next(a for a in state["artifacts"] if a["artifactType"] == "component-plan")
        cp = component["content"]
        for index in range(6):
            role = copy.deepcopy(cp["componentRoles"][0])
            role["componentRoleId"] = f"extra-role-{index}"
            cp["componentRoles"].insert(0, role)
            candidate = copy.deepcopy(cp["candidates"][0])
            candidate.update(
                componentRoleId=role["componentRoleId"],
                candidateId=f"extra-candidate-{index}",
                partNumber=f"OTHER-{index}",
            )
            cp["candidates"].insert(0, candidate)
        _store.save_initialization_package(state)
        original = copy.deepcopy(state)
        derived = derive_default_configuration(state)
        expected["components"].sort(key=lambda c: c["candidateId"])
        derived["components"].sort(key=lambda c: c["candidateId"])
        assert derived == expected
        assert state == original
        electrical = next(
            a["content"]
            for a in state["artifacts"]
            if a["artifactType"] == "electrical-architecture"
        )
        bus = next(
            c
            for c in electrical["connections"]
            if c["connectionId"] == expected["i2c"]["connectionId"]
        )
        if binding == "unresolved":
            bus["status"] = "unresolved"
        elif binding == "ambiguous":
            second_bus = copy.deepcopy(bus)
            second_bus["connectionId"] = "second-i2c-binding"
            for endpoint in ("fromNodeId", "toNodeId"):
                node = copy.deepcopy(
                    next(n for n in electrical["nodes"] if n["nodeId"] == bus[endpoint])
                )
                candidate = copy.deepcopy(
                    next(
                        c
                        for c in cp["candidates"]
                        if c["candidateId"] == node["componentCandidateId"]
                    )
                )
                candidate["candidateId"] += "-second"
                cp["candidates"].append(candidate)
                node["nodeId"] += "-second"
                node["componentCandidateId"] = candidate["candidateId"]
                electrical["nodes"].append(node)
                second_bus[endpoint] = node["nodeId"]
            electrical["connections"].append(second_bus)
        _store.save_initialization_package(state)
        response = await client.post(
            f"/v1/projects/{pid}/execution-plan/propose",
            json={
                "requestedBy": actor,
                "baseProjectStateVersion": state["project"]["currentStateVersion"],
                "basePlanVersion": 0,
            },
        )
        if binding != "valid":
            assert response.status_code == 422, response.text
            error = response.json()["error"]
            assert error["code"] == "COMMAND_VALIDATION_FAILED"
            assert "Default configuration requires one usable" in error["message"]
            assert _store.get_current_state(pid) == state
            return
        assert response.status_code == 200, response.text
        content = response.json()["content"]
        content["configuration"]["components"].sort(key=lambda c: c["candidateId"])
        assert content["configuration"] == expected
        assert len(content["plan"]["components"]) == 8
        # Proposing is review only; the project has not accepted or materialized it.
        assert _store.get_current_state(pid)["project"] == state["project"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_key",
    ["partNumber", "specifications", "candidateId", "candidateState", "componentRoleId"],
)
@pytest.mark.parametrize("category", ["compute", "sensing"])
async def test_default_configuration_skips_malformed_candidates(
    missing_key: str, category: str
) -> None:
    from nexus_api.main import _store, app
    from nexus_board.errors import CommandValidationError
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        derive_default_configuration,
    )

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, expected = await _setup(client, actor)
        state = _store.get_current_state(pid)
        cp = next(a["content"] for a in state["artifacts"] if a["artifactType"] == "component-plan")
        candidate = next(
            c
            for c in cp["candidates"]
            if (c["candidateCategory"] == "compute") == (category == "compute")
        )
        malformed = copy.deepcopy(candidate)
        malformed["candidateId"] = "malformed-unbound-candidate"
        del malformed[missing_key]
        cp["candidates"].insert(0, malformed)
        derived = derive_default_configuration(state)
        assert sorted(derived["components"], key=lambda c: c["candidateId"]) == sorted(
            expected["components"], key=lambda c: c["candidateId"]
        )
        del candidate[missing_key]
        with pytest.raises(
            CommandValidationError, match="Default configuration requires one usable"
        ):
            derive_default_configuration(state)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("collection", "key"),
    [
        ("candidates", None),
        ("nodes", None),
        ("nodes", "nodeId"),
        ("nodes", "componentCandidateId"),
        ("connections", None),
        *[
            ("connections", k)
            for k in ("interfaceType", "status", "fromNodeId", "toNodeId", "connectionId")
        ],
        ("specifications", None),
        ("specifications", "specKey"),
        ("specifications", "value"),
    ],
)
async def test_default_configuration_skips_malformed_entries(
    collection: str, key: str | None
) -> None:
    from nexus_api.main import _store, app
    from nexus_board.errors import CommandValidationError
    from nexus_embedded_systems.workflows.project_modification.execution_plan import (
        derive_default_configuration,
    )

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, expected = await _setup(client, actor)
        state = _store.get_current_state(pid)
        cp = next(a["content"] for a in state["artifacts"] if a["artifactType"] == "component-plan")
        electrical = next(
            a["content"]
            for a in state["artifacts"]
            if a["artifactType"] == "electrical-architecture"
        )
        compute = next(c for c in cp["candidates"] if c["candidateCategory"] == "compute")
        if collection == "candidates":
            entries, valid = cp["candidates"], compute
        elif collection == "specifications":
            entries = compute["specifications"]
            valid = next(s for s in entries if s["specKey"] == "gpio-sda")
        else:
            entries = electrical[collection]
            bus = next(c for c in electrical["connections"] if c["interfaceType"] == "i2c")
            valid = (
                bus
                if collection == "connections"
                else next(n for n in entries if n["nodeId"] == bus["fromNodeId"])
            )
        malformed: Any = copy.deepcopy(valid) if key else None
        if key:
            del malformed[key]
        entries.insert(0, malformed)
        original = copy.deepcopy(state)
        derived = derive_default_configuration(state)
        derived["components"].sort(key=lambda c: c["candidateId"])
        expected["components"].sort(key=lambda c: c["candidateId"])
        assert derived == expected
        assert state == original
        entries[:] = [malformed]
        if collection == "specifications":
            # Ignored spec items preserve the established default pins.
            result = derive_default_configuration(state)
            result["components"].sort(key=lambda c: c["candidateId"])
            assert result == expected
        else:
            with pytest.raises(
                CommandValidationError, match="Default configuration requires one usable"
            ):
                derive_default_configuration(state)
        if collection == "connections" and key == "status":
            _store.save_initialization_package(state)
            response = await client.post(
                f"/v1/projects/{pid}/execution-plan/propose",
                json={
                    "requestedBy": actor,
                    "baseProjectStateVersion": state["project"]["currentStateVersion"],
                    "basePlanVersion": 0,
                },
            )
            assert response.status_code == 422, response.text
            assert response.json()["error"]["code"] == "COMMAND_VALIDATION_FAILED"
            assert (
                "Default configuration requires one usable" in response.json()["error"]["message"]
            )
            assert _store.get_current_state(pid) == state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [None, "unrelated", "unrelated-live", "user-provided", "agent-inference", "manufacturer"],
)
async def test_fixture_plan_compatibility_preserves_provenance(invalid: str | None) -> None:
    from nexus_api.main import app

    actor = _actor()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH
    ) as client:
        pid, config = await _setup(client, actor, fixture=True)
        if invalid:
            overrides = {
                "partNumber": "FX-MCU-32",
                "manufacturer": "Fixture Compute",
                "source": "fixture",
            }
            if invalid == "unrelated":
                overrides["partNumber"] = "UNSUPPORTED-MCU"
            elif invalid == "unrelated-live":
                overrides.update(partNumber="UNSUPPORTED-MCU", source="user-provided")
            elif invalid == "manufacturer":
                overrides["manufacturer"] = "Other"
            else:
                overrides["source"] = invalid
            await _revise_candidates(client, pid, actor, overrides=overrides)
        before = (await client.get(f"/v1/projects/{pid}")).json()
        response = await _propose(client, pid, actor, config)
        assert response.status_code == (422 if invalid else 200), response.text
        if invalid:
            assert response.json()["error"]["code"] == "COMMAND_VALIDATION_FAILED"
        else:
            proposal = response.json()
            accepted = await _command(
                client,
                pid,
                actor,
                "artifact.accept-revision",
                proposal["workspace"],
                {"proposalId": proposal["commandResult"]["proposalId"]},
            )
            assert accepted["status"] == "completed", accepted
            after = (await client.get(f"/v1/projects/{pid}")).json()
            before_component = next(
                a for a in before["artifacts"] if a["artifactType"] == "component-plan"
            )
            after_component = next(
                a for a in after["artifacts"] if a["artifactType"] == "component-plan"
            )
            assert after_component == before_component
            assert {c["source"] for c in after_component["content"]["candidates"]} == {"fixture"}
