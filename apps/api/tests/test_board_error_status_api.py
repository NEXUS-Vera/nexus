"""Board-layer NOT_FOUND errors map to 404 on every route that catches BoardError."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from nexus_board import errors as board_errors


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={
            "Authorization": "Bearer nexus-dev-session-token",
            "x-request-id": "board-error-status",
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


# (patch target factory, attribute, method, path suffix, body)
_ROUTES = [
    (lambda: main._kernel.workspaces, "get_or_none", "GET", "/artifacts/analysis/workspace", None),
    (
        lambda: main._kernel.workspaces,
        "create_if_missing",
        "POST",
        "/artifacts/analysis/workspace",
        {},
    ),
    (
        lambda: main._kernel,
        "dispatch",
        "POST",
        "/artifact-commands",
        {"commandId": "cmd_1234567890abcdef", "commandType": "workspace.update-draft"},
    ),
    (lambda: main._kernel_store, "list_graph_nodes", "GET", "/graph", None),
    (lambda: main._kernel.executions, "list_logs", "GET", "/executions/run_x/logs", None),
    (lambda: main._kernel.executions, "cancel", "POST", "/executions/run_x/cancel", {}),
]


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (board_errors.WorkspaceNotFoundError("missing record"), 404),
        (board_errors.BoardError("missing record", code="GRAPH_NODE_NOT_FOUND"), 404),
        (board_errors.CommandValidationError("missing record"), 422),
    ],
)
@pytest.mark.parametrize(("target", "attr", "method", "suffix", "body"), _ROUTES)
async def test_board_error_status(
    client, project_id, monkeypatch, target, attr, method, suffix, body, error, status
):
    def fail(*args, **kwargs):
        raise error

    executions = main._kernel.executions
    monkeypatch.setattr(executions, "get_run", lambda *args, **kwargs: {"projectId": project_id})
    monkeypatch.setattr(target(), attr, fail)
    response = await client.request(method, f"/v1/projects/{project_id}{suffix}", json=body)
    assert response.status_code == status, response.text
    assert response.json() == {
        "error": {
            "code": error.code,
            "message": "missing record",
            "requestId": "board-error-status",
        }
    }
