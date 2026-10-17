"""A non-integer version/duration field is a 422 naming the field, not a 500.

Routes used to call ``int()`` on client values, so ``"abc"``, ``{}`` or ``[]`` raised
ValueError/TypeError and came back as an unhandled 500. Bools are rejected too:
``True`` is an ``int`` in Python but is never a valid version or duration.
Integer strings and integral floats keep working, as they did with ``int()``.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main

REQUEST_ID = "integer-field-validation"
_VERSIONS = {"expectedDraftVersion": 1, "baseArtifactVersion": 1, "baseProjectStateVersion": 1}
_REQUESTED_BY = {"requestedBy": {"actorId": "actor_test", "actorType": "user"}}


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


# (id, target factory, method name, HTTP method, path suffix, valid body, integer field,
# kernel kwarg that receives it).
_ROUTES = [
    (
        "artifact-file-write",
        _runtime,
        "write_file",
        "PUT",
        "/artifacts/analysis/workspace/file",
        {"path": "data/a.csv", "content": "x", **_VERSIONS},
        "expectedDraftVersion",
        "expected_draft_version",
    ),
    (
        "workspace-file-write",
        _filesystem,
        "write_file",
        "PUT",
        "/workspaces/ws_x/file",
        {"path": "a.txt", "content": "x", **_REQUESTED_BY, **_VERSIONS},
        "baseArtifactVersion",
        "base_artifact_version",
    ),
    (
        "workspace-file-rename",
        _filesystem,
        "rename_file",
        "POST",
        "/workspaces/ws_x/files/rename",
        {"fromPath": "a.txt", "toPath": "b.txt", **_REQUESTED_BY, **_VERSIONS},
        "baseProjectStateVersion",
        "base_project_state_version",
    ),
    (
        "workspace-file-delete",
        _filesystem,
        "delete_file",
        "DELETE",
        "/workspaces/ws_x/file?path=a.txt",
        {**_REQUESTED_BY, **_VERSIONS},
        "expectedDraftVersion",
        "expected_draft_version",
    ),
    (
        "scaffold",
        _runtime,
        "generate_firmware_scaffold",
        "POST",
        "/artifacts/firmware/workspace/scaffold",
        dict(_VERSIONS),
        "baseArtifactVersion",
        "base_artifact_version",
    ),
    (
        "patch-apply",
        _runtime,
        "apply_firmware_patch",
        "POST",
        "/artifacts/firmware/workspace/patch/apply",
        {"proposalId": "prop_x", **_VERSIONS},
        "expectedDraftVersion",
        "expected_draft_version",
    ),
    (
        "input-upload",
        _runtime,
        "write_analysis_input_file",
        "POST",
        "/artifacts/analysis/workspace/inputs/upload",
        {"path": "data/a.csv", "content": "x", **_VERSIONS},
        "baseProjectStateVersion",
        "base_project_state_version",
    ),
    (
        "import-produced-output",
        _runtime,
        "import_produced_output_into_analysis_input",
        "POST",
        "/artifacts/analysis/workspace/inputs/import-produced-output",
        {"outputId": "out_x", "path": "data/a.csv", **_VERSIONS},
        "baseArtifactVersion",
        "base_artifact_version",
    ),
    (
        "execution-start-max-duration",
        _runtime,
        "start_execution",
        "POST",
        "/artifacts/firmware/workspace/executions",
        {"snapshotId": "snap_x", "commandSpec": {"argv": ["true"]}, "maxDurationMs": 1000},
        "maxDurationMs",
        "max_duration_ms",
    ),
    (
        "execution-start-base-version",
        _runtime,
        "start_execution",
        "POST",
        "/artifacts/firmware/workspace/executions",
        {"snapshotId": "snap_x", "commandSpec": {"argv": ["true"]}, "baseArtifactVersion": 1},
        "baseArtifactVersion",
        "base_artifact_version",
    ),
    (
        "execution-start-state-version",
        _runtime,
        "start_execution",
        "POST",
        "/artifacts/firmware/workspace/executions",
        {"snapshotId": "snap_x", "commandSpec": {"argv": ["true"]}, "baseProjectStateVersion": 1},
        "baseProjectStateVersion",
        "base_project_state_version",
    ),
]

# Compile/test/run/rerun read the same three optional integers before the runtime call.
_OPTIONAL_INTEGER_ROUTES = [
    ("compile", "compile_firmware", "/artifacts/firmware/workspace/compile", {}),
    ("test", "test_firmware", "/artifacts/firmware/workspace/test", {}),
    ("run", "run_analysis", "/artifacts/analysis/workspace/run", {}),
    ("rerun", "rerun_analysis", "/artifacts/analysis/workspace/rerun", {"snapshotId": "snap_x"}),
]
_OPTIONAL_INTEGER_FIELDS = [
    ("baseArtifactVersion", "base_artifact_version"),
    ("baseProjectStateVersion", "base_project_state_version"),
    ("maxDurationMs", "max_duration_ms"),
]
_ROUTES += [
    (f"{name}-{field}", _runtime, attr, "POST", suffix, {**body, field: 1}, field, kwarg)
    for name, attr, suffix, body in _OPTIONAL_INTEGER_ROUTES
    for field, kwarg in _OPTIONAL_INTEGER_FIELDS
]
_IDS = [route[0] for route in _ROUTES]
_PARAMS = ("name", "target", "attr", "method", "suffix", "body", "field", "kwarg")

_BAD_VALUES = [
    pytest.param("abc", id="string"),
    pytest.param("1.5", id="decimal-string"),
    pytest.param({}, id="object"),
    pytest.param([1], id="list"),
    pytest.param(True, id="bool"),
    pytest.param(1.5, id="fraction"),
]


def _patch(monkeypatch, project_id, target, attr, *, raises: BaseException | None = None):
    calls: list[dict] = []

    def reached(*args, **kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return {"ok": True}

    # Workspace-scoped routes look the workspace up before reading the body.
    monkeypatch.setattr(
        main._kernel.kernel_store,
        "get_workspace",
        lambda *args, **kwargs: {"projectId": project_id},
    )
    monkeypatch.setattr(target(), attr, reached)
    return calls


@pytest.mark.parametrize("bad", _BAD_VALUES)
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_non_integer_field_is_a_422_naming_the_field(
    client, project_id, monkeypatch, name, target, attr, method, suffix, body, field, kwarg, bad
):
    calls = _patch(monkeypatch, project_id, target, attr, raises=AssertionError("not reached"))
    response = await client.request(
        method, f"/v1/projects/{project_id}{suffix}", json={**body, field: bad}
    )
    assert response.status_code == 422, response.text
    assert response.json() == {
        "error": {
            "code": "COMMAND_VALIDATION_FAILED",
            "message": f"{field} must be an integer.",
            "requestId": REQUEST_ID,
        }
    }
    assert calls == []


@pytest.mark.parametrize(
    ("good", "expected"),
    [
        pytest.param(3, 3, id="int"),
        pytest.param("3", 3, id="int-string"),
        pytest.param(3.0, 3, id="integral-float"),
    ],
)
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_integer_like_values_still_reach_the_kernel_as_int(
    server_error_client,
    project_id,
    monkeypatch,
    name,
    target,
    attr,
    method,
    suffix,
    body,
    field,
    kwarg,
    good,
    expected,
):
    calls = _patch(monkeypatch, project_id, target, attr)
    # The stub result is not a full kernel payload, so routes that read it may 500;
    # only the converted kwarg matters here.
    response = await server_error_client.request(
        method, f"/v1/projects/{project_id}{suffix}", json={**body, field: good}
    )
    assert len(calls) == 1, response.text
    value = calls[0][kwarg]
    assert value == expected and type(value) is int


@pytest.mark.parametrize("absent", [pytest.param(None, id="null"), pytest.param(..., id="missing")])
async def test_optional_execution_integers_may_be_null_or_absent(
    client, project_id, monkeypatch, absent
):
    calls = _patch(monkeypatch, project_id, _runtime, "start_execution")
    body = {"snapshotId": "snap_x", "commandSpec": {"argv": ["true"]}}
    if absent is None:
        body.update(baseArtifactVersion=None, baseProjectStateVersion=None, maxDurationMs=None)
    response = await client.post(
        f"/v1/projects/{project_id}/artifacts/firmware/workspace/executions", json=body
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0]["base_artifact_version"] is None
    assert calls[0]["base_project_state_version"] is None
    assert calls[0]["max_duration_ms"] is None


@pytest.mark.parametrize("absent", [pytest.param(None, id="null"), pytest.param(..., id="missing")])
@pytest.mark.parametrize(
    ("name", "attr", "suffix", "body"),
    _OPTIONAL_INTEGER_ROUTES,
    ids=[route[0] for route in _OPTIONAL_INTEGER_ROUTES],
)
async def test_optional_workspace_run_integers_may_be_null_or_absent(
    client, project_id, monkeypatch, name, attr, suffix, body, absent
):
    calls = _patch(monkeypatch, project_id, _runtime, attr)
    body = dict(body)
    if absent is None:
        body.update({field: None for field, _ in _OPTIONAL_INTEGER_FIELDS})
    response = await client.post(f"/v1/projects/{project_id}{suffix}", json=body)
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    for _, kwarg in _OPTIONAL_INTEGER_FIELDS:
        assert calls[0][kwarg] is None


@pytest.mark.parametrize("error", [ValueError("boom"), TypeError("boom")], ids=["value", "type"])
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_kernel_value_or_type_error_is_still_a_500(
    server_error_client,
    project_id,
    monkeypatch,
    name,
    target,
    attr,
    method,
    suffix,
    body,
    field,
    kwarg,
    error,
):
    calls = _patch(monkeypatch, project_id, target, attr, raises=error)
    response = await server_error_client.request(
        method, f"/v1/projects/{project_id}{suffix}", json=body
    )
    assert len(calls) == 1, response.text
    assert response.status_code == 500, response.text
    assert "must be an integer" not in response.text
