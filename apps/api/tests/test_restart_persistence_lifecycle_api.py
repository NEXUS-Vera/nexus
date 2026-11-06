"""Offline HTTP restart regression: stub compiler and real fixture-backed analysis."""

import hashlib
import importlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from test_golden_lifecycle_http_api import (
    AUTH,
    GOLDEN_DIR,
    _actor,
    _wait_run,
    run_golden_lifecycle_over_http,
)
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401


async def _get(client: AsyncClient, route: str) -> dict[str, Any]:
    response = await client.get(route)
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


async def _capture(client: AsyncClient, prefix: str) -> dict[str, Any]:
    """Capture identities, versions, links, hashes and file content through HTTP."""
    routes = ["", "/artifacts", "/verify/evidence-chain", "/outputs", "/executions"]
    for kind in ("firmware", "analysis"):
        root = f"/artifacts/{kind}/workspace"
        routes.extend([f"{root}/runtime", f"{root}/files", f"{root}/snapshots"])
    captured = {route: await _get(client, prefix + route) for route in routes}
    outputs = captured["/outputs"]["items"]
    assert outputs
    for output in outputs:
        oid = output["outputId"]
        routes.append(f"/outputs/{oid}")
        routes.append(f"/artifacts/analysis/workspace/outputs/{oid}/preview")
        routes.append(f"/executions/{output['executionRunId']}")
    for kind in ("firmware", "analysis"):
        root = f"/artifacts/{kind}/workspace"
        files = captured[f"{root}/files"]["files"]
        assert files
        for file in files:
            routes.append(f"{root}/file?path={file['path']}")
        snapshots = captured[f"{root}/snapshots"]["snapshots"]
        assert snapshots
        # Capture the actual immutable inputs of every produced-output run.
        for rid in {o["executionRunId"] for o in outputs}:
            run = (await _get(client, f"{prefix}/executions/{rid}"))["executionRun"]
            if run["artifactId"] != captured[f"{root}/runtime"]["binding"]["artifactId"]:
                continue
            assert run["status"] == "completed", run
            assert set(run["outputReferences"]) == {
                o["outputId"] for o in outputs if o["executionRunId"] == rid
            }
            assert run["inputSnapshotId"] in {s["snapshotId"] for s in snapshots}
            for file in files:
                routes.append(f"{root}/snapshots/{run['inputSnapshotId']}/file?path={file['path']}")
    for route in dict.fromkeys(routes):
        if route not in captured:
            captured[route] = await _get(client, prefix + route)
    summary = next(o for o in outputs if o["name"] == "outputs/summary.json")
    preview = captured[f"/artifacts/analysis/workspace/outputs/{summary['outputId']}/preview"]
    assert not preview["truncated"]
    assert (
        json.loads(preview["text"])["inputSha256"]
        == hashlib.sha256((GOLDEN_DIR / "stationary_imu.csv").read_bytes()).hexdigest()
    )
    chain = captured["/verify/evidence-chain"]["chains"]
    verified = next(c for c in chain if c["requirementId"] == "R7")
    assert verified["assessment"] == "PASS"
    assert verified["executionRunId"] == summary["executionRunId"]
    assert verified["evidenceReferences"]
    return captured


@pytest.mark.asyncio
@pytest.mark.usefixtures("ticking_http_loop")
async def test_http_restart_preserves_lifecycle_and_accepts_follow_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = main.settings
    monkeypatch.setattr(
        "nexus_api.config.settings",
        replace(
            original,
            storage_backend="sqlite",
            database_url=f"sqlite:///{tmp_path / 'restart.db'}",
            file_store_root=str(tmp_path / "files"),
        ),
    )
    try:
        importlib.reload(main)
        app_a, kernel_a = main.app, main._kernel
        # Existing HTTP golden harness initializes, edits/scaffolds firmware,
        # compiles, runs analysis and promotes linked evidence into the Test Plan.
        pid = await run_golden_lifecycle_over_http(monkeypatch)
        prefix = f"/v1/projects/{pid}"
        async with AsyncClient(
            transport=ASGITransport(app=app_a), base_url="http://test", headers=AUTH
        ) as client_a:
            before = await _capture(client_a, prefix)
        stored_bytes = {
            str(p.relative_to(tmp_path / "files")): p.read_bytes()
            for p in (tmp_path / "files").rglob("*")
            if p.is_file()
        }
        assert stored_bytes
        kernel_a.jobs.shutdown()
        importlib.reload(main)
        assert main.app is not app_a
        assert main._kernel is not kernel_a
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=AUTH
        ) as client_b:
            assert await _capture(client_b, prefix) == before
            assert {
                str(p.relative_to(tmp_path / "files")): p.read_bytes()
                for p in (tmp_path / "files").rglob("*")
                if p.is_file()
            } == stored_bytes
            lease = before["/artifacts/firmware/workspace/runtime"]["draft"]["editLease"]
            actor = _actor()
            actor.update(actorId=lease["ownerActorId"], actorType=lease["ownerActorType"])
            started = await client_b.post(
                f"{prefix}/artifacts/firmware/workspace/compile",
                json={"requestedBy": actor},
            )
            assert started.status_code == 200, started.text
            run_id = started.json()["executionRun"]["executionRunId"]
            assert run_id not in {o["executionRunId"] for o in before["/outputs"]["items"]}
            run = await _wait_run(client_b, pid, run_id)
            assert run["status"] == "completed", run
            outputs = (await _get(client_b, prefix + "/outputs"))["items"]
            new_outputs = [o for o in outputs if o["executionRunId"] == run_id]
            assert new_outputs
            assert set(run["outputReferences"]) == {o["outputId"] for o in new_outputs}
            snapshots = await _get(client_b, prefix + "/artifacts/firmware/workspace/snapshots")
            assert run["inputSnapshotId"] in {s["snapshotId"] for s in snapshots["snapshots"]}
            # A new run may add evidence; historical records and links stay intact.
            for route, payload in before.items():
                if route.startswith("/outputs/") or route.startswith("/executions/"):
                    assert await _get(client_b, prefix + route) == payload
            assert (
                await _get(client_b, prefix + "/verify/evidence-chain")
                == before["/verify/evidence-chain"]
            )
    finally:
        main._kernel.jobs.shutdown()
        monkeypatch.setattr("nexus_api.config.settings", original)
        importlib.reload(main)
