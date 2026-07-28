from __future__ import annotations

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
            json={
                "message": (
                    "greenhouse vibration tremor rover obstacle detection machine"
                )
            },
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
