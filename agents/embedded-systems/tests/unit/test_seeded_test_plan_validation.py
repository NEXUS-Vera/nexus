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


@pytest.mark.parametrize(
    "criterion",
    [
        {"criterionType": "unknown"},
        {"criterionType": "contains", "marker": "ok", "result": "PASS"},
        {"criterionType": "contains", "marker": "x" * 4097},
        {"criterionType": "range", "metricId": "sampling_hz", "minValue": 60, "maxValue": 40},
        {
            "criterionType": "numeric-comparison",
            "metricId": "m",
            "operator": "<",
            "expectedValue": float("inf"),
        },
        {
            "criterionType": "numeric-comparison",
            "metricId": "m",
            "operator": "<",
            "expectedValue": True,
        },
        {"criterionType": "exact-match", "expectedValue": {"verdict": "PASS"}},
        {"criterionType": "contains"},
    ],
)
def test_invalid_criterion_proposals(criterion: dict) -> None:
    from nexus_contracts.validation.execution_plan_validator import valid_criterion_proposal

    assert not valid_criterion_proposal(criterion)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_model_criterion_proposal_is_optional_and_validated(invalid: bool) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from nexus_embedded_systems.workflows.project_initialization.execution_plan import (
        propose_execution_plan_criteria,
    )

    criterion = {"criterionType": "contains", "marker": "NEXUS_MPU_READY"}
    if invalid:
        criterion["result"] = "PASS"
    gateway = SimpleNamespace(
        generate_structured=AsyncMock(
            return_value=SimpleNamespace(
                parsed_output={
                    "objectives": [
                        {
                            "objectiveId": "o1",
                            "criterion": criterion,
                            "verificationMethod": "simulation",
                        }
                    ]
                }
            )
        )
    )
    plan = {"verificationObjectives": [{"objectiveId": "o1"}]}
    await propose_execution_plan_criteria(
        plan,
        {"artifacts": [{"artifactType": "requirement-set", "content": {"requirements": []}}]},
        gateway,
        None,
    )
    if invalid:
        assert plan["verificationObjectives"] == [{"objectiveId": "o1"}]
    else:
        assert plan["verificationObjectives"][0]["criterion"] == criterion
    from nexus_contracts.validation.schema_validator import make_validator

    output_schema = gateway.generate_structured.call_args.kwargs["output_schema"]
    assert make_validator(output_schema).is_valid(
        gateway.generate_structured.return_value.parsed_output
    ) == (not invalid)
    prompt = gateway.generate_structured.call_args.kwargs["system_instructions"]
    assert "Never author results" in prompt


def test_criterion_definition_serialized_budget() -> None:
    from nexus_contracts.validation.execution_plan_validator import valid_criterion_proposal

    criterion = {"criterionType": "contains", "marker": ""}
    criterion["marker"] = "x" * (4096 - len(json.dumps(criterion)))
    assert len(json.dumps(criterion)) == 4096
    assert valid_criterion_proposal(criterion)
    criterion["marker"] += "x"
    assert not valid_criterion_proposal(criterion)
