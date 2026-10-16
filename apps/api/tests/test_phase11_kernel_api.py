"""Phase 11 kernel API tests."""

from __future__ import annotations

import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.config import settings
from nexus_api.main import app

AUTH_HEADERS = {"Authorization": f"Bearer {settings.session_token}"}

GREENHOUSE = (
    "I want to build a greenhouse monitoring node that measures temperature, "
    "humidity, soil moisture, and light, and reports the readings remotely."
)


def _cmd_id() -> str:
    return f"cmd_{secrets.token_hex(16)}"


def _actor() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "actorId": f"actor_{secrets.token_hex(16)}",
        "actorType": "user",
        "displayName": "User",
    }


@pytest.mark.asyncio
async def test_phase11_kernel_api_flow() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=AUTH_HEADERS
    ) as client:
        types = await client.get("/v1/artifact-types")
        assert types.status_code == 200
        names = {t["artifactType"] for t in types.json()["artifactTypes"]}
        assert names == {
            "project-brief",
            "requirement-set",
            "functional-architecture",
            "next-action",
            "component-plan",
            "code-scratch",
            "firmware",
            "electrical-architecture",
            "physical-architecture",
        }

        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200, created.text
        project_id = created.json()["project"]["projectId"]
        req = next(a for a in created.json()["artifacts"] if a["artifactType"] == "requirement-set")

        board = await client.get(f"/v1/projects/{project_id}/board")
        assert board.status_code == 200
        summaries = {s["artifactType"] for s in board.json()["artifactSummaries"]}
        assert "component-plan" in summaries

        missing = await client.get(f"/v1/projects/{project_id}/artifacts/requirement-set/workspace")
        assert missing.status_code == 200, missing.text
        assert missing.json()["workspace"]["artifactType"] == "requirement-set"

        ws = await client.post(
            f"/v1/projects/{project_id}/artifacts/requirement-set/workspace",
            json={"requestedBy": _actor()},
        )
        assert ws.status_code == 200, ws.text
        workspace_id = ws.json()["workspace"]["workspaceId"]
        assert workspace_id == missing.json()["workspace"]["workspaceId"]
        draft_version = ws.json()["draft"]["draftVersion"]
        editor = _actor()

        lease = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": req["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": editor,
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {},
            },
        )
        assert lease.status_code == 200, lease.text

        conflict = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.update-draft",
                "projectId": project_id,
                "artifactId": req["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": 99,
                "baseProjectStateVersion": 1,
                "requestedBy": editor,
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {"content": {"requirements": []}, "expectedDraftVersion": draft_version},
            },
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "ARTIFACT_VERSION_CONFLICT"

        updated = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.update-draft",
                "projectId": project_id,
                "artifactId": req["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": editor,
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {
                    "content": {"requirements": [{"statement": "api"}]},
                    "expectedDraftVersion": draft_version,
                },
            },
        )
        assert updated.status_code == 200, updated.text

        snap = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.create-snapshot",
                "projectId": project_id,
                "artifactId": req["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": editor,
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {"reason": "api-checkpoint"},
            },
        )
        assert snap.status_code == 200, snap.text

        events = await client.get(f"/v1/projects/{project_id}/events?limit=10")
        assert events.status_code == 200
        assert len(events.json()["items"]) >= 1

        page = await client.get(f"/v1/projects/{project_id}/events?limit=1")
        assert page.status_code == 200
        assert page.json().get("nextCursor")

        bad_cmd = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": "bad",
                "commandType": "workspace.create-snapshot",
                "projectId": project_id,
                "artifactId": req["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": _actor(),
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {"reason": "x"},
            },
        )
        assert bad_cmd.status_code == 422

        executions = await client.get(f"/v1/projects/{project_id}/executions?limit=5")
        assert executions.status_code == 200

        graph = await client.get(f"/v1/projects/{project_id}/graph?direction=both&maxDepth=2")
        assert graph.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_type", ["vera", "embedded-systems-agent", "execution"])
async def test_api_non_user_acceptance_preserves_head(actor_type: str) -> None:
    """M4: the HTTP boundary denies non-user approval of a real proposal."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH_HEADERS
    ) as client:
        initialized = await client.post("/v1/projects/initialize", json={"message": GREENHOUSE})
        assert initialized.status_code == 200, initialized.text
        package = initialized.json()
        project_id = package["project"]["projectId"]
        artifact = next(a for a in package["artifacts"] if a["artifactType"] == "requirement-set")
        prefix = f"/v1/projects/{project_id}"
        owner = _actor()
        created = await client.post(
            f"{prefix}/artifacts/requirement-set/workspace", json={"requestedBy": owner}
        )
        assert created.status_code == 200, created.text
        base = {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "artifactId": artifact["artifactId"],
            "workspaceId": created.json()["workspace"]["workspaceId"],
            "baseArtifactVersion": 1,
            "baseProjectStateVersion": 1,
            "requestedBy": owner,
            "requestedAt": "2026-08-04T12:00:00Z",
        }
        lease = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "input": {},
            },
        )
        assert lease.status_code == 200, lease.text
        snapshot = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "workspace.create-snapshot",
                "input": {"reason": "authority"},
            },
        )
        assert snapshot.status_code == 200, snapshot.text
        proposal = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "artifact.propose-revision",
                "input": {"snapshotId": snapshot.json()["snapshotId"]},
            },
        )
        assert proposal.status_code == 200, proposal.text
        denied = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "artifact.accept-revision",
                "requestedBy": {**_actor(), "actorType": actor_type},
                "input": {"proposalId": proposal.json()["proposalId"]},
            },
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "GOVERNANCE_REJECTED"
        current = await client.get(f"{prefix}/artifacts/requirement-set")
        assert current.status_code == 200, current.text
        assert current.json() == artifact


@pytest.mark.asyncio
async def test_api_positive_artifact_lifecycle() -> None:
    """M1: propose, accept and execute a revision through the HTTP boundary."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=AUTH_HEADERS
    ) as client:
        initialized = await client.post("/v1/projects/initialize", json={"message": GREENHOUSE})
        assert initialized.status_code == 200, initialized.text
        package = initialized.json()
        project_id = package["project"]["projectId"]
        artifact = next(a for a in package["artifacts"] if a["artifactType"] == "requirement-set")
        prefix = f"/v1/projects/{project_id}"
        owner = _actor()
        created = await client.post(
            f"{prefix}/artifacts/requirement-set/workspace", json={"requestedBy": owner}
        )
        assert created.status_code == 200, created.text
        base = {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "artifactId": artifact["artifactId"],
            "workspaceId": created.json()["workspace"]["workspaceId"],
            "baseArtifactVersion": 1,
            "baseProjectStateVersion": 1,
            "requestedBy": owner,
            "requestedAt": "2026-08-04T12:00:00Z",
        }
        lease = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "input": {},
            },
        )
        assert lease.status_code == 200, lease.text
        snapshot = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "workspace.create-snapshot",
                "input": {"reason": "lifecycle input"},
            },
        )
        assert snapshot.status_code == 200, snapshot.text
        proposal = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "artifact.propose-revision",
                "input": {"snapshotId": snapshot.json()["snapshotId"]},
            },
        )
        assert proposal.status_code == 200, proposal.text
        assert proposal.json()["status"] == "completed"
        accepted = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "artifact.accept-revision",
                "input": {"proposalId": proposal.json()["proposalId"]},
            },
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "completed"
        current = await client.get(f"{prefix}/artifacts/requirement-set")
        assert current.status_code == 200, current.text
        head = current.json()
        assert head["artifactVersion"] == artifact["artifactVersion"] + 1 == 2
        assert head["artifactId"] != artifact["artifactId"]
        project = await client.get(prefix)
        assert project.status_code == 200, project.text
        assert project.json()["project"]["currentStateVersion"] == 2

        base.update(artifactId=head["artifactId"], baseArtifactVersion=2, baseProjectStateVersion=2)
        snapshot = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "workspace.create-snapshot",
                "input": {"reason": "accepted input"},
            },
        )
        assert snapshot.status_code == 200, snapshot.text
        executed = await client.post(
            f"{prefix}/artifact-commands",
            json={
                **base,
                "commandId": _cmd_id(),
                "commandType": "artifact.execute",
                "input": {
                    "snapshotId": snapshot.json()["snapshotId"],
                    "capability": "fake-execution",
                },
            },
        )
        assert executed.status_code == 200, executed.text
        assert executed.json()["status"] == "completed"
        executions = await client.get(f"{prefix}/executions")
        assert executions.status_code == 200, executions.text
        [run] = executions.json()["items"]
        assert run["executionRunId"] == executed.json()["executionRunId"]
        assert run["status"] == "completed"
        assert run["artifactId"] == head["artifactId"]
        assert run["baseArtifactVersion"] == run["baseProjectStateVersion"] == 2
        assert run["inputSnapshotId"] == snapshot.json()["snapshotId"]
        assert run["outputReferences"] == executed.json()["outputReferences"]
        assert run["outputReferences"]
        events = await client.get(f"{prefix}/events")
        assert events.status_code == 200, events.text
        assert {event["eventType"] for event in events.json()["items"]} >= {
            "artifact.revision-proposed",
            "artifact.revision-accepted",
            "artifact.superseded",
            "execution.queued",
            "execution.started",
            "execution.completed",
            "output.produced",
            "evidence.attached",
        }
