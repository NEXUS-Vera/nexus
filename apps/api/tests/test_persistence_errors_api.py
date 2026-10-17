"""Persistence errors retain their classification at the HTTP boundary."""

from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from nexus_board.ids import new_id
from nexus_persistence import errors


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={
            "Authorization": "Bearer nexus-dev-session-token",
            "x-request-id": "persistence-regression",
        },
    ) as value:
        yield value


@pytest.mark.parametrize(
    ("error_type", "status"),
    [
        (errors.ProjectNotFoundError, 404),
        (errors.ArtifactNotFoundError, 404),
        (errors.ArtifactVersionNotFoundError, 404),
        (errors.WorkspaceNotFoundError, 404),
        (errors.SnapshotNotFoundError, 404),
        (errors.ProposalNotFoundError, 404),
        (errors.ExecutionNotFoundError, 404),
        (errors.FirmwarePatchNotFoundError, 404),
        (errors.ArtifactVersionConflictError, 409),
        (errors.ProjectStateConflictError, 409),
        (errors.SnapshotImmutableError, 409),
        (errors.LedgerImmutableError, 409),
        (errors.ProjectPersistenceError, 500),
        (errors.ProjectRetrievalError, 500),
        (errors.PersistenceError, 500),
    ],
)
async def test_persistence_classification(client, monkeypatch, caplog, error_type, status):
    def fail(*args, **kwargs):
        raise error_type("store failure")

    monkeypatch.setattr(main._kernel.workspace_runtime, "list_files", fail)
    with caplog.at_level(logging.ERROR, logger="nexus.api"):
        response = await client.get(
            f"/v1/projects/{new_id('proj')}/artifacts/analysis/workspace/files"
        )
    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": error_type.code,
            "message": "store failure",
            "requestId": "persistence-regression",
        }
    }
    assert bool(caplog.records) == (status == 500)
    if status == 500:
        assert caplog.records[-1].exc_info


@pytest.mark.parametrize(
    ("method", "suffix", "body", "code"),
    [
        ("GET", "/artifacts/analysis/workspace/files", None, "PROJECT_NOT_FOUND"),
        ("GET", "/artifacts/analysis/workspace/snapshots", None, "PROJECT_NOT_FOUND"),
        ("POST", "/artifacts/analysis/workspace", {}, "PROJECT_NOT_FOUND"),
        ("GET", "/verify/evidence-chain", None, "PROJECT_NOT_FOUND"),
        ("POST", "/verify/promote-execution", {"executionRunId": "missing"}, "EXECUTION_NOT_FOUND"),
        (
            "GET",
            "/artifacts/analysis/workspace/outputs/missing/preview",
            None,
            "EXECUTION_NOT_FOUND",
        ),
        (
            "POST",
            "/artifacts/analysis/workspace/compare-outputs",
            {"baselineExecutionRunId": "missing", "rerunExecutionRunId": "missing"},
            "EXECUTION_NOT_FOUND",
        ),
    ],
)
async def test_real_unknown_ids(client, method, suffix, body, code):
    response = await client.request(method, f"/v1/projects/{new_id('proj')}{suffix}", json=body)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == "persistence-regression"


@pytest.mark.parametrize(
    ("target", "method_name", "method", "suffix", "body", "error_type"),
    [
        (
            "workspaces",
            "create_if_missing",
            "POST",
            "/artifacts/analysis/workspace",
            {},
            errors.ArtifactNotFoundError,
        ),
        (
            None,
            "dispatch",
            "POST",
            "/artifact-commands",
            {"commandId": "cmd_1234567890abcdef", "commandType": "workspace.update-draft"},
            errors.WorkspaceNotFoundError,
        ),
        (
            None,
            "dispatch",
            "POST",
            "/artifact-commands",
            {"commandId": "cmd_1234567890abcdef", "commandType": "artifact.accept-revision"},
            errors.ProposalNotFoundError,
        ),
        (
            None,
            "dispatch",
            "POST",
            "/artifact-commands",
            {"commandId": "cmd_1234567890abcdef", "commandType": "artifact.accept-revision"},
            errors.ArtifactVersionConflictError,
        ),
        (
            "workspace_runtime",
            "restore_snapshot",
            "POST",
            "/artifacts/code-scratch/workspace/snapshots/missing/restore",
            {},
            errors.SnapshotNotFoundError,
        ),
        (
            "verification",
            "evidence_chain",
            "GET",
            "/verify/evidence-chain",
            None,
            errors.ArtifactNotFoundError,
        ),
    ],
)
async def test_route_family_errors(
    client, monkeypatch, target, method_name, method, suffix, body, error_type
):
    initialized = await client.post(
        "/v1/projects/initialize",
        json={
            "message": "Build a greenhouse temperature monitoring node.",
            "autonomyMode": "collaborate",
        },
    )
    assert initialized.status_code == 200, initialized.text
    project_id = initialized.json()["project"]["projectId"]

    def fail(*args, **kwargs):
        raise error_type("missing or conflicting record")

    monkeypatch.setattr(
        getattr(main._kernel, target) if target else main._kernel, method_name, fail
    )
    response = await client.request(method, f"/v1/projects/{project_id}{suffix}", json=body)
    assert response.status_code == (
        409 if error_type is errors.ArtifactVersionConflictError else 404
    ), response.text
    assert response.json() == {
        "error": {
            "code": error_type.code,
            "message": "missing or conflicting record",
            "requestId": "persistence-regression",
        }
    }


@pytest.mark.parametrize(
    "error_type", [errors.ArtifactVersionConflictError, errors.ProjectStateConflictError]
)
async def test_layered_architecture_conflict(client, monkeypatch, error_type):
    from nexus_embedded_systems.workflows import layered_architecture

    project_id = new_id("proj")
    monkeypatch.setattr(main._store, "get_project", lambda *args: {"currentStateVersion": 1})
    monkeypatch.setattr(main._store, "get_artifacts", lambda *args: [])
    monkeypatch.setattr(
        layered_architecture,
        "ensure_layered_architecture_artifacts",
        lambda **kwargs: {"created": [{"createdAt": "2026-10-16T00:00:00Z"}]},
    )

    def fail(**kwargs):
        raise error_type("concurrent update")

    monkeypatch.setattr(main._store, "apply_accepted_artifact_revision", fail)
    response = await client.post(f"/v1/projects/{project_id}/ensure-layered-architecture", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == error_type.code


async def test_unclassified_error_code_does_not_make_it_not_found(client, monkeypatch):
    def fail(*args, **kwargs):
        raise errors.PersistenceError("unclassified", code="UNCLASSIFIED_NOT_FOUND")

    monkeypatch.setattr(main._kernel.workspace_runtime, "list_files", fail)
    response = await client.get(f"/v1/projects/{new_id('proj')}/artifacts/analysis/workspace/files")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "UNCLASSIFIED_NOT_FOUND"


async def test_other_exception_keeps_route_fallback(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(main._store, "get_project", fail)
    response = await client.get(f"/v1/projects/{new_id('proj')}/verify/evidence-chain")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PROJECT_RETRIEVAL_FAILED"


async def test_missing_snapshot_from_real_store(client):
    initialized = await client.post(
        "/v1/projects/initialize",
        json={
            "message": "Build a greenhouse temperature monitoring node.",
            "autonomyMode": "collaborate",
        },
    )
    project_id = initialized.json()["project"]["projectId"]
    response = await client.post(
        f"/v1/projects/{project_id}/artifacts/code-scratch/workspace/snapshots/missing/restore",
        json={},
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "SNAPSHOT_NOT_FOUND"
