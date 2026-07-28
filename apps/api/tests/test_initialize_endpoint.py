from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

PROMPTS = {
    "indoor-environmental-rover": (
        "I want to build a small indoor rover that drives around a room and maps "
        "temperature, humidity, and air quality."
    ),
    "wearable-tremor-monitor": (
        "I want to build a wrist-worn device that measures hand tremors "
        "and records the motion data for later analysis."
    ),
    "greenhouse-sensing-node": (
        "I want to build a greenhouse monitoring node that measures temperature, "
        "humidity, soil moisture, and light, and reports the readings remotely."
    ),
    "vibration-monitoring-device": (
        "I want to build a device that attaches to a machine and records vibration "
        "so I can detect changes in how the machine is operating."
    ),
    "robot-obstacle-detection-module": (
        "I want to build an obstacle-detection module for a small indoor robot "
        "so it can detect objects in front of it and react before it hits them."
    ),
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _collect_ids(payload: dict, prefix: str) -> set[str]:
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and node.startswith(prefix):
            found.add(node)

    walk(payload)
    return found


@pytest.mark.asyncio
@pytest.mark.parametrize("family", list(PROMPTS))
async def test_initialize_supported_families(family: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={"message": PROMPTS[family], "autonomyMode": "collaborate"},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["schemaVersion"] == "1.0.0"
    types = {a["artifactType"] for a in payload["artifacts"]}
    assert types == {
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "next-action",
    }
    assert len(payload["artifacts"]) == 4
    next_ref = payload["veraResponse"]["nextActionArtifactReference"]["artifactId"]
    assert any(a["artifactId"] == next_ref for a in payload["artifacts"])
    steps = [s["stepType"] for s in payload["workflowRun"]["stepRecords"]]
    assert steps == [
        "route-turn",
        "select-fixture-family",
        "create-project-context",
        "materialize-fixture-package",
        "validate-schema",
        "validate-project-package",
        "build-result",
        "complete-workflow",
    ]
    assert all(s["status"] == "completed" for s in payload["workflowRun"]["stepRecords"])


@pytest.mark.asyncio
async def test_initialize_unsupported() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={"message": "I want a recipe recommendation chatbot."},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE"
    assert body["error"]["supportedFamilies"]


@pytest.mark.asyncio
async def test_initialize_ambiguous() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={"message": ("greenhouse vibration tremor rover obstacle detection machine")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AMBIGUOUS_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE"


@pytest.mark.asyncio
async def test_initialize_empty_message_rejected() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={"message": ""},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_initialize_invalid_autonomy_mode() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={"message": PROMPTS["wearable-tremor-monitor"], "autonomyMode": "chaos"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_repeated_initialize_produces_fresh_runtime_ids() -> None:
    transport = ASGITransport(app=app)
    prompt = PROMPTS["greenhouse-sensing-node"]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/projects/initialize",
            json={"message": prompt, "autonomyMode": "collaborate"},
        )
        second = await client.post(
            "/v1/projects/initialize",
            json={"message": prompt, "autonomyMode": "collaborate"},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    left = first.json()
    right = second.json()
    for prefix in (
        "proj_",
        "turn_",
        "route_",
        "run_",
        "art_",
        "req_",
        "arch_",
        "node_",
        "edge_",
        "issue_",
        "question_",
        "act_",
        "actor_",
    ):
        a = _collect_ids(left, prefix)
        b = _collect_ids(right, prefix)
        if not a and not b:
            continue
        assert a and b
        assert a.isdisjoint(b), prefix


@pytest.mark.asyncio
async def test_corrupted_package_returns_structured_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nexus_embedded_systems.workflows.project_initialization import materializer

    original = materializer.materialize_fixture_package

    def corrupt(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, str]]:
        result, id_map = original(*args, **kwargs)
        result["artifacts"] = result["artifacts"][:1]
        return result, id_map

    monkeypatch.setattr(
        "nexus_embedded_systems.workflows.project_initialization.providers."
        "fixture_provider.materialize_fixture_package",
        corrupt,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/projects/initialize",
            json={
                "message": PROMPTS["wearable-tremor-monitor"],
                "autonomyMode": "collaborate",
            },
        )
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INITIALIZATION_PACKAGE_VALIDATION_FAILED"
    assert "project" not in body
    assert "artifacts" not in body
    assert "Traceback" not in response.text
    assert "traceback" not in response.text.lower()
