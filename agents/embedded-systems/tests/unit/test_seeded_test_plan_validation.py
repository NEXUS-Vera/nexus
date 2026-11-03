"""Seeded artifact diagnostics retain paths without dumping the artifact."""

import json
from pathlib import Path

import pytest
from nexus_board.errors import CommandValidationError
from nexus_embedded_systems.workflows.project_modification.execution_plan import (
    _validate_seeded_test_plan,
)


@pytest.mark.parametrize("field", ["actor", "content", "long"])
def test_seeded_test_plan_leaf_diagnostic(field: str) -> None:
    artifact = json.loads(
        (
            Path(__file__).resolve().parents[4] / "packages/contracts/examples/valid/"
            "esp32-imu-vibration-monitor/test-plan-artifact.json"
        ).read_text()
    )
    if field == "actor":
        artifact["createdBy"]["actorId"] = "actor_acceptance_operator"
        path, leaf = "createdBy.actorId", "does not match"
    else:
        artifact["content"]["testCases"][0]["status"] = (
            "invalid" if field == "content" else "x" * 9000
        )
        path, leaf = "content.testCases.0.status", "is not one of"
    with pytest.raises(CommandValidationError) as caught:
        _validate_seeded_test_plan(artifact)
    message = str(caught.value)
    assert path in message
    assert leaf in message
    assert len(message) <= 400
    assert "artifactId" not in message


def test_valid_seeded_test_plan() -> None:
    artifact = json.loads(
        (
            Path(__file__).resolve().parents[4] / "packages/contracts/examples/valid/"
            "esp32-imu-vibration-monitor/test-plan-artifact.json"
        ).read_text()
    )
    _validate_seeded_test_plan(artifact)
