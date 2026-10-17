"""PUT .../workspace/investigation: validated analysis investigation metadata.

Before this route, an external agent could only write nexus/investigation.json
through the generic workspace file PUT, which skips validation and records the
file as USER-authored.
"""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

AUTH = {"Authorization": "Bearer nexus-dev-session-token"}
PROMPT = (
    "Build an ESP32-based vibration monitor using an MPU6050. "
    "It should stream acceleration telemetry and analyze stationary sensor noise "
    "to verify that accel_x RMS noise stays below 0.10 g."
)
INVESTIGATION_PATH = "nexus/investigation.json"


def _actor() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "actorId": f"actor_{secrets.token_hex(8)}",
        "actorType": "user",
        "displayName": "User",
    }


def _investigation(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "investigationId": f"ainv_{secrets.token_hex(8)}",
        "title": "Stationary accel_x noise",
        "purpose": "verification",
        "question": "Is accel_x RMS noise below 0.10 g?",
        "linkedRequirementIds": [],
        "lifecycleStage": "INPUTS",
    }
    payload.update(overrides)
    return payload


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=AUTH)


async def _project(client: AsyncClient) -> str:
    created = await client.post(
        "/v1/projects/initialize", json={"message": PROMPT, "autonomyMode": "collaborate"}
    )
    assert created.status_code == 200, created.text
    return str(created.json()["project"]["projectId"])


async def _leased_binding(
    client: AsyncClient, project_id: str, artifact_type: str, actor: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    resp = await client.get(
        f"/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/runtime"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    binding = body["binding"]
    lease = await client.post(
        f"/v1/projects/{project_id}/artifact-commands",
        json={
            "schemaVersion": "1.0.0",
            "commandId": f"cmd_{secrets.token_hex(16)}",
            "commandType": "workspace.acquire-edit-lease",
            "projectId": project_id,
            "artifactId": binding["artifactId"],
            "workspaceId": binding["workspaceId"],
            "baseArtifactVersion": binding["baseArtifactVersion"],
            "baseProjectStateVersion": binding["baseProjectStateVersion"],
            "requestedBy": actor,
            "requestedAt": "2026-10-17T00:00:00Z",
            "input": {},
        },
    )
    assert lease.status_code == 200, lease.text
    return binding, int(body["draft"]["draftVersion"])


def _versions(binding: dict[str, Any], draft_version: int) -> dict[str, int]:
    return {
        "expectedDraftVersion": draft_version,
        "baseArtifactVersion": binding["baseArtifactVersion"],
        "baseProjectStateVersion": binding["baseProjectStateVersion"],
    }


def _url(project_id: str, artifact_type: str = "analysis") -> str:
    return f"/v1/projects/{project_id}/artifacts/{artifact_type}/workspace/investigation"


@pytest.mark.asyncio
async def test_investigation_put_writes_generated_validated_metadata() -> None:
    actor = _actor()
    investigation = _investigation()
    async with _client() as client:
        project_id = await _project(client)
        binding, draft = await _leased_binding(client, project_id, "analysis", actor)
        resp = await client.put(
            _url(project_id),
            json={
                "investigation": investigation,
                "requestedBy": actor,
                **_versions(binding, draft),
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["path"] == INVESTIGATION_PATH
        assert int(body["draft"]["draftVersion"]) > draft

        read = await client.get(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/file",
            params={"path": INVESTIGATION_PATH},
        )
        assert read.status_code == 200, read.text
        read_body = read.json()
        assert read_body["file"]["origin"] == "GENERATED"
        assert read_body["file"]["generatedFrom"] == "analysis-investigation.v1"
        assert read_body["encoding"] == "utf-8"
        assert json.loads(read_body["content"]) == investigation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("investigation", "message"),
    [
        (_investigation(schemaVersion="2.0.0"), "investigation.schemaVersion must be 1.0.0"),
        (_investigation(investigationId=""), "investigationId is required"),
        (_investigation(title="   "), "title is required"),
        (_investigation(purpose="guess"), "purpose must be exploration or verification"),
        # An unhashable purpose used to raise TypeError inside the validator (a 500).
        (_investigation(purpose=["verification"]), "purpose must be exploration or verification"),
        (_investigation(lifecycleStage="DONE"), "lifecycleStage must be one of"),
        (_investigation(question=3), "question must be a string or null"),
        (
            _investigation(linkedRequirementIds="R7"),
            "linkedRequirementIds must be a list of strings",
        ),
        (
            _investigation(verificationCriterion="metric < 0.1"),
            "verificationCriterion must be an object or null",
        ),
    ],
)
async def test_investigation_put_rejects_invalid_metadata(
    investigation: dict[str, Any], message: str
) -> None:
    actor = _actor()
    async with _client() as client:
        project_id = await _project(client)
        binding, draft = await _leased_binding(client, project_id, "analysis", actor)
        resp = await client.put(
            _url(project_id),
            json={
                "investigation": investigation,
                "requestedBy": actor,
                **_versions(binding, draft),
            },
        )
        assert resp.status_code == 422, resp.text
        error = resp.json()["error"]
        assert error["code"] == "COMMAND_VALIDATION_FAILED"
        assert error["message"].startswith(message)
        # Nothing was written.
        read = await client.get(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/file",
            params={"path": INVESTIGATION_PATH},
        )
        assert read.status_code == 404, read.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            {"expectedDraftVersion": 1, "baseArtifactVersion": 1, "baseProjectStateVersion": 1},
            "Missing required field: investigation",
        ),
        (
            {
                "investigation": _investigation(),
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
            },
            "Missing required field: expectedDraftVersion",
        ),
        (
            {
                "investigation": "not-an-object",
                "expectedDraftVersion": 1,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
            },
            "investigation must be an object.",
        ),
        (
            {
                "investigation": _investigation(),
                "expectedDraftVersion": "x",
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
            },
            "expectedDraftVersion must be an integer.",
        ),
        (
            {
                "investigation": _investigation(),
                "expectedDraftVersion": True,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
            },
            "expectedDraftVersion must be an integer.",
        ),
    ],
)
async def test_investigation_put_rejects_bad_request_fields(
    body: dict[str, Any], message: str
) -> None:
    async with _client() as client:
        project_id = await _project(client)
        resp = await client.put(_url(project_id), json=body)
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"] == {
            **resp.json()["error"],
            "code": "COMMAND_VALIDATION_FAILED",
            "message": message,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "message"),
    [(b"{not json", "Invalid JSON body."), (b"[1, 2]", "Body must be an object.")],
)
async def test_investigation_put_rejects_malformed_bodies(content: bytes, message: str) -> None:
    async with _client() as client:
        project_id = await _project(client)
        resp = await client.put(
            _url(project_id), content=content, headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["message"] == message


@pytest.mark.asyncio
async def test_investigation_put_rejects_non_analysis_artifact() -> None:
    actor = _actor()
    async with _client() as client:
        project_id = await _project(client)
        binding, draft = await _leased_binding(client, project_id, "firmware", actor)
        resp = await client.put(
            _url(project_id, "firmware"),
            json={
                "investigation": _investigation(),
                "requestedBy": actor,
                **_versions(binding, draft),
            },
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "WORKSPACE_RUNTIME_CAPABILITY_DENIED"


@pytest.mark.asyncio
async def test_investigation_put_unknown_project_is_404() -> None:
    async with _client() as client:
        resp = await client.put(
            _url(f"proj_{secrets.token_hex(8)}"),
            json={
                "investigation": _investigation(),
                "expectedDraftVersion": 1,
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
            },
        )
        assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_investigation_put_stale_draft_version_matches_upload_route() -> None:
    actor = _actor()
    async with _client() as client:
        project_id = await _project(client)
        binding, draft = await _leased_binding(client, project_id, "analysis", actor)
        stale = _versions(binding, draft + 7)
        investigation = await client.put(
            _url(project_id),
            json={"investigation": _investigation(), "requestedBy": actor, **stale},
        )
        upload = await client.post(
            f"/v1/projects/{project_id}/artifacts/analysis/workspace/inputs/upload",
            json={
                "path": "data/x.csv",
                "contentBase64": base64.b64encode(b"t,a\n0,1\n").decode("ascii"),
                "mediaType": "text/csv",
                "requestedBy": actor,
                **stale,
            },
        )
        assert upload.status_code != 200, upload.text
        assert investigation.status_code == upload.status_code, investigation.text
        assert investigation.json()["error"]["code"] == upload.json()["error"]["code"]
