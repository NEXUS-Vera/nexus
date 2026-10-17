"""Promote routes take ``accept`` as a JSON boolean, never a truthy coercion.

``bool(body.get("accept", True))`` read the string ``"false"`` as True, so a
client that declined acceptance still got an accepted Test Plan revision. Any
non-boolean value now gives 422 before the verification service is called.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main

PROJECT_ID = "proj_ACCEPTFLAG0000000"

# (route suffix, VerificationService method, minimal valid body without accept)
_ROUTES = [
    ("promote-execution", "promote_execution_evidence", {"executionRunId": "exec_x"}),
    (
        "promote-analysis-summary",
        "promote_analysis_summary",
        {"executionRunId": "exec_x", "summary": {"accel_x_rms_noise_g": 0.0157}},
    ),
    ("promote-structural", "promote_structural_mapping", {"signalMap": {"SDA": "GPIO21"}}),
]


def _spy(monkeypatch: pytest.MonkeyPatch, method: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def reached(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"sentinel": True}

    monkeypatch.setattr(main._kernel.verification, method, reached)
    return calls


async def _post(suffix: str, body: dict[str, Any]) -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        return await client.post(f"/v1/projects/{PROJECT_ID}/verify/{suffix}", json=body)


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None, [], {}], ids=repr)
@pytest.mark.parametrize(("suffix", "method", "body"), _ROUTES)
async def test_non_boolean_accept_is_rejected(
    monkeypatch: pytest.MonkeyPatch, suffix: str, method: str, body: dict[str, Any], value: Any
) -> None:
    calls = _spy(monkeypatch, method)
    response = await _post(suffix, {**body, "accept": value})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "COMMAND_VALIDATION_FAILED"
    assert response.json()["error"]["message"] == "accept must be a boolean."
    assert calls == []


@pytest.mark.parametrize(
    ("extra", "expected"), [({}, True), ({"accept": True}, True), ({"accept": False}, False)]
)
@pytest.mark.parametrize(("suffix", "method", "body"), _ROUTES)
async def test_boolean_or_absent_accept_reaches_the_service(
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    method: str,
    body: dict[str, Any],
    extra: dict[str, Any],
    expected: bool,
) -> None:
    calls = _spy(monkeypatch, method)
    response = await _post(suffix, {**body, **extra})
    assert response.status_code == 200, response.text
    assert [call["accept"] for call in calls] == [expected]
