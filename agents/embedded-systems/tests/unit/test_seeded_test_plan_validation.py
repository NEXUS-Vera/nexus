"""Seeded artifact diagnostics retain paths without dumping the artifact."""

import json
from pathlib import Path

import pytest
from nexus_board.errors import CommandValidationError
from nexus_embedded_systems.workflows.project_modification.execution_plan import (
    _validate_seeded_test_plan,
)


@pytest.mark.parametrize("field", ["actor", "content", "long", "root", "dotted-key"])
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
    elif field == "root":
        artifact["content"] = {}
        path, leaf = "content:", "is a required property"
    elif field == "dotted-key":
        artifact["content"]["testCases"][0]["status"] = "invalid"
        artifact["content"]["unexpected.key.with.many.dots"] = True
        path, leaf = "content.testCases.0.status", "is not one of"
    else:
        artifact["content"]["testCases"][0]["status"] = (
            "invalid" if field == "content" else "x" * 9000
        )
        path, leaf = "content.testCases.0.status", "is not one of"
    with pytest.raises(CommandValidationError) as caught:
        _validate_seeded_test_plan(artifact)
    message = str(caught.value)
    assert "content.:" not in message
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


def test_seeded_test_plan_depth_counts_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from jsonschema import ValidationError
    from nexus_embedded_systems.workflows.project_modification import execution_plan

    errors = iter(
        [
            [ValidationError("shallow dotted key", path=["a.b.c.d.e"])],
            [ValidationError("deep leaf", path=["testCases", 0, "status"])],
        ]
    )
    monkeypatch.setattr(
        execution_plan,
        "make_validator",
        lambda *args: SimpleNamespace(iter_errors=lambda payload: next(errors)),
    )
    with pytest.raises(CommandValidationError, match=r"content\.testCases\.0\.status: deep leaf"):
        _validate_seeded_test_plan({"content": {}})
