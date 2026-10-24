"""W7 HTTP regression helpers, exercised by the W6 scripted handoff fixture.

Scripted build/simulation and fixture source are regression evidence only.
Analysis executes real Python; no live model or simulator acceptance is claimed.
"""

import base64
import copy
import importlib
import json
import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from test_golden_lifecycle_http_api import (
    AUTH,
    _acquire_lease,
    _actor,
    _binding,
    _put_file,
    _versions,
    _wait_run,
)


@pytest.mark.parametrize(
    "change", ["requirement-set", "electrical-architecture", "analysis", "firmware", "test-plan"]
)
@pytest.mark.asyncio
async def test_accepted_change_replay_and_authorized_reruns_after_restart(
    monkeypatch, tmp_path, change
):
    from test_provenance_handoffs import run_http_provenance_handoffs

    async def lifecycle(pid, simulate):
        await exercise_invalidation_lifecycle(pid, change, simulate)

    await run_http_provenance_handoffs(monkeypatch, tmp_path, lifecycle)


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


async def exercise_invalidation_lifecycle(pid, change, simulate):
    prefix = f"/v1/projects/{pid}"
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:

        async def get(route):
            response = await client.get(f"{prefix}/{route}")
            assert response.status_code == 200, response.text
            return response.json()

        async def post(route, body):
            response = await client.post(f"{prefix}/{route}", json=body)
            assert response.status_code == 200, response.text
            return response.json()

        async def case(display="T7"):
            plan = await get("artifacts/test-plan")
            return next(c for c in plan["content"]["testCases"] if c["displayId"] == display)

        async def accept(kind, mutate=None):
            created = await post(f"artifacts/{kind}/workspace", {"requestedBy": _actor()})
            workspace, draft = created["workspace"], created["draft"]
            lease = draft.get("editLease") or {}
            actor = _actor()
            if lease:
                actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
            await _acquire_lease(client, pid, workspace, actor)

            async def command(command_type, data):
                current = (await post(f"artifacts/{kind}/workspace", {"requestedBy": actor}))[
                    "workspace"
                ]
                state = (await client.get(prefix)).json()["project"]["currentStateVersion"]
                return await post(
                    "artifact-commands",
                    {
                        "schemaVersion": "1.0.0",
                        "commandId": f"cmd_{secrets.token_hex(16)}",
                        "commandType": command_type,
                        "projectId": pid,
                        "artifactId": current["artifactId"],
                        "workspaceId": current["workspaceId"],
                        "baseArtifactVersion": current["baseArtifactVersion"],
                        "baseProjectStateVersion": state,
                        "requestedBy": actor,
                        "requestedAt": "2026-10-23T00:00:00Z",
                        "input": data,
                    },
                )

            if mutate:
                content = (
                    (await get("artifacts/test-plan"))["content"]
                    if kind == "test-plan"
                    else draft["content"]
                )
                mutate(content)
                await command(
                    "workspace.update-draft",
                    {
                        "content": content,
                        "expectedDraftVersion": draft["draftVersion"],
                    },
                )
            snapshot = await command(
                "workspace.create-snapshot", {"reason": "W7 accepted input change"}
            )
            proposal = await command(
                "artifact.propose-revision", {"snapshotId": snapshot["snapshotId"]}
            )
            assert "proposalId" in proposal, json.dumps(proposal)
            await command("artifact.accept-revision", {"proposalId": proposal["proposalId"]})

        # An unrelated accepted requirement change must leave both results current.
        def requirement(content, display):
            next(r for r in content["requirements"] if r["displayId"] == display)["statement"] += (
                " Revised input requirement."
            )

        original = await case()
        unrelated = await case("T8")
        assert unrelated["applicability"] == {"state": "CURRENT", "reasons": []}
        old_run = original["verificationBasis"]["executionRunId"]
        old_plan = await get("artifacts/test-plan")
        historical = _bytes(
            (await get(f"artifacts/test-plan?version={old_plan['artifactVersion']}"))["content"]
        )
        historical_outputs = await get("outputs")
        previews = {
            o["outputId"]: _bytes(
                await get(f"artifacts/analysis/workspace/outputs/{o['outputId']}/preview")
            )
            for o in historical_outputs["items"]
            if o["content"]["kind"] == "storage-reference"
            or isinstance((o["content"].get("structuredResult") or {}).get("text"), str)
        }
        await accept("requirement-set", lambda c: requirement(c, "R3"))
        assert await case() == original
        assert (await get("artifacts/test-plan"))["artifactVersion"] == old_plan["artifactVersion"]

        if change == "requirement-set":
            await accept(change, lambda c: requirement(c, "R7"))
        elif change == "test-plan":

            def criterion(content):
                target = next(c for c in content["testCases"] if c["displayId"] == "T7")
                target["criterion"]["expectedValue"] += 0.1

            await accept(change, criterion)
        elif change == "electrical-architecture":

            def interface(content):
                connection = next(c for c in content["connections"] if c["interfaceType"] == "i2c")
                # The existing golden architecture represents its pin intent in
                # the connection description; preserve every entity identity.
                pin = "GPIO21" if "GPIO21" in connection["description"] else "GPIO18"
                connection["description"] = connection["description"].replace(
                    pin, "GPIO18" if pin == "GPIO21" else "GPIO21"
                )

            await accept(change, interface)
        elif change == "firmware":
            body = await _binding(client, pid, change)
            workspace = await post("artifacts/firmware/workspace", {"requestedBy": _actor()})
            actor = _actor()
            lease = workspace["draft"]["editLease"]
            actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
            body["binding"]["baseProjectStateVersion"] = (await client.get(prefix)).json()[
                "project"
            ]["currentStateVersion"]
            response = await client.get(
                f"{prefix}/artifacts/firmware/workspace/file", params={"path": "src/main.cpp"}
            )
            await _put_file(
                client,
                pid,
                body["binding"],
                body["draft"]["draftVersion"],
                actor,
                "src/main.cpp",
                response.json()["content"].encode() + b"\n// W7 source revision\n",
            )
            await accept(change)
        else:
            body = await _binding(client, pid, "analysis")
            body["binding"]["baseProjectStateVersion"] = (await client.get(prefix)).json()[
                "project"
            ]["currentStateVersion"]
            actor = _actor()
            # Use the existing lease owner from the public workspace response.
            workspace = await post("artifacts/analysis/workspace", {"requestedBy": actor})
            lease = workspace["draft"].get("editLease") or {}
            actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
            await _acquire_lease(client, pid, body["binding"], actor)
            response = await client.get(
                f"{prefix}/artifacts/analysis/workspace/file", params={"path": "data/serial.log"}
            )
            assert response.status_code == 200, response.text
            await post(
                "artifacts/analysis/workspace/inputs/upload",
                {
                    "path": "data/serial.log",
                    "contentBase64": base64.b64encode(
                        response.json()["content"].encode() + b"TEL,10.0,0.02,0,1\n"
                    ).decode(),
                    "mediaType": "text/csv",
                    "requestedBy": actor,
                    **_versions(body["binding"], body["draft"]["draftVersion"]),
                },
            )
            await accept(change)

        stale = await case()
        assert stale["applicability"]["state"] == "STALE", stale["applicability"]
        history_fields = (
            "status",
            "assessment",
            "assessmentAuthority",
            "actualResult",
            "evidenceReferences",
        )
        assert _bytes({k: stale.get(k) for k in history_fields}) == _bytes(
            {k: original.get(k) for k in history_fields}
        )
        assert stale["assessment"] == "PASS"
        reason = stale["applicability"]["reasons"][0]
        assert reason["triggerArtifactType"] == change
        expected_dependency = {"requirement-set": "R7", "test-plan": original["testId"]}.get(
            change, change
        )
        assert reason["reason"] == f"DEPENDENCY_CHANGED:{expected_dependency}"
        if change == "test-plan":
            assert (
                stale["criterion"]["expectedValue"] == original["criterion"]["expectedValue"] + 0.1
            )
            assert len(reason["path"]) == 2
        assert len(reason["path"]) >= (5 if change == "firmware" else 1), reason
        assert reason["toVersion"] >= reason["fromVersion"]
        if change in {"requirement-set", "test-plan"}:
            assert await case("T8") == unrelated
        events = await get("verify/invalidations")
        assert reason["eventId"] in {e["eventId"] for e in events["items"]}
        chain = await get("verify/evidence-chain")
        affected = next(c for c in chain["chains"] if c["requirementId"] == "R7")
        assert affected["verificationState"] == "STALE"
        assert affected["applicability"] == stale["applicability"]
        outputs = await get("outputs")

        main._kernel.jobs.shutdown()
        importlib.reload(main)
        assert await get("verify/evidence-chain") == chain
        assert await get("verify/invalidations") == events
        assert (
            _bytes(
                (await get(f"artifacts/test-plan?version={old_plan['artifactVersion']}"))["content"]
            )
            == historical
        )
        assert await get("outputs") == outputs

        # Deliver the same invalidation event twice; this is the existing service's
        # duplicate-processing seam, not a separate product endpoint.
        # Test Plan invalidation writes a system revision after the accepted
        # criterion revision; redeliver the original trigger, not that projection.
        current = await get(f"artifacts/{change}?version={reason['toVersion']}")
        previous = (
            await get(f"artifacts/{change}?version={current['artifactVersion'] - 1}")
            if current["artifactVersion"] > 1
            else None
        )
        for _ in range(2):
            assert main._kernel.invalidation.process(pid, previous, current) == {"changed": False}
        assert await get("verify/invalidations") == events
        assert (
            _bytes(
                (await get(f"artifacts/test-plan?version={old_plan['artifactVersion']}"))["content"]
            )
            == historical
        )

        actor = _actor()
        if change == "test-plan":
            review = await post("artifacts/test-plan/workspace", {"requestedBy": actor})
            lease = review["draft"]["editLease"]
            actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
        replay = await post(
            "verify/promote-execution",
            {"executionRunId": old_run, "requestedBy": actor, "accept": True},
        )
        replayed = await case()
        # Identical evidence is an idempotent no-op for the original case:
        # stamp skips it, preserving STALE and its dependency-change reasons.
        assert replayed == stale
        assert replay["idempotent"] is True
        assert replay["changed"] is False
        if change == "test-plan":
            introduced_display = (
                f"T{max(int(c['displayId'][1:]) for c in old_plan['content']['testCases']) + 1}"
            )

            def introduce_case(content):
                introduced = copy.deepcopy(
                    next(c for c in content["testCases"] if c["displayId"] == "T7")
                )
                introduced.update(
                    testId=f"test_{secrets.token_hex(16)}",
                    displayId=introduced_display,
                    status="ready",
                    assessment="NOT_ASSESSED",
                    evidenceReferences=[],
                    producedOutputIds=[],
                )
                for key in (
                    "applicability",
                    "verificationBasis",
                    "actualResult",
                    "assessmentAuthority",
                    "executionRunId",
                ):
                    introduced.pop(key, None)
                content["testCases"].append(introduced)

            await accept(change, introduce_case)
            # The new case was accepted after this run captured its inputs. Promotion can
            # assess it, but cannot invent the missing criterion dependency.
            promoted = await post(
                "verify/promote-execution",
                {"executionRunId": old_run, "requestedBy": actor, "accept": True},
            )
            assert promoted["changed"] is True
            introduced = await case(introduced_display)
            assert introduced["applicability"]["state"] == "RECHECK_REQUIRED", json.dumps(
                introduced
            )
            assert [r["reason"] for r in introduced["applicability"]["reasons"]] == [
                "UNKNOWN_DEPENDENCY"
            ]

        # Execute all current affected tool steps and import the newly produced
        # observations through the same endpoints as the original golden run.
        for kind in ("firmware", "analysis"):
            workspace = await post(f"artifacts/{kind}/workspace", {"requestedBy": actor})
            lease = workspace["draft"].get("editLease") or {}
            if lease:
                actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
            binding = (await _binding(client, pid, kind))["binding"]
            binding["baseProjectStateVersion"] = (await client.get(prefix)).json()["project"][
                "currentStateVersion"
            ]
            await _acquire_lease(client, pid, binding, actor)
            if kind == "firmware":
                if change == "electrical-architecture":
                    body = await _binding(client, pid, kind)
                    body["binding"]["baseProjectStateVersion"] = (await client.get(prefix)).json()[
                        "project"
                    ]["currentStateVersion"]
                    response = await client.get(
                        f"{prefix}/artifacts/firmware/workspace/file",
                        params={"path": "src/main.cpp"},
                    )
                    source = response.json()["content"]
                    source = (
                        source.replace("21", "18")
                        if "PIN_SDA = 21" in source
                        else source.replace("18", "21")
                    )
                    await _put_file(
                        client,
                        pid,
                        body["binding"],
                        body["draft"]["draftVersion"],
                        actor,
                        "src/main.cpp",
                        source.encode(),
                    )
                    await accept("firmware")
                started = await post("artifacts/firmware/workspace/compile", {"requestedBy": actor})
                run = await _wait_run(client, pid, started["executionRun"]["executionRunId"])
                assert run["status"] == "completed", run
                outputs = (await get("outputs"))["items"]
                serial = await simulate(
                    client,
                    pid,
                    actor,
                    [o for o in outputs if o["executionRunId"] == run["executionRunId"]],
                )
            else:
                body = await _binding(client, pid, kind)
                body["binding"]["baseProjectStateVersion"] = (await client.get(prefix)).json()[
                    "project"
                ]["currentStateVersion"]
                await post(
                    "artifacts/analysis/workspace/inputs/import-produced-output",
                    {
                        "outputId": serial["outputId"],
                        "path": "data/serial.log",
                        "requestedBy": actor,
                        **_versions(body["binding"], body["draft"]["draftVersion"]),
                    },
                )
                started = await post("artifacts/analysis/workspace/run", {"requestedBy": actor})
                run = await _wait_run(client, pid, started["executionRun"]["executionRunId"])
                assert run["status"] == "completed", run
        before_proposal = await case()
        proposed = await post(
            "verify/promote-execution",
            {"executionRunId": run["executionRunId"], "requestedBy": actor, "accept": False},
        )
        assert await case() == before_proposal
        review = await post("artifacts/test-plan/workspace", {"requestedBy": actor})
        workspace = review["workspace"]
        accepted = await post(
            "artifact-commands",
            {
                "schemaVersion": "1.0.0",
                "commandId": f"cmd_{secrets.token_hex(16)}",
                "commandType": "artifact.accept-revision",
                "projectId": pid,
                "artifactId": workspace["artifactId"],
                "workspaceId": workspace["workspaceId"],
                "baseArtifactVersion": workspace["baseArtifactVersion"],
                "baseProjectStateVersion": (await client.get(prefix)).json()["project"][
                    "currentStateVersion"
                ],
                "requestedBy": actor,
                "requestedAt": "2026-10-23T00:00:00Z",
                "input": {"proposalId": proposed["proposalId"]},
            },
        )
        assert accepted["status"] == "completed"
        restored = await case()
        assert restored["applicability"] == {"state": "CURRENT", "reasons": []}
        events = await get("verify/invalidations")
        assert any(
            e["eventType"] == "verification.revalidated"
            and e["payload"]["executionRunId"] == run["executionRunId"]
            for e in (await get("events?limit=100"))["items"]
        )
        chain = await get("verify/evidence-chain")
        affected = next(c for c in chain["chains"] if c["requirementId"] == "R7")
        assert affected["verificationState"] == "VERIFIED"
        assert affected["applicability"] == restored["applicability"]
        main._kernel.jobs.shutdown()
        importlib.reload(main)
        assert await get("verify/evidence-chain") == chain
        assert await get("verify/invalidations") == events
        assert (
            _bytes(
                (await get(f"artifacts/test-plan?version={old_plan['artifactVersion']}"))["content"]
            )
            == historical
        )
        for output_id, preview in previews.items():
            assert (
                _bytes(await get(f"artifacts/analysis/workspace/outputs/{output_id}/preview"))
                == preview
            )
        for output in historical_outputs["items"]:
            response = await get(f"outputs/{output['outputId']}")
            assert _bytes(response) == _bytes(output)
        repeated = await post(
            "verify/promote-execution",
            {
                "executionRunId": run["executionRunId"],
                "requestedBy": actor,
                "accept": True,
            },
        )
        assert repeated["idempotent"] is True
        assert repeated["changed"] is False
        assert await case() == restored
        assert await get("verify/invalidations") == events
