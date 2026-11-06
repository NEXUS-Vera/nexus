"""HTTP re-verification uses retained evidence and accepted server revisions."""

from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator
from nexus_api import main
from nexus_board.ids import utc_now_iso
from nexus_contracts.validation.schema_validator import (
    load_schemas_by_id,
    validate_against_schema_id,
)
from referencing import Registry, Resource
from test_m5_invalidation import _change_requirement
from test_phase17f_verify_e2e import _seed, _seed_run_inputs

REQUEST_SCHEMA = "https://nexus.local/schemas/executions/project-verify-request.v1.schema.json"
RESULT_SCHEMA = "https://nexus.local/schemas/responses/project-verify-result.v1.schema.json"


def _validate_result(payload: Any) -> None:
    schemas = load_schemas_by_id()
    registry = Registry().with_resources(
        (key, Resource.from_contents(schema)) for key, schema in schemas.items()
    )
    Draft202012Validator(schemas[RESULT_SCHEMA], registry=registry).validate(payload)


def _run(kernel: Any, pid: str, run_id: str, *, mode: str = "real") -> None:
    existing = kernel.kernel_store.list_execution_runs(pid)[0]
    provenance = (
        {
            k: existing[0][k]
            for k in ("workspaceId", "artifactId", "baseArtifactVersion", "inputSnapshotId")
        }
        if existing
        else _seed_run_inputs(kernel, pid)
    )
    outputs: list[str] = []
    for name, text in [
        ("outputs/summary.json", json.dumps({"accel_x_rms_noise_g": 0.0157})),
        ("outputs/processed.csv", "t,x\n0,0.01\n"),
        ("outputs/accel_plot.png", "png"),
    ]:
        oid = f"out_{run_id}_{len(outputs)}"
        kernel.kernel_store.create_produced_output(
            {
                "schemaVersion": "1.0.0",
                "outputId": oid,
                "projectId": pid,
                "executionRunId": run_id,
                "name": name,
                "outputType": "file",
                "content": {"kind": "inline-structured", "structuredResult": {"text": text}},
                "createdAt": utc_now_iso(),
            }
        )
        outputs.append(oid)
    job_id = f"execjob_{run_id}"
    run = {
        "schemaVersion": "1.0.0",
        "executionRunId": run_id,
        "projectId": pid,
        **provenance,
        "artifactType": "analysis",
        "status": "failed" if mode == "failed" else "completed",
        "createdAt": utc_now_iso(),
        "outputReferences": outputs,
        "executionJobId": job_id,
        "runtimeIdentity": {"runtimeKind": "process"},
    }
    kernel.kernel_store.create_execution_run(run)
    kernel.kernel_store.create_execution_job(
        {
            "executionJobId": job_id,
            "executionRunId": run_id,
            "projectId": pid,
            "status": "succeeded",
            "logTruncated": mode == "truncated",
            "commandSpec": {
                "executable": "python3",
                "arguments": ["analysis_stub.py" if mode == "fixture" else "analysis.py"],
            },
        }
    )
    kernel.invalidation.record_run(run)


@pytest.fixture
async def context(monkeypatch: pytest.MonkeyPatch) -> Any:
    kernel, projects, pid, user = _seed()
    monkeypatch.setattr(main, "_kernel", kernel)
    monkeypatch.setattr(main, "_store", projects)
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        yield kernel, projects, pid, user, client
    kernel.jobs.shutdown()


async def test_stale_to_current_via_fresh_promotion(context: Any) -> None:
    kernel, projects, pid, user, client = context
    url = f"/v1/projects/{pid}/verify"
    body = {"requireReal": True, "requestedBy": user}
    assert not validate_against_schema_id(body, REQUEST_SCHEMA)
    _run(kernel, pid, "exec_original")
    response = await client.post(url, json=body)
    assert response.status_code == 200, response.text
    _validate_result(response.json())
    _change_requirement(kernel, pid)
    before = projects.get_artifact(pid, "test-plan")
    case = next(c for c in before["content"]["testCases"] if c["displayId"] == "T7")
    assert case["applicability"]["state"] == "STALE"
    stale = await client.post(url, json={**body, "executionRunId": "exec_original"})
    assert stale.status_code == 422, stale.text
    assert projects.get_artifact(pid, "test-plan") == before
    _run(kernel, pid, "exec_fresh")
    _run(kernel, pid, "exec_newer_fixture", mode="fixture")
    response = await client.post(url, json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    _validate_result(payload)
    assert payload["executionRunId"] == "exec_fresh"
    after = projects.get_artifact(pid, "test-plan")
    assert payload["artifact"] == after
    assert payload["testPlanVersion"] == after["artifactVersion"] > before["artifactVersion"]
    case = next(c for c in after["content"]["testCases"] if c["displayId"] == "T7")
    assert case["applicability"]["state"] == "CURRENT"
    assert case["assessment"] == "PASS"
    assert case["verificationBasis"]["executionRunId"] == "exec_fresh"
    read = await client.get(
        f"/v1/projects/{pid}/artifacts/test-plan?version={after['artifactVersion']}"
    )
    assert read.status_code == 200
    assert read.json() == after
    repeated = await client.post(url, json={**body, "executionRunId": "exec_fresh"})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["artifact"] == after
    assert projects.get_artifact(pid, "test-plan") == after


@pytest.mark.parametrize(
    "field,value",
    [
        ("requireReal", False),
        ("requireReal", "true"),
        ("requireReal", 1),
        ("requireReal", None),
        ("requestedBy", None),
        (
            "requestedBy",
            {"schemaVersion": "1.0.0", "actorId": "actor_invalid", "actorType": "user"},
        ),
        (
            "requestedBy",
            {"schemaVersion": "1.0.0", "actorId": "actor_0000000000000000", "actorType": "system"},
        ),
        ("schemaVersion", "2.0.0"),
    ],
)
async def test_invalid_contract_does_not_mutate(context: Any, field: str, value: Any) -> None:
    kernel, projects, pid, user, client = context
    _run(kernel, pid, "exec_valid")
    before = projects.get_artifact(pid, "test-plan")
    body = {"requireReal": True, "requestedBy": user}
    if value is None:
        body.pop(field, None)
    else:
        body[field] = value
    assert validate_against_schema_id(body, REQUEST_SCHEMA)
    response = await client.post(f"/v1/projects/{pid}/verify", json=body)
    assert response.status_code == 422, response.text
    assert projects.get_artifact(pid, "test-plan") == before


@pytest.mark.parametrize(
    "mode", ["missing", "unknown", "failed", "fixture", "truncated", "foreign"]
)
async def test_unusable_evidence_does_not_mutate(context: Any, mode: str) -> None:
    kernel, projects, pid, user, client = context
    body = {"requireReal": True, "requestedBy": user}
    if mode != "missing":
        body["executionRunId"] = "exec_candidate"
        if mode != "unknown":
            _run(kernel, pid, "exec_candidate", mode=mode)
            if mode == "foreign":
                run = kernel.kernel_store.get_execution_run("exec_candidate")
                run["projectId"] = "proj_FOREIGN"
                kernel.kernel_store.update_execution_status("exec_candidate", run)
    before = projects.get_artifact(pid, "test-plan")
    response = await client.post(f"/v1/projects/{pid}/verify", json=body)
    assert response.status_code == (404 if mode == "unknown" else 422), response.text
    assert projects.get_artifact(pid, "test-plan") == before
    if mode != "unknown":
        assert "Rerun compile/simulation/analysis" in response.text


async def test_session_required(context: Any) -> None:
    _, _, pid, user, client = context
    response = await client.post(
        f"/v1/projects/{pid}/verify",
        headers={"Authorization": ""},
        json={"requireReal": True, "requestedBy": user},
    )
    assert response.status_code == 401


async def test_consumed_fixture_evidence_is_rejected(context: Any) -> None:
    kernel, projects, pid, user, client = context
    _run(kernel, pid, "exec_fixture", mode="fixture")
    _run(kernel, pid, "exec_consumer")
    run = kernel.kernel_store.get_execution_run("exec_consumer")
    run["inputOutputReferences"] = ["out_exec_fixture_0"]
    kernel.kernel_store.update_execution_status("exec_consumer", run)
    before = projects.get_artifact(pid, "test-plan")
    response = await client.post(
        f"/v1/projects/{pid}/verify",
        json={
            "requireReal": True,
            "requestedBy": user,
            "executionRunId": "exec_consumer",
        },
    )
    assert response.status_code == 422, response.text
    assert projects.get_artifact(pid, "test-plan") == before
