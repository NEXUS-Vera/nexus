"""Routes with an optional JSON body reject malformed JSON instead of defaulting to {}."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from nexus_board.errors import BoardError
from nexus_embedded_systems.workflows import layered_architecture

REQUEST_ID = "malformed-json-body"
_VERSIONS = "expectedDraftVersion=1&baseArtifactVersion=1&baseProjectStateVersion=1"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={
            "Authorization": "Bearer nexus-dev-session-token",
            "x-request-id": REQUEST_ID,
        },
    ) as value:
        yield value


@pytest.fixture
async def project_id(client):
    initialized = await client.post(
        "/v1/projects/initialize",
        json={
            "message": "Build a greenhouse temperature monitoring node.",
            "autonomyMode": "collaborate",
        },
    )
    assert initialized.status_code == 200, initialized.text
    return initialized.json()["project"]["projectId"]


# (patch target factory, attribute, method, path suffix). The patched callable is the
# first thing each route does with the parsed body.
_ROUTES = [
    (
        lambda: layered_architecture,
        "ensure_layered_architecture_artifacts",
        "POST",
        "/ensure-layered-architecture",
    ),
    (lambda: main._kernel.workspaces, "create_if_missing", "POST", "/artifacts/analysis/workspace"),
    (
        lambda: main._kernel.workspace_runtime,
        "delete_file",
        "DELETE",
        f"/artifacts/analysis/workspace/file?path=data/a.csv&{_VERSIONS}",
    ),
    (
        lambda: main._kernel.workspace_runtime,
        "create_firmware_snapshot",
        "POST",
        "/artifacts/firmware/workspace/snapshots",
    ),
    (
        lambda: main._kernel.workspace_runtime,
        "restore_firmware_snapshot",
        "POST",
        "/artifacts/firmware/workspace/snapshots/snap_x/restore",
    ),
    (
        lambda: main._kernel.kernel_store,
        "get_workspace",
        "DELETE",
        "/workspaces/ws_x/file?path=a.txt",
    ),
    (lambda: main._kernel.executions, "cancel", "POST", "/executions/run_x/cancel"),
    (
        lambda: main._kernel.workspace_runtime,
        "compile_firmware",
        "POST",
        "/artifacts/firmware/workspace/compile",
    ),
    (
        lambda: main._kernel.workspace_runtime,
        "test_firmware",
        "POST",
        "/artifacts/firmware/workspace/test",
    ),
    (
        lambda: main._kernel.workspace_runtime,
        "run_analysis",
        "POST",
        "/artifacts/analysis/workspace/run",
    ),
]


def _spy(monkeypatch, project_id, target, attr):
    calls: list[dict] = []

    def reached(*args, **kwargs):
        calls.append(kwargs)
        if attr == "ensure_layered_architecture_artifacts":
            return {"skippedReason": "test sentinel"}
        raise BoardError("test sentinel", code="TEST_SENTINEL")

    monkeypatch.setattr(
        main._kernel.executions, "get_run", lambda *args, **kwargs: {"projectId": project_id}
    )
    monkeypatch.setattr(target(), attr, reached)
    return calls


@pytest.mark.parametrize(
    "content",
    [b"{not json", b'{"reason": "x",}', b"\xff\xfe\x00garbage"],
    ids=["broken", "trailing-comma", "invalid-utf8"],
)
@pytest.mark.parametrize(("target", "attr", "method", "suffix"), _ROUTES)
async def test_malformed_json_body_is_rejected(
    client, project_id, monkeypatch, target, attr, method, suffix, content
):
    calls = _spy(monkeypatch, project_id, target, attr)
    response = await client.request(
        method,
        f"/v1/projects/{project_id}{suffix}",
        content=content,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert response.json() == {
        "error": {
            "code": "COMMAND_VALIDATION_FAILED",
            "message": "Invalid JSON body.",
            "requestId": REQUEST_ID,
        }
    }
    assert calls == []


@pytest.mark.parametrize("content", [b"", b"  \n\t "], ids=["empty", "whitespace"])
@pytest.mark.parametrize(("target", "attr", "method", "suffix"), _ROUTES)
async def test_empty_body_still_means_defaults(
    client, project_id, monkeypatch, target, attr, method, suffix, content
):
    calls = _spy(monkeypatch, project_id, target, attr)
    response = await client.request(method, f"/v1/projects/{project_id}{suffix}", content=content)
    assert len(calls) == 1, response.text
    assert response.json()["error"]["message"] != "Invalid JSON body."


async def test_valid_json_body_is_still_used(client, project_id, monkeypatch):
    calls = _spy(monkeypatch, project_id, lambda: main._kernel.workspace_runtime, "create_snapshot")
    response = await client.post(
        f"/v1/projects/{project_id}/artifacts/analysis/workspace/snapshots",
        json={"reason": "before refactor"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "TEST_SENTINEL"
    assert calls[0]["reason"] == "before refactor"
