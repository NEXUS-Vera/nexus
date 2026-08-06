"""API persistence and multi-turn modification tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

GREENHOUSE = (
    "I want to build a greenhouse monitoring node that measures temperature, "
    "humidity, soil moisture, and light, and reports the readings remotely."
)


@pytest.mark.asyncio
async def test_initialize_get_history_and_runtime_turn() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200
        body = created.json()
        project_id = body["project"]["projectId"]
        brief_v1 = next(
            a["artifactVersion"]
            for a in body["artifacts"]
            if a["artifactType"] == "project-brief"
        )

        fetched = await client.get(f"/v1/projects/{project_id}")
        assert fetched.status_code == 200
        assert fetched.json()["project"]["projectId"] == project_id

        artifacts = await client.get(f"/v1/projects/{project_id}/artifacts")
        assert artifacts.status_code == 200
        assert len(artifacts.json()["artifacts"]) == 5

        history = await client.get(f"/v1/projects/{project_id}/history")
        assert history.status_code == 200
        assert len(history.json()["turns"]) == 1

        turned = await client.post(
            f"/v1/projects/{project_id}/turns",
            json={
                "message": "It should run for at least six months on battery power.",
                "autonomyMode": "collaborate",
            },
        )
        assert turned.status_code == 200, turned.text
        result = turned.json()
        arts = result["currentState"]["artifacts"]
        by_type = {a["artifactType"]: a["artifactVersion"] for a in arts}
        assert by_type["project-brief"] == brief_v1
        assert by_type["requirement-set"] == 2
        assert by_type["functional-architecture"] == 2
        assert by_type["component-plan"] >= 2
        assert by_type["next-action"] == 2

        again = await client.get(f"/v1/projects/{project_id}")
        assert again.status_code == 200
        assert again.json()["project"]["currentStateVersion"] == 2

        hist2 = await client.get(f"/v1/projects/{project_id}/history")
        assert len(hist2.json()["turns"]) == 2


@pytest.mark.asyncio
async def test_project_not_found() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/projects/proj_DOESNOTEXIST00001")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_unsupported_fixture_modification() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        project_id = created.json()["project"]["projectId"]
        response = await client.post(
            f"/v1/projects/{project_id}/turns",
            json={"message": "Please redesign the PCB stackup now.", "autonomyMode": "collaborate"},
        )
        assert response.status_code == 422
        assert (
            response.json()["error"]["code"]
            == "UNSUPPORTED_PROJECT_MODIFICATION_FOR_FIXTURE_PHASE"
        )
