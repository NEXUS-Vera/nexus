"""Offline API coverage for provider-neutral circuit-simulation surfaces."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.config import settings
from nexus_api.main import _kernel_store, app
from nexus_board.ids import new_id, utc_now_iso


@pytest.mark.asyncio
async def test_support_health_and_controlled_export_without_provider_call() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {settings.session_token}"},
    ) as client:
        initialized = await client.post(
            "/v1/projects/initialize",
            json={
                "message": (
                    "I want to build a device that records machine vibration "
                    "using a microcontroller and motion sensor."
                ),
                "autonomyMode": "collaborate",
            },
        )
        assert initialized.status_code == 200, initialized.text
        project_id = initialized.json()["project"]["projectId"]

        support = await client.get(
            f"/v1/projects/{project_id}/artifacts/"
            "electrical-architecture/circuit-simulation/support"
        )
        assert support.status_code == 200, support.text
        payload = support.json()
        assert payload["providerAvailability"]["providerId"] == "wokwi"
        assert payload["providerAvailability"]["status"] in {
            "READY",
            "WOKWI_CLI_MISSING",
            "WOKWI_CREDENTIAL_MISSING",
        }
        assert payload["assessment"]["capabilityId"] == "circuit-simulation"
        assert payload["assessment"]["providerId"] == "wokwi"

        outputs = await client.get(f"/v1/projects/{project_id}/outputs")
        assert outputs.status_code == 200
        assert outputs.json()["items"] == []

        export = await client.get(
            f"/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/export"
        )
        assert export.status_code == 404
        assert export.json()["error"]["code"] == "SIMULATION_EXPORT_NOT_FOUND"

        preview = await client.get(
            f"/v1/projects/{project_id}/artifacts/"
            "electrical-architecture/circuit-simulation/preview"
        )
        assert preview.status_code == 200, preview.text
        preview_payload = preview.json()
        assert preview_payload["providerId"] == "wokwi"
        assert "mappings" in preview_payload
        assert "connections" in preview_payload
        assert "diagram.json" not in preview_payload

        electrical = next(
            artifact
            for artifact in initialized.json()["artifacts"]
            if artifact["artifactType"] == "electrical-architecture"
        )
        now = utc_now_iso()
        _kernel_store.create_produced_output(
            {
                "schemaVersion": "1.0.0",
                "outputId": new_id("out"),
                "projectId": project_id,
                "artifactId": electrical["artifactId"],
                "workspaceId": new_id("ws"),
                "executionRunId": new_id("exec"),
                "outputType": "file-reference",
                "name": "provider-workspace-manifest",
                "mediaType": "application/json",
                "content": {
                    "kind": "inline-structured",
                    "structuredResult": {
                        "workspaceDigest": "sha256-test",
                        "manifest": {"providerId": "wokwi"},
                        "files": {"diagram.json": "{}\n"},
                    },
                },
                "contentDigest": "sha256-test",
                "createdAt": now,
                "evidenceStatus": "unverified",
                "supports": [
                    {
                        "supportKind": "artifact",
                        "targetId": electrical["artifactId"],
                    }
                ],
            }
        )
        persisted_export = await client.get(
            f"/v1/projects/{project_id}/artifacts/electrical-architecture/circuit-simulation/export"
        )
        assert persisted_export.status_code == 200
        assert persisted_export.json()["files"] == {"diagram.json": "{}\n"}
        assert "attachment;" in persisted_export.headers["content-disposition"]
