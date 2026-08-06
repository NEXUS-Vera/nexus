"""Phase 12 Component Plan API integration tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

GREENHOUSE = (
    "I want to build a greenhouse monitoring node that measures temperature, "
    "humidity, soil moisture, and light, and reports the readings remotely."
)


@pytest.mark.asyncio
async def test_phase12_component_plan_init_get_and_approve() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/projects/initialize",
            json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
        )
        assert created.status_code == 200, created.text
        body = created.json()
        project_id = body["project"]["projectId"]
        artifact_types = {a["artifactType"] for a in body["artifacts"]}
        assert "component-plan" in artifact_types
        assert len(body["artifacts"]) >= 5

        component = next(a for a in body["artifacts"] if a["artifactType"] == "component-plan")
        assert component["content"]["componentRoles"]
        assert "coverageSummary" in component["content"]

        fetched = await client.get(f"/v1/projects/{project_id}/artifacts/component-plan")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["artifactId"] == component["artifactId"]

        board = await client.get(f"/v1/projects/{project_id}/board")
        assert board.status_code == 200
        summaries = {
            s["artifactType"]: s for s in board.json()["artifactSummaries"]
        }
        assert "component-plan" in summaries
        cp_summary = summaries["component-plan"]
        assert cp_summary.get("roleCount", 0) >= 1
        assert "maturity" in cp_summary

        # Fixture-mode turn: add a budget constraint (works even without candidates).
        turn = await client.post(
            f"/v1/projects/{project_id}/turns",
            json={
                "message": "Add a budget constraint under $25 for the component role.",
                "autonomyMode": "collaborate",
            },
        )
        assert turn.status_code == 200, turn.text
        turn_body = turn.json()
        updated_cp = next(
            a
            for a in turn_body["currentState"]["artifacts"]
            if a["artifactType"] == "component-plan"
        )
        # Role IDs preserved across selective update when architecture unchanged.
        old_role_ids = {r["componentRoleId"] for r in component["content"]["componentRoles"]}
        new_role_ids = {r["componentRoleId"] for r in updated_cp["content"]["componentRoles"]}
        assert old_role_ids.intersection(new_role_ids) or updated_cp["content"][
            "selectionConstraints"
        ]

        # If candidates exist (or after alternatives request), approval path works.
        alt = await client.post(
            f"/v1/projects/{project_id}/turns",
            json={
                "message": "Please propose alternative component candidates.",
                "autonomyMode": "collaborate",
            },
        )
        assert alt.status_code == 200, alt.text
        alt_cp = next(
            a
            for a in alt.json()["currentState"]["artifacts"]
            if a["artifactType"] == "component-plan"
        )
        if alt_cp["content"].get("candidates"):
            approve = await client.post(
                f"/v1/projects/{project_id}/turns",
                json={
                    "message": "Approve the component selection for the sensor candidate.",
                    "autonomyMode": "collaborate",
                },
            )
            assert approve.status_code == 200, approve.text
            approved_cp = next(
                a
                for a in approve.json()["currentState"]["artifacts"]
                if a["artifactType"] == "component-plan"
            )
            assert any(
                s.get("selectionState") == "approved"
                for s in approved_cp["content"].get("selectionDecisions") or []
            )
