"""Component planning composition and selective revision tests."""

from __future__ import annotations

import pytest
from nexus_embedded_systems.workflows.component_planning import (
    apply_component_plan_operation,
    compose_component_plan_content,
)
from nexus_embedded_systems.workflows.component_planning.revise import (
    ComponentPlanRevisionError,
)
from nexus_embedded_systems.workflows.project_modification.fixture_interpreter import (
    FixtureModificationError,
    interpret_fixture_change,
)
from nexus_embedded_systems.workflows.project_modification.impact import analyze_impact


def _architecture() -> dict:
    return {
        "nodes": [
            {
                "nodeId": "node_SENSINGNODE0000000001",
                "name": "Environmental sensing",
                "description": "Acquire temperature measurements",
                "responsibilities": ["Measure ambient temperature"],
                "satisfiesRequirementIds": ["req_TEMPREQUIREMENT00001"],
            },
            {
                "nodeId": "node_POWERNODE000000000001",
                "name": "Power delivery",
                "description": "Supply power",
                "responsibilities": ["Provide battery power"],
                "satisfiesRequirementIds": [],
            },
        ]
    }


def _requirements() -> dict:
    return {
        "requirements": [
            {
                "requirementId": "req_TEMPREQUIREMENT00001",
                "statement": "Measure temperature accurately",
                "category": "performance",
                "confirmationStatus": "confirmed",
            }
        ]
    }


def test_compose_derives_sensor_role() -> None:
    content = compose_component_plan_content(
        architecture_content=_architecture(),
        requirement_set_content=_requirements(),
        include_candidates=False,
    )
    assert content["componentRoles"]
    assert content["maturity"] == "roles-defined"
    assert content["coverageSummary"]["rolesWithoutCandidates"] >= 1
    role_ids = {r["componentRoleId"] for r in content["componentRoles"]}
    assert all(rid.startswith("role_") for rid in role_ids)


def test_approve_selection_preserves_role_id() -> None:
    content = compose_component_plan_content(
        architecture_content=_architecture(),
        requirement_set_content=_requirements(),
        include_candidates=True,
    )
    role_id = content["componentRoles"][0]["componentRoleId"]
    candidate_id = content["candidates"][0]["candidateId"]
    updated = apply_component_plan_operation(
        content,
        operation="approve-component-selection",
        message="Approve the fixture candidate",
        architecture_content=_architecture(),
        target_candidate_id=candidate_id,
    )
    assert updated["componentRoles"][0]["componentRoleId"] == role_id
    assert any(s["selectionState"] == "approved" for s in updated["selectionDecisions"])


def test_ambiguous_candidate_rejection() -> None:
    content = compose_component_plan_content(
        architecture_content=_architecture(),
        requirement_set_content=_requirements(),
        include_candidates=True,
    )
    # Force two candidates without target id.
    content["candidates"].append(dict(content["candidates"][0]))
    content["candidates"][-1]["candidateId"] = "cand_SECONDCANDIDATE0001"
    with pytest.raises(ComponentPlanRevisionError) as exc:
        apply_component_plan_operation(
            content,
            operation="reject-component-candidate",
            message="Reject a candidate",
            architecture_content=_architecture(),
        )
    assert exc.value.code == "AMBIGUOUS_PROJECT_CHANGE_TARGET"


def test_fixture_interpreter_approve_selection() -> None:
    content = compose_component_plan_content(
        architecture_content=_architecture(),
        requirement_set_content=_requirements(),
        include_candidates=True,
    )
    state = {
        "artifacts": [{"artifactType": "component-plan", "content": content}],
        "openQuestions": [],
    }
    intent = interpret_fixture_change(
        "Please approve the component selection for the sensor.",
        source_turn_id="turn_abcdefghijklmnop",
        current_state=state,
    )
    assert intent["operation"] == "approve-component-selection"
    impact = analyze_impact(operation=intent["operation"])
    assert "component-plan" in impact["regenerate"]
    assert "next-action" in impact["regenerate"]


def test_fixture_interpreter_ambiguous_candidates() -> None:
    content = compose_component_plan_content(
        architecture_content=_architecture(),
        requirement_set_content=_requirements(),
        include_candidates=True,
    )
    content["candidates"].append(dict(content["candidates"][0]))
    content["candidates"][-1]["candidateId"] = "cand_SECONDCANDIDATE0001"
    state = {
        "artifacts": [{"artifactType": "component-plan", "content": content}],
        "openQuestions": [],
    }
    with pytest.raises(FixtureModificationError) as exc:
        interpret_fixture_change(
            "Reject the component candidate.",
            source_turn_id="turn_abcdefghijklmnop",
            current_state=state,
        )
    assert exc.value.code == "AMBIGUOUS_PROJECT_CHANGE_TARGET"
