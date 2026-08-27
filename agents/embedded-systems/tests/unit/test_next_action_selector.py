"""Priority ordering for deterministic Next Action selection."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.next_action_selector import (
    select_next_action,
)


def _blocking_issue(
    issue_id: str = "issue_1", code: str = "missing-engineering-dimensions"
) -> dict[str, Any]:
    return {"issueId": issue_id, "blocking": True, "code": code}


def _non_blocking_issue(issue_id: str = "issue_warn") -> dict[str, Any]:
    return {"issueId": issue_id, "blocking": False, "code": "non-blocking-warning"}


def _open_question(
    question_id: str = "question_1",
    *,
    artifact_ids: tuple[str, ...] = (),
    status: str = "open",
    question: str = "What is the target sampling rate?",
) -> dict[str, Any]:
    return {
        "questionId": question_id,
        "status": status,
        "question": question,
        "blocks": [],
        "sourceReferences": [
            {"kind": "artifact", "artifactId": artifact_id} for artifact_id in artifact_ids
        ],
    }


def test_blocking_issue_outranks_everything_else() -> None:
    action = select_next_action(
        issues=[_blocking_issue()],
        open_questions=[_open_question(artifact_ids=("art_1", "art_2"))],
        missing_dimensions=["performance", "interface", "architecture"],
        project_stage="concept",
    )
    assert action["priority"] == "critical"
    assert action["title"] == "Resolve blocking validation defect"
    assert action["sourceIssueIds"] == ["issue_1"]
    assert action["blocks"] == [{"issueId": "issue_1"}]


def test_non_blocking_issue_does_not_trigger_blocking_action() -> None:
    action = select_next_action(
        issues=[_non_blocking_issue()],
        open_questions=[],
        missing_dimensions=[],
        project_stage="concept",
    )
    assert action["title"] != "Resolve blocking validation defect"
    assert action["priority"] == "low"


def test_multi_artifact_open_question_outranks_missing_dimensions() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[_open_question(artifact_ids=("art_1", "art_2"))],
        missing_dimensions=["performance target", "interface constraints", "architecture gap"],
        project_stage="concept",
    )
    assert action["title"] == "Resolve decision blocking multiple artifacts"
    assert action["priority"] == "high"
    assert action["sourceQuestionIds"] == ["question_1"]


def test_single_artifact_open_question_does_not_outrank_missing_dimensions() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[_open_question(artifact_ids=("art_1",))],
        missing_dimensions=["performance target"],
        project_stage="concept",
    )
    assert action["title"] == "Clarify measurement and performance targets"


def test_resolved_multi_artifact_question_is_ignored() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[_open_question(artifact_ids=("art_1", "art_2"), status="resolved")],
        missing_dimensions=["performance target"],
        project_stage="concept",
    )
    assert action["title"] == "Clarify measurement and performance targets"


def test_measurement_dimension_outranks_interface_and_architecture() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=["interface constraints", "sampling rate", "architecture gap"],
        project_stage="concept",
    )
    assert action["title"] == "Clarify measurement and performance targets"
    assert action["priority"] == "high"


def test_interface_dimension_outranks_architecture() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=["architecture gap", "connectivity requirements"],
        project_stage="concept",
    )
    assert action["title"] == "Clarify interface, environment, or resource constraints"
    assert action["priority"] == "medium"


def test_architecture_dimension_is_lowest_ranked_missing_dimension() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=["system boundary is unresolved"],
        project_stage="concept",
    )
    assert action["title"] == "Resolve remaining functional architecture gaps"
    assert action["priority"] == "medium"


def test_fallback_component_selection_ready_when_nothing_outstanding() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="prototype-planning",
    )
    assert action["title"] == "Proceed to component-selection scoping"
    assert action["priority"] == "low"
    assert "prototype-planning" in action["rationale"]


def test_action_id_is_minted_and_completion_condition_present() -> None:
    action = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="concept",
    )
    assert action["actionId"].startswith("act_")
    assert action["owner"] == "vera"
    assert "conditionType" in action["completionCondition"]
    assert "completionCriteria" in action["completionCondition"]


def test_dimension_gap_action_attaches_relevant_open_question_prerequisites() -> None:
    question = _open_question(
        question_id="question_perf",
        artifact_ids=("art_1",),
        question="What is the required sampling rate for the sensor?",
    )
    action = select_next_action(
        issues=[],
        open_questions=[question],
        missing_dimensions=["sampling rate"],
        project_stage="concept",
    )
    assert action["sourceQuestionIds"] == ["question_perf"]
    assert action["prerequisites"] == [{"schemaVersion": "1.0.0", "questionId": "question_perf"}]


def test_verify_failed_and_uncovered_surface_as_next_action() -> None:
    failed = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="prototype-planning",
        test_plan_content={
            "coverageSummary": {
                "uncoveredRequirements": 0,
                "failedRequirements": 1,
            },
            "testCases": [],
        },
    )
    assert failed["title"] == "Resolve failed requirement verification"

    uncovered = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="prototype-planning",
        test_plan_content={
            "coverageSummary": {
                "uncoveredRequirements": 2,
                "failedRequirements": 0,
            },
            "testCases": [],
        },
    )
    assert uncovered["title"] == "Cover uncovered requirements with TestCases"


def test_verify_blocked_and_high_risk_gaps_surface() -> None:
    blocked = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="prototype-planning",
        test_plan_content={
            "coverageSummary": {"uncoveredRequirements": 0, "failedRequirements": 0},
            "testCases": [{"displayId": "T4", "status": "blocked"}],
        },
    )
    assert blocked["title"] == "Unblock blocked verification tests"

    risk = select_next_action(
        issues=[],
        open_questions=[],
        missing_dimensions=[],
        project_stage="prototype-planning",
        test_plan_content={
            "coverageSummary": {"uncoveredRequirements": 0, "failedRequirements": 0},
            "testCases": [{"displayId": "T7", "status": "passed"}],
        },
        risk_register_content={
            "risks": [
                {
                    "displayId": "K9",
                    "severity": "high",
                    "status": "open",
                    "verificationTestIds": [],
                    "linkedTestIds": [],
                }
            ]
        },
    )
    assert risk["title"] == "Add verification tests for high-severity risks"
