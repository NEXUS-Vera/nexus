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


@pytest.mark.parametrize(
    "snapshot",
    [
        {"projectId": "other", "content": {"structuredContent": {}}},
        {"projectId": "proj_test", "content": {}},
        {"projectId": "proj_test", "content": {"structuredContent": None}},
        {"projectId": "proj_test", "content": {"structuredContent": []}},
    ],
)
def test_adapter_rejects_invalid_snapshot(snapshot: dict) -> None:
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import CircuitExecutionError

    provider, store = Mock(), Mock()
    adapter = CircuitSimulationExecutionAdapter(
        provider=provider, project_store=store, firmware_ready=True
    )
    with pytest.raises(CircuitExecutionError):
        adapter.execute(
            {
                "projectId": "proj_test",
                "artifactId": "art_test",
                "artifactType": "electrical-architecture",
                "artifactVersion": 1,
                "snapshot": snapshot,
            }
        )
    provider.assess_support.assert_not_called()
    store.get_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_validate_endpoint_does_not_block_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import threading

    from nexus_api import main
    from nexus_circuit_simulation import FakeCircuitSimulationProvider

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class SlowProvider(FakeCircuitSimulationProvider):
        def validate(self, workspace):
            entered.set()
            release.wait(3)
            finished.set()
            return super().validate(workspace)

    monkeypatch.setattr(main, "_wokwi_provider", SlowProvider())
    async with AsyncClient(
        transport=ASGITransport(app=app),
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
        assert initialized.status_code == 200
        pid = initialized.json()["project"]["projectId"]

        async def health_during_validation():
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            assert not release.is_set()
            assert not finished.is_set(), "validation blocked the event loop until it finished"
            response = await client.get("/healthz")
            assert response.status_code == 200
            release.set()

        task = asyncio.create_task(
            client.post(
                f"/v1/projects/{pid}/artifacts/electrical-architecture/circuit-simulation/validate"
            )
        )
        try:
            await health_during_validation()
            for _ in range(200):
                if task.done():
                    break
                await asyncio.sleep(0.01)
            response = await asyncio.wait_for(task, 1)
            assert response.status_code == 200, response.text
        finally:
            release.set()
            await asyncio.wait_for(task, 3)


def test_adapter_raises_typed_circuit_execution_error_on_timeout() -> None:
    from unittest.mock import Mock

    from nexus_api.circuit_simulation import CircuitSimulationExecutionAdapter
    from nexus_circuit_simulation import (
        CircuitExecutionError,
        ExecutionResult,
        SupportStatus,
    )

    provider, store = Mock(), Mock()
    store.get_artifact.return_value = {"content": {}}
    provider.assess_support.return_value.status = SupportStatus.SURROGATE_REQUIRED
    provider.materialize.return_value.manifest = {"mappings": []}
    provider.validate.return_value.valid = True
    provider.validate.return_value.findings = ()
    provider.execute.return_value = ExecutionResult(
        succeeded=False,
        exit_code=None,
        timed_out=True,
    )
    adapter = CircuitSimulationExecutionAdapter(
        provider=provider, project_store=store, firmware_ready=True
    )
    with pytest.raises(CircuitExecutionError) as error:
        adapter.execute(
            {
                "projectId": "proj_test",
                "artifactId": "art_test",
                "artifactType": "electrical-architecture",
                "artifactVersion": 1,
                "snapshot": {"projectId": "proj_test", "content": {"structuredContent": {}}},
            }
        )
    assert error.value.code == "SIMULATION_TIMEOUT"
    # Preserve the execution service's timed-out status classification.
    assert isinstance(error.value, TimeoutError)
