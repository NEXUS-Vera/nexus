"""INT-01 analysis summary promotion enforces execution provenance over HTTP."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main
from test_phase17f_verify_e2e import _seed, _seed_summary_run


@pytest.mark.parametrize(
    "case,status,message",
    [
        ("missing", 422, "executionRunId is required."),
        ("unknown", 404, ""),
        ("foreign", 422, "ExecutionRun does not belong to this project."),
        ("failed", 422, "Only completed ExecutionRuns may promote verification evidence."),
        ("truncated", 422, "ExecutionRun logs were truncated; evidence is incomplete."),
        ("completed", 200, ""),
        ("completed-with-warnings", 200, ""),
    ],
)
async def test_analysis_summary_run_gate(
    case: str, status: int, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel, projects, project_id, _ = _seed()
    monkeypatch.setattr(main, "_kernel", kernel)
    run_id = "exec_API_SUMMARY"
    if case not in {"missing", "unknown"}:
        _seed_summary_run(
            kernel,
            "proj_FOREIGN" if case == "foreign" else project_id,
            run_id,
            "completed" if case == "foreign" else case,
        )
    before = projects.get_artifact(project_id, "test-plan")
    body = {
        "summary": {"accel_x_rms_noise_g": 0.0157},
        "producedOutputNames": [
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
    }
    if case != "missing":
        body["executionRunId"] = run_id
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        response = await client.post(
            f"/v1/projects/{project_id}/verify/promote-analysis-summary", json=body
        )
    assert response.status_code == status, response.text
    if message:
        assert message in response.text
    after = projects.get_artifact(project_id, "test-plan")
    if status != 200:
        assert after == before
    else:
        assert response.json()["executionRunId"] == run_id
        assert response.json()["changed"] is True
        assert after["artifactVersion"] > before["artifactVersion"]
