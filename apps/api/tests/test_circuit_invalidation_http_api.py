"""Offline cross-tool invalidation through the HTTP electrical circuit draft.

The API owns electrical-architecture, not an editable circuit/diagram.json
artifact. Its accepted wiring intent is the source of the Wokwi diagram export.
Scripted compiler/simulator outputs are regression evidence, not hardware proof.
"""

import copy
import secrets
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from test_golden_lifecycle_http_api import AUTH, _acquire_lease, _actor, _wait_run
from test_provenance_handoffs import run_http_provenance_handoffs
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_circuit_revision_invalidates_simulation_but_preserves_compile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exercised = False

    async def lifecycle(pid: str, simulate: Any) -> None:
        nonlocal exercised
        # The shared SQLite/file-store harness invokes its lifecycle twice.
        if exercised:
            return
        exercised = True
        prefix = f"/v1/projects/{pid}"
        actor = _actor()
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client:

            async def get(route: str) -> dict[str, Any]:
                response = await client.get(f"{prefix}/{route}" if route else prefix)
                assert response.status_code == 200, response.text
                return cast(dict[str, Any], response.json())

            async def post(route: str, data: dict[str, Any]) -> dict[str, Any]:
                response = await client.post(f"{prefix}/{route}", json=data)
                assert response.status_code == 200, response.text
                return cast(dict[str, Any], response.json())

            async def accept(kind: str, content: dict[str, Any] | None) -> None:
                workspace = await post(f"artifacts/{kind}/workspace", {"requestedBy": actor})
                lease = workspace["draft"].get("editLease") or {}
                if lease:
                    actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
                await _acquire_lease(client, pid, workspace["workspace"], actor)

                async def command(command_type: str, data: dict[str, Any]) -> dict[str, Any]:
                    current = await post(f"artifacts/{kind}/workspace", {"requestedBy": actor})
                    state = await get("")
                    return await post(
                        "artifact-commands",
                        {
                            "schemaVersion": "1.0.0",
                            "commandId": f"cmd_{secrets.token_hex(16)}",
                            "commandType": command_type,
                            "projectId": pid,
                            **{
                                key: current["workspace"][key]
                                for key in ("artifactId", "workspaceId", "baseArtifactVersion")
                            },
                            "baseProjectStateVersion": state["project"]["currentStateVersion"],
                            "requestedBy": actor,
                            "requestedAt": "2026-11-06T00:00:00Z",
                            "input": data,
                        },
                    )

                if content is not None:
                    await command(
                        "workspace.update-draft",
                        {
                            "content": content,
                            "expectedDraftVersion": workspace["draft"]["draftVersion"],
                        },
                    )
                snapshot = await command(
                    "workspace.create-snapshot", {"reason": "circuit regression"}
                )
                proposal = await command(
                    "artifact.propose-revision", {"snapshotId": snapshot["snapshotId"]}
                )
                accepted = await command(
                    "artifact.accept-revision", {"proposalId": proposal["proposalId"]}
                )
                assert accepted["status"] == "completed", accepted

            async def cases() -> dict[str, Any]:
                plan = await get("artifacts/test-plan")
                return {case["displayId"]: case for case in plan["content"]["testCases"]}

            outputs = (await get("outputs"))["items"]
            elf = next(o for o in outputs if o["name"].endswith("firmware.elf"))
            preview = await get("artifacts/electrical-architecture/circuit-simulation/preview")
            pins = {(c["sourcePin"], c["targetPin"]) for c in preview["connections"]}
            assert ("D21", "SDA") in pins
            assert ("D22", "SCL") in pins

            # Golden R1 is I2C, not compile. Give this regression an independent
            # compile-output existence criterion and three simulation observations.
            plan = (await get("artifacts/test-plan"))["content"]
            for case in plan["testCases"]:
                display = case["displayId"]
                if display == "T1":
                    case.update(
                        title="Firmware compile output",
                        verificationMethod="analysis",
                        criterion={"criterionType": "existence", "outputName": elf["name"]},
                    )
                elif display in {"T4", "T5", "T6"}:
                    marker = "NEXUS_MPU_READY" if display == "T4" else "TEL,"
                    case.update(
                        verificationMethod="simulation",
                        criterion={"criterionType": "contains", "marker": marker},
                    )
            await accept("test-plan", plan)

            async def refresh() -> str:
                # Rebuild against the current circuit and reviewed criteria before
                # simulation; replaying the old ELF retains its old circuit basis.
                await accept("firmware", None)
                workspace = await post("artifacts/firmware/workspace", {"requestedBy": actor})
                lease = workspace["draft"]["editLease"]
                actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
                started = await post("artifacts/firmware/workspace/compile", {"requestedBy": actor})
                run = await _wait_run(client, pid, started["executionRun"]["executionRunId"])
                assert run["status"] == "completed", run
                elf = next(
                    o
                    for o in (await get("outputs"))["items"]
                    if o["executionRunId"] == run["executionRunId"]
                    and o["name"].endswith("firmware.elf")
                )

                serial = await simulate(client, pid, actor, [elf])
                await post(
                    "verify/promote-execution",
                    {
                        "executionRunId": serial["executionRunId"],
                        "requestedBy": actor,
                        "accept": True,
                    },
                )
                # The summary-only route assesses the compile existence criterion
                # without replacing simulation marker observations with build logs.
                await post(
                    "verify/promote-analysis-summary",
                    {
                        "executionRunId": elf["executionRunId"],
                        "summary": {},
                        "producedOutputNames": [elf["name"]],
                        "requestedBy": actor,
                        "accept": True,
                    },
                )
                return str(serial["executionRunId"])

            old_run = await refresh()
            before = await cases()
            for display in ("T1", "T4", "T5", "T6"):
                assert before[display]["assessment"] == "PASS", before[display]
                assert before[display]["applicability"] == {"state": "CURRENT", "reasons": []}
                assert f"R{display[1:]}" in before[display]["linkedRequirementIds"]
            assert "electrical-architecture" not in {
                d["artifactType"] for d in before["T1"]["verificationBasis"]["dependencies"]
            }
            electrical = await get("artifacts/electrical-architecture")
            changed = copy.deepcopy(electrical["content"])
            connection = next(c for c in changed["connections"] if c["interfaceType"] == "i2c")
            # The current translator uses a fixed 21/22 pin profile; change its
            # accepted circuit source, without claiming GPIO18 was materialized.
            connection["description"] = connection["description"].replace("GPIO21", "GPIO18")
            assert changed != electrical["content"]
            await accept("electrical-architecture", changed)
            current = await get("artifacts/electrical-architecture")
            assert current["artifactVersion"] == electrical["artifactVersion"] + 1
            assert current["content"] == changed

            stale = await cases()
            assert stale["T1"] == before["T1"], (
                "Circuit edits must preserve firmware-only compile evidence",
                stale["T1"]["applicability"],
            )
            for display in ("T4", "T5", "T6"):
                case = stale[display]
                assert case["applicability"]["state"] in {"STALE", "RECHECK_REQUIRED"}, case
                reasons = case["applicability"]["reasons"]
                assert any(
                    r["triggerArtifactType"] == "electrical-architecture"
                    and any(
                        code in r["reason"] for code in ("CIRCUIT_MODIFIED", "DEPENDENCY_CHANGED")
                    )
                    for r in reasons
                ), reasons
                for key in ("assessment", "evidenceReferences", "verificationBasis"):
                    assert case[key] == before[display][key]

            new_run = await refresh()
            assert new_run != old_run
            restored = await cases()
            for display in ("T4", "T5", "T6"):
                assert restored[display]["assessment"] == "PASS"
                assert restored[display]["applicability"] == {"state": "CURRENT", "reasons": []}
            for display in ("T4", "T5", "T6"):
                basis = restored[display]["verificationBasis"]
                assert basis["executionRunId"] == new_run
                assert any(
                    d["artifactType"] == "electrical-architecture"
                    and d["artifactVersion"] == current["artifactVersion"]
                    for d in basis["dependencies"]
                )

    await run_http_provenance_handoffs(monkeypatch, tmp_path, lifecycle)
    assert exercised
