"""Fixture regression evidence: plan retrieval over HTTP survives SQLite restart."""

import importlib
from dataclasses import replace

import nexus_api.main as main
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_execution_plan_survives_sqlite_restart(monkeypatch, tmp_path):
    original = main.settings
    monkeypatch.setattr(
        "nexus_api.config.settings",
        replace(
            original,
            storage_backend="sqlite",
            initialization_provider="fixture",
            database_url=f"sqlite:///{tmp_path / 'plan.db'}",
        ),
    )
    headers = {"Authorization": f"Bearer {original.session_token}"}
    try:
        importlib.reload(main)
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=headers
        ) as client:
            response = await client.post(
                "/v1/projects/initialize",
                json={
                    "message": "I want a golden Nexus circuit simulation project with an "
                    "ESP32-class MCU and an IMU motion sensor for Wokwi surrogate simulation."
                },
            )
            assert response.status_code == 200, response.text
            initialized = response.json()
            project_id = initialized["project"]["projectId"]
            plan = initialized["project"]["executionPlan"]
            before = await client.get(f"/v1/projects/{project_id}")
            assert before.status_code == 200, before.text
            assert before.json()["project"]["executionPlan"] == plan
            assert before.json()["artifacts"] == initialized["artifacts"]
        # Reconstruct the API, engines, repositories and services against the same database.
        importlib.reload(main)
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test", headers=headers
        ) as client:
            after = await client.get(f"/v1/projects/{project_id}")
            assert after.status_code == 200, after.text
            assert after.json()["project"]["executionPlan"] == plan
            assert after.json()["artifacts"] == initialized["artifacts"]
            assert after.json()["veraResponse"] == initialized["veraResponse"]
    finally:
        monkeypatch.setattr("nexus_api.config.settings", original)
        importlib.reload(main)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "goal",
    [
        "Create mechanical CAD for my ESP32 robot.",
        "Design the PCB layout for my ESP32 vibration monitor.",
        "Create a manufacturing plan for an ESP32 vibration monitor.",
    ],
)
async def test_fixture_initialization_declines_excluded_scope(goal):
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {main.settings.session_token}"},
    ) as client:
        response = await client.post("/v1/projects/initialize", json={"message": goal})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE"
