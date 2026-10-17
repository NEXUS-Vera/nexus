"""A non-string optional text field is a 422 naming the field, not a 500.

The firmware snapshot route passed ``reason`` straight to the runtime, which called
``.strip()`` on it, and the scaffold routes passed ``profileId`` to a dict lookup,
so ``7``, ``[1]`` or ``{}`` came back as an unhandled 500 (or, for other artifact
types, a non-string reason was stored as-is). Strings and null/absent are unchanged.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main

REQUEST_ID = "string-field-validation"
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


# (id, runtime method, path suffix, valid body, string field, kernel kwarg that receives it).
_ROUTES = [
    (
        "firmware-snapshot",
        "create_firmware_snapshot",
        "/artifacts/firmware/workspace/snapshots",
        {},
        "reason",
        "reason",
    ),
    (
        "analysis-snapshot",
        "create_snapshot",
        "/artifacts/analysis/workspace/snapshots",
        {},
        "reason",
        "reason",
    ),
    (
        "firmware-scaffold",
        "generate_firmware_scaffold",
        "/artifacts/firmware/workspace/scaffold",
        dict(_VERSIONS),
        "profileId",
        "profile_id",
    ),
    (
        "analysis-scaffold",
        "generate_analysis_scaffold",
        "/artifacts/analysis/workspace/scaffold",
        dict(_VERSIONS),
        "profileId",
        "profile_id",
    ),
]
_IDS = [route[0] for route in _ROUTES]
_PARAMS = ("name", "attr", "suffix", "body", "field", "kwarg")

_BAD_VALUES = [
    pytest.param(7, id="int"),
    pytest.param(1.5, id="float"),
    pytest.param(True, id="bool"),
    pytest.param([1], id="list"),
    pytest.param({}, id="empty-object"),
    pytest.param({"a": 1}, id="object"),
]


def _patch(monkeypatch, attr, *, raises: BaseException | None = None):
    calls: list[dict] = []

    def reached(*args, **kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return {"status": "ok"}

    monkeypatch.setattr(main._kernel.workspace_runtime, attr, reached)
    return calls


@pytest.mark.parametrize("bad", _BAD_VALUES)
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_non_string_field_is_a_422_naming_the_field(
    client, project_id, monkeypatch, name, attr, suffix, body, field, kwarg, bad
):
    calls = _patch(monkeypatch, attr, raises=AssertionError("not reached"))
    response = await client.post(f"/v1/projects/{project_id}{suffix}", json={**body, field: bad})
    assert response.status_code == 422, response.text
    assert response.json() == {
        "error": {
            "code": "COMMAND_VALIDATION_FAILED",
            "message": f"{field} must be a string.",
            "requestId": REQUEST_ID,
        }
    }
    assert calls == []


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("manual-checkpoint", id="string"),
        pytest.param("", id="empty-string"),
        pytest.param(None, id="null"),
        pytest.param(..., id="missing"),
    ],
)
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_strings_and_null_still_reach_the_kernel_unchanged(
    client, project_id, monkeypatch, name, attr, suffix, body, field, kwarg, value
):
    calls = _patch(monkeypatch, attr)
    payload = dict(body) if value is ... else {**body, field: value}
    response = await client.post(f"/v1/projects/{project_id}{suffix}", json=payload)
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0][kwarg] == (None if value is ... else value)


@pytest.mark.parametrize("error", [ValueError("boom"), TypeError("boom")], ids=["value", "type"])
@pytest.mark.parametrize(_PARAMS, _ROUTES, ids=_IDS)
async def test_kernel_value_or_type_error_is_still_a_500(
    server_error_client, project_id, monkeypatch, name, attr, suffix, body, field, kwarg, error
):
    calls = _patch(monkeypatch, attr, raises=error)
    response = await server_error_client.post(
        f"/v1/projects/{project_id}{suffix}", json={**body, field: "ok"}
    )
    assert len(calls) == 1, response.text
    assert response.status_code == 500, response.text
    assert "must be a string" not in response.text


async def test_real_firmware_snapshot_with_numeric_reason_is_a_422_not_a_500(
    server_error_client, project_id
):
    # No stub: this used to raise AttributeError ('int' has no attribute 'strip').
    response = await server_error_client.post(
        f"/v1/projects/{project_id}/artifacts/firmware/workspace/snapshots", json={"reason": 7}
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message"] == "reason must be a string."
