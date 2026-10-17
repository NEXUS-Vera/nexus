"""Only a missing request-body field is a 422; a KeyError from the runtime is a 500.

These routes used to wrap the whole kernel/runtime call in ``except KeyError``, so a
KeyError from a bug deep inside the runtime came back to the client as
``422 Missing required field: <internal key>``.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main

REQUEST_ID = "missing-field-keyerror"
_VERSIONS = {"expectedDraftVersion": 1, "baseArtifactVersion": 1, "baseProjectStateVersion": 1}


def _client(*, raise_app_exceptions: bool) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=main.app, raise_app_exceptions=raise_app_exceptions),
        base_url="http://test",
        headers={
            "Authorization": "Bearer nexus-dev-session-token",
            "x-request-id": REQUEST_ID,
        },
    )


@pytest.fixture
async def client():
    async with _client(raise_app_exceptions=True) as value:
        yield value


@pytest.fixture
async def server_error_client():
    async with _client(raise_app_exceptions=False) as value:
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


def _runtime():
    return main._kernel.workspace_runtime


def _filesystem():
    return main._kernel.filesystem


_REQUESTED_BY = {"requestedBy": {"actorId": "actor_test", "actorType": "user"}}

# (id, target factory, method name, HTTP method, path suffix, valid body, required field
# that the route reads from the body, or None when the route has no such field).
_ROUTES = [
    (
        "artifact-file-write",
        _runtime,
        "write_file",
        "PUT",
        "/artifacts/analysis/workspace/file",
        {"path": "data/a.csv", "content": "x", **_VERSIONS},
        "expectedDraftVersion",
    ),
    (
        "execution-start",
        _runtime,
        "start_execution",
        "POST",
        "/artifacts/firmware/workspace/executions",
        {"snapshotId": "snap_x", "commandSpec": {"argv": ["true"]}},
        "commandSpec",
    ),
    (
        "workspace-file-write",
        _filesystem,
        "write_file",
        "PUT",
        "/workspaces/ws_x/file",
        {"path": "a.txt", "content": "x", **_REQUESTED_BY, **_VERSIONS},
        "requestedBy",
    ),
    (
        "workspace-file-rename",
        _filesystem,
        "rename_file",
        "POST",
        "/workspaces/ws_x/files/rename",
        {"fromPath": "a.txt", "toPath": "b.txt", **_REQUESTED_BY, **_VERSIONS},
        "baseArtifactVersion",
    ),
    (
        "workspace-file-delete",
        _filesystem,
        "delete_file",
        "DELETE",
        "/workspaces/ws_x/file?path=a.txt",
        {**_REQUESTED_BY, **_VERSIONS},
        "baseProjectStateVersion",
    ),
    (
        "scaffold",
        _runtime,
        "generate_firmware_scaffold",
        "POST",
        "/artifacts/firmware/workspace/scaffold",
        dict(_VERSIONS),
        "expectedDraftVersion",
    ),
    (
        "patch-propose",
        _runtime,
        "propose_firmware_patch",
        "POST",
        "/artifacts/firmware/workspace/patch/propose",
        {"requestedChange": "Blink faster."},
        None,
    ),
    (
        "patch-apply",
        _runtime,
        "apply_firmware_patch",
        "POST",
        "/artifacts/firmware/workspace/patch/apply",
        {"proposalId": "prop_x", **_VERSIONS},
        "proposalId",
    ),
    (
        "patch-discard",
        _runtime,
        "discard_firmware_patch",
        "POST",
        "/artifacts/firmware/workspace/patch/discard",
        {"proposalId": "prop_x"},
        "proposalId",
    ),
    (
        "input-upload",
        _runtime,
        "write_analysis_input_file",
        "POST",
        "/artifacts/analysis/workspace/inputs/upload",
        {"path": "data/a.csv", "content": "x", **_VERSIONS},
        "path",
    ),
    (
        "import-produced-output",
        _runtime,
        "import_produced_output_into_analysis_input",
        "POST",
        "/artifacts/analysis/workspace/inputs/import-produced-output",
        {"outputId": "out_x", "path": "data/a.csv", **_VERSIONS},
        "outputId",
    ),
    (
        "rerun",
        _runtime,
        "rerun_analysis",
        "POST",
        "/artifacts/analysis/workspace/rerun",
        {"snapshotId": "snap_x"},
        "snapshotId",
    ),
    (
        "compare-outputs",
        _runtime,
        "compare_analysis_run_outputs",
        "POST",
        "/artifacts/analysis/workspace/compare-outputs",
        {"baselineExecutionRunId": "run_a", "rerunExecutionRunId": "run_b"},
        "rerunExecutionRunId",
    ),
]
_IDS = [route[0] for route in _ROUTES]


def _patch(monkeypatch, project_id, target, attr, *, raises: BaseException):
    calls: list[dict] = []

    def reached(*args, **kwargs):
        calls.append(kwargs)
        raise raises

    # Workspace-scoped routes look the workspace up before reading the body.
    monkeypatch.setattr(
        main._kernel.kernel_store,
        "get_workspace",
        lambda *args, **kwargs: {"projectId": project_id},
    )
    monkeypatch.setattr(target(), attr, reached)
    return calls


@pytest.mark.parametrize(
    ("name", "target", "attr", "method", "suffix", "body", "field"), _ROUTES, ids=_IDS
)
async def test_internal_keyerror_is_a_500_not_a_missing_field(
    server_error_client, project_id, monkeypatch, name, target, attr, method, suffix, body, field
):
    calls = _patch(monkeypatch, project_id, target, attr, raises=KeyError("internalKey"))
    response = await server_error_client.request(
        method, f"/v1/projects/{project_id}{suffix}", json=body
    )
    assert len(calls) == 1, response.text
    assert response.status_code == 500, response.text
    assert "Missing required field" not in response.text


_FIELD_ROUTES = [route for route in _ROUTES if route[6] is not None]


@pytest.mark.parametrize(
    ("name", "target", "attr", "method", "suffix", "body", "field"),
    _FIELD_ROUTES,
    ids=[route[0] for route in _FIELD_ROUTES],
)
async def test_missing_required_field_is_still_a_422(
    client, project_id, monkeypatch, name, target, attr, method, suffix, body, field
):
    calls = _patch(monkeypatch, project_id, target, attr, raises=AssertionError("not reached"))
    without_field = {key: value for key, value in body.items() if key != field}
    response = await client.request(
        method, f"/v1/projects/{project_id}{suffix}", json=without_field
    )
    assert response.status_code == 422, response.text
    assert response.json() == {
        "error": {
            "code": "COMMAND_VALIDATION_FAILED",
            "message": f"Missing required field: {field}",
            "requestId": REQUEST_ID,
        }
    }
    assert calls == []
