"""Phase 14D artifact-scoped workspace runtime API smoke."""

from __future__ import annotations

import base64
import secrets
import time

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

GREENHOUSE = (
    "I want to build a greenhouse monitoring node that measures temperature, "
    "humidity, soil moisture, and light, and reports the readings remotely."
)


def _cmd_id() -> str:
    return f"cmd_{secrets.token_hex(16)}"


def _actor() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "actorId": f"actor_{secrets.token_hex(8)}",
        "actorType": "user",
        "displayName": "User",
    }


@pytest.mark.asyncio
async def test_workspace_runtime_api_binding_files_snapshot_execute() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200
        project_id = created.json()["project"]["projectId"]
        actor = _actor()

        binding_resp = await client.get(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/runtime"
        )
        assert binding_resp.status_code == 200
        binding_body = binding_resp.json()
        binding = binding_body["binding"]
        assert binding["artifactType"] == "code-scratch"
        assert binding["capabilities"]["filesystem"] is True
        assert binding["capabilities"]["execution"] is True
        workspace_id = binding["workspaceId"]
        artifact_id = binding["artifactId"]
        draft_version = binding_body["draft"]["draftVersion"]

        lease = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": artifact_id,
                "workspaceId": workspace_id,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
                "requestedAt": "2026-08-11T00:00:00Z",
                "input": {},
            },
        )
        assert lease.status_code == 200, lease.text

        content_b64 = base64.b64encode(b"print('api')\n").decode("ascii")
        written = await client.put(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/file",
            json={
                "path": "main.py",
                "contentEncoding": "base64",
                "content": content_b64,
                "expectedDraftVersion": draft_version,
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
            },
        )
        assert written.status_code == 200, written.text

        files = await client.get(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/files"
        )
        assert files.status_code == 200
        assert any(f["path"] == "main.py" for f in files.json()["files"])

        snap = await client.post(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/snapshots",
            json={"reason": "api-smoke", "requestedBy": actor},
        )
        assert snap.status_code == 200, snap.text
        snapshot_id = snap.json()["snapshotId"]

        started = await client.post(
            f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/executions",
            json={
                "snapshotId": snapshot_id,
                "requestedBy": actor,
                "commandSpec": {
                    "schemaVersion": "1.0.0",
                    "executable": "python3",
                    "arguments": [
                        "-c",
                        "print('NEXUS_RUNTIME_READY'); open('out.txt','w').write('ok')",
                    ],
                    "workingDirectory": "",
                    "environment": [],
                    "declaredOutputs": [{"path": "out.txt", "kind": "result"}],
                },
            },
        )
        assert started.status_code == 200, started.text
        run_id = started.json()["executionRun"]["executionRunId"]

        final = None
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status = await client.get(f"/v1/projects/{project_id}/executions/{run_id}")
            assert status.status_code == 200
            final = status.json()["executionRun"]
            if final["status"] not in {"queued", "starting", "running", "cancelling"}:
                break
            time.sleep(0.05)
        assert final is not None
        assert final["status"] in {"completed", "completed-with-warnings"}, final

        logs = await client.get(f"/v1/projects/{project_id}/executions/{run_id}/logs")
        assert logs.status_code == 200
        stdout = "".join(c["content"] for c in logs.json()["chunks"] if c["stream"] == "stdout")
        assert "NEXUS_RUNTIME_READY" in stdout

        outputs = await client.get(f"/v1/projects/{project_id}/outputs")
        assert outputs.status_code == 200
        assert any(o.get("name") == "out.txt" for o in outputs.json()["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("artifact_type", "filesystem", "execution"),
    [("electrical-architecture", False, False), ("code-scratch", True, True)],
)
async def test_workspace_snapshot_capabilities_and_lease(
    artifact_type: str, filesystem: bool, execution: bool
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200, created.text
        project_id = created.json()["project"]["projectId"]
        path = f"/v1/projects/{project_id}/artifacts/{artifact_type}/workspace"
        runtime = await client.get(f"{path}/runtime")
        assert runtime.status_code == 200, runtime.text
        binding = runtime.json()["binding"]
        assert binding["capabilities"] == {
            "filesystem": filesystem,
            "snapshots": True,
            "execution": execution,
            "logs": execution,
        }
        actor = _actor()
        denied = await client.post(
            f"{path}/snapshots", json={"requestedBy": actor, "reason": "regression"}
        )
        assert denied.status_code == 422, denied.text
        assert denied.json()["error"]["code"] == "DRAFT_EDIT_LEASE_REQUIRED"
        lease = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": binding["artifactId"],
                "workspaceId": binding["workspaceId"],
                "baseArtifactVersion": binding["baseArtifactVersion"],
                "baseProjectStateVersion": binding["baseProjectStateVersion"],
                "requestedBy": actor,
                "requestedAt": "2026-11-03T00:00:00Z",
                "input": {},
            },
        )
        assert lease.status_code == 200, lease.text
        denied = await client.post(f"{path}/snapshots", json={"requestedBy": _actor()})
        assert denied.status_code == 422, denied.text
        assert denied.json()["error"]["code"] == "DRAFT_EDIT_LEASE_HELD"
        snapshot = await client.post(
            f"{path}/snapshots", json={"requestedBy": actor, "reason": "regression"}
        )
        assert snapshot.status_code == 200, snapshot.text
        body = snapshot.json()
        assert body["snapshotId"].startswith("snap_")
        assert body["content"]["kind"] == ("filesystem" if filesystem else "structured")
        if not filesystem:
            assert binding["workspaceType"] == "graph-workspace"
            assert body["content"]["structuredContent"] == runtime.json()["draft"]["content"]
        listed = await client.get(f"{path}/snapshots")
        assert listed.status_code == 200, listed.text
        assert [s["snapshotId"] for s in listed.json()["snapshots"]] == [body["snapshotId"]]
        refreshed = await client.get(f"{path}/runtime")
        assert refreshed.json()["binding"]["currentSnapshotId"] == body["snapshotId"]
