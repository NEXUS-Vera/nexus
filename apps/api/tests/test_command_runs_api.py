"""Read persisted command results without changing project state."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from nexus_api.config import settings
from test_phase11_kernel_api import GREENHOUSE, _actor, _cmd_id


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_command_run_read_and_project_isolation(failed: bool) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {settings.session_token}"},
    ) as client:

        async def initialize() -> dict:
            response = await client.post(
                "/v1/projects/initialize",
                json={"message": GREENHOUSE, "autonomyMode": "collaborate"},
            )
            assert response.status_code == 200, response.text
            return response.json()

        project = await initialize()
        project_id = project["project"]["projectId"]
        artifact = next(a for a in project["artifacts"] if a["artifactType"] == "requirement-set")
        workspace = await client.post(
            f"/v1/projects/{project_id}/artifacts/requirement-set/workspace",
            json={"requestedBy": _actor()},
        )
        assert workspace.status_code == 200, workspace.text
        command = await client.post(
            f"/v1/projects/{project_id}/artifact-commands",
            json={
                "schemaVersion": "1.0.0",
                "commandId": _cmd_id(),
                "commandType": "workspace.acquire-edit-lease",
                "projectId": project_id,
                "artifactId": artifact["artifactId"],
                "workspaceId": workspace.json()["workspace"]["workspaceId"],
                "baseArtifactVersion": 1,
                "baseProjectStateVersion": 1,
                "requestedBy": _actor(),
                "requestedAt": "2026-08-04T12:00:00Z",
                "input": {},
            },
        )
        assert command.status_code == 200, command.text
        result = command.json()
        run_id = result["commandRunId"]
        assert "executionRunId" not in result
        if failed:
            # Reproduce a persisted failed composite command with no execution run.
            result["status"] = "failed"
            main._kernel_store.append_command_run(result)
        persisted = main._kernel_store.get_command_run(run_id)
        before = (await client.get(f"/v1/projects/{project_id}")).json()
        # A read must never append a command result.
        with patch.object(main._kernel_store, "append_command_run", side_effect=AssertionError):
            response = await client.get(f"/v1/projects/{project_id}/command-runs/{run_id}")
            assert response.status_code == 200, response.text
            assert response.json() == {"schemaVersion": "1.0.0", "commandRun": persisted}
            assert persisted == result

            other_project_id = (await initialize())["project"]["projectId"]
            for target_project, target_run, code in [
                (project_id, "cmdrun_missing", "COMMAND_RUN_NOT_FOUND"),
                ("malformed-project-id", run_id, "PROJECT_NOT_FOUND"),
                ("proj_00000000000000000000000000", "cmdrun_missing", "PROJECT_NOT_FOUND"),
                ("proj_00000000000000000000000000", run_id, "PROJECT_NOT_FOUND"),
                (other_project_id, run_id, "COMMAND_RUN_NOT_FOUND"),
            ]:
                response = await client.get(
                    f"/v1/projects/{target_project}/command-runs/{target_run}",
                    headers={"X-Request-ID": "command-read-test"},
                )
                assert response.status_code == 404, response.text
                assert response.json()["error"]["code"] == code
                assert response.json()["error"]["requestId"] == "command-read-test"
                assert "commandRun" not in response.json()

        assert (await client.get(f"/v1/projects/{project_id}")).json() == before
        assert main._kernel_store.get_command_run(run_id) == persisted
        path = "/v1/projects/{project_id}/command-runs/{command_run_id}"
        assert "get" in main.app.openapi()["paths"][path]
