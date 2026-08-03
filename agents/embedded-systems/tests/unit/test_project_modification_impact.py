"""Fixture interpreter and impact unit tests for project modification."""

from __future__ import annotations

import pytest
from nexus_embedded_systems.workflows.project_modification.fixture_interpreter import (
    FixtureModificationError,
    interpret_fixture_change,
)
from nexus_embedded_systems.workflows.project_modification.impact import analyze_impact


def _state_with_requirements(requirements: list[dict]) -> dict:
    return {
        "artifacts": [
            {
                "artifactType": "requirement-set",
                "content": {"requirements": requirements},
            }
        ],
        "openQuestions": [],
    }


def test_runtime_change_impacts_architecture() -> None:
    impact = analyze_impact(
        operation="add-requirement",
        requirement_categories=["runtime"],
        semantic_change=True,
    )
    assert "requirement-set" in impact["regenerate"]
    assert "functional-architecture" in impact["regenerate"]
    assert "next-action" in impact["regenerate"]
    assert "project-brief" in impact["unchanged"]


def test_accuracy_clarify_does_not_force_architecture() -> None:
    impact = analyze_impact(
        operation="clarify-requirement",
        requirement_categories=["accuracy"],
        semantic_change=False,
    )
    assert "requirement-set" in impact["regenerate"]
    assert "functional-architecture" not in impact["regenerate"]
    assert "project-brief" in impact["unchanged"]


def test_fixture_runtime_battery_intent() -> None:
    intent = interpret_fixture_change(
        "It should run for at least six months on battery power.",
        source_turn_id="turn_abcdefghijklmnop",
        current_state=_state_with_requirements(
            [
                {
                    "requirementId": "req_runtime_1",
                    "category": "resource",
                    "statement": "Operate for a useful duration.",
                    "confirmationStatus": "proposed",
                }
            ]
        ),
    )
    assert intent["operation"] in {"add-requirement", "change-requirement", "clarify-requirement"}
    assert intent["targetArtifactType"] == "requirement-set"


def test_fixture_reject_proposed() -> None:
    intent = interpret_fixture_change(
        "Please reject the proposed requirement about remote reporting.",
        source_turn_id="turn_abcdefghijklmnop",
        current_state=_state_with_requirements(
            [
                {
                    "requirementId": "req_comms_1",
                    "category": "communication",
                    "statement": "Report readings remotely.",
                    "confirmationStatus": "proposed",
                }
            ]
        ),
    )
    assert intent["operation"] == "remove-proposed-requirement"
    assert intent["targetRequirementId"] == "req_comms_1"


def test_fixture_ambiguous_runtime_targets() -> None:
    with pytest.raises(FixtureModificationError) as exc:
        interpret_fixture_change(
            "Update the battery / runtime requirement to six months.",
            source_turn_id="turn_abcdefghijklmnop",
            current_state=_state_with_requirements(
                [
                    {
                        "requirementId": "req_runtime_1",
                        "category": "resource",
                        "statement": "Battery life should be long.",
                        "confirmationStatus": "confirmed",
                    },
                    {
                        "requirementId": "req_runtime_2",
                        "category": "resource",
                        "statement": "Runtime should support field use.",
                        "confirmationStatus": "confirmed",
                    },
                ]
            ),
        )
    assert exc.value.code == "AMBIGUOUS_PROJECT_CHANGE_TARGET"
