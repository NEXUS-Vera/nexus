"""M5 accepted changes and restart persistence through public HTTP routes only."""

import importlib
from dataclasses import replace
from pathlib import Path

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient
from test_golden_lifecycle_http_api import AUTH, _actor, run_golden_lifecycle_over_http


@pytest.mark.asyncio
async def test_m5_invalidation_over_http_survives_sqlite_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = main.settings
    monkeypatch.setattr(
        main,
        "settings",
        replace(original, storage_backend="sqlite", database_url=f"sqlite:///{tmp_path / 'm5.db'}"),
    )
    # main imports settings from config when constructed, including on restart.
    monkeypatch.setattr("nexus_api.config.settings", main.settings)
    try:
        importlib.reload(main)
        project_id = await run_golden_lifecycle_over_http(monkeypatch)
        prefix = f"/v1/projects/{project_id}"
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client:
            before = (await client.get(f"{prefix}/verify/evidence-chain")).json()
            old = next(r for r in before["chains"] if r["requirementId"] == "R7")
            assert old["applicability"]["state"] == "CURRENT"
            artifact = (await client.get(f"{prefix}/artifacts/requirement-set")).json()
            state = (await client.get(prefix)).json()
            actor = _actor()
            workspace = await client.post(
                f"{prefix}/artifacts/requirement-set/workspace", json={"requestedBy": actor}
            )
            assert workspace.status_code == 200, workspace.text
            base = {
                "schemaVersion": "1.0.0",
                "projectId": project_id,
                "artifactId": artifact["artifactId"],
                "workspaceId": workspace.json()["workspace"]["workspaceId"],
                "baseArtifactVersion": artifact["artifactVersion"],
                "baseProjectStateVersion": state["project"]["currentStateVersion"],
                "requestedBy": actor,
                "requestedAt": "2026-10-22T00:00:00Z",
            }

            async def command(kind: str, body: dict) -> dict:
                import secrets

                response = await client.post(
                    f"{prefix}/artifact-commands",
                    json={
                        **base,
                        "commandId": f"cmd_{secrets.token_hex(16)}",
                        "commandType": kind,
                        "input": body,
                    },
                )
                assert response.status_code == 200, response.text
                return response.json()

            await command("workspace.acquire-edit-lease", {})
            content = artifact["content"]
            next(r for r in content["requirements"] if r["displayId"] == "R7")["statement"] = (
                "Stationary accel_x RMS noise shall be below 0.01 g."
            )
            await command(
                "workspace.update-draft",
                {
                    "content": content,
                    "expectedDraftVersion": workspace.json()["draft"]["draftVersion"],
                },
            )
            snapshot = await command(
                "workspace.create-snapshot", {"reason": "M5 requirement change"}
            )
            proposal = await command(
                "artifact.propose-revision", {"snapshotId": snapshot["snapshotId"]}
            )
            await command("artifact.accept-revision", {"proposalId": proposal["proposalId"]})
            chain_response = await client.get(f"{prefix}/verify/evidence-chain")
            assert chain_response.status_code == 200, chain_response.text
            chain = chain_response.json()
            r7 = next(r for r in chain["chains"] if r["requirementId"] == "R7")
            assert r7["verificationState"] == r7["applicability"]["state"] == "STALE"
            assert r7["assessment"] == old["assessment"] == "PASS"
            assert r7["evidenceReferences"] == old["evidenceReferences"]
            reason = r7["applicability"]["reasons"][0]
            assert reason["triggerArtifactType"] == "requirement-set"
            assert reason["fromVersion"] == artifact["artifactVersion"]
            assert reason["toVersion"] == artifact["artifactVersion"] + 1
            assert reason["reason"] and reason["path"]
            invalidations = await client.get(f"{prefix}/verify/invalidations")
            assert invalidations.status_code == 200, invalidations.text
            events = invalidations.json()
            assert reason["eventId"] in {e["eventId"] for e in events["items"]}
            assert all(e["eventType"] == "verification.invalidated" for e in events["items"])

        importlib.reload(main)
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client:
            assert (await client.get(f"{prefix}/verify/evidence-chain")).json() == chain
            assert (await client.get(f"{prefix}/verify/invalidations")).json() == events
    finally:
        monkeypatch.setattr("nexus_api.config.settings", original)
        importlib.reload(main)
