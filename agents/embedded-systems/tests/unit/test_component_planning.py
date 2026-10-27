"""Component planning composition and selective revision tests."""

from __future__ import annotations

import pytest
from nexus_embedded_systems.workflows.component_planning import (
    apply_component_plan_operation,
    compose_component_plan_content,
)
from nexus_embedded_systems.workflows.component_planning.propose_candidates import (
    propose_candidates_for_roles,
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
    assert "electrical-architecture" in impact["regenerate"]
    assert "physical-architecture" in impact["regenerate"]
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


def test_functional_type_is_primary_category_signal() -> None:
    from nexus_embedded_systems.workflows.component_planning.derive_roles import (
        derive_roles_with_coverage,
    )

    architecture = {
        "nodes": [
            {
                "nodeId": "node_SENSINGNODE0000000001",
                "name": "Deployment configuration",
                "functionalType": "sensing",
                "responsibilities": ["Configure deployment session placeholders"],
                "satisfiesRequirementIds": ["req_TEMPREQUIREMENT00001"],
            },
            {
                "nodeId": "node_UINODE00000000000001",
                "name": "User session input",
                "functionalType": "user-interface",
                "responsibilities": ["Measure ambient temperature for display"],
                "satisfiesRequirementIds": [],
            },
            {
                "nodeId": "node_EXTERNALNODE00000001",
                "name": "Remote cloud",
                "functionalType": "external-system",
                "responsibilities": ["Receive remote reports"],
                "satisfiesRequirementIds": [],
            },
            {
                "nodeId": "node_STORAGENODE000000001",
                "name": "Local log storage",
                "functionalType": "storage",
                "responsibilities": ["Persist records"],
                "satisfiesRequirementIds": [],
            },
        ]
    }
    roles, skipped = derive_roles_with_coverage(architecture, source="inferred")
    by_node = {r["architectureNodeIds"][0]: r for r in roles}
    assert by_node["node_SENSINGNODE0000000001"]["category"] == "sensor"
    # functionalType wins over "Measure" text that would otherwise imply sensor
    assert by_node["node_UINODE00000000000001"]["category"] == "interface"
    assert by_node["node_STORAGENODE000000001"]["category"] == "storage"
    assert "node_EXTERNALNODE00000001" not in by_node
    assert any(s["nodeId"] == "node_EXTERNALNODE00000001" for s in skipped)


def test_role_derivation_does_not_silently_truncate() -> None:
    nodes = []
    for i in range(8):
        nodes.append(
            {
                "nodeId": f"node_SENSINGNODE{i:016d}",
                "name": f"Sensor bank {i}",
                "functionalType": "sensing",
                "responsibilities": [f"Sense channel {i}"],
                "satisfiesRequirementIds": ["req_TEMPREQUIREMENT00001"],
            }
        )
    content = compose_component_plan_content(
        architecture_content={"nodes": nodes},
        requirement_set_content=_requirements(),
        include_candidates=False,
    )
    assert len(content["componentRoles"]) == 8


def test_approved_selection_survives_unrelated_architecture_refresh() -> None:
    from nexus_embedded_systems.workflows.component_planning.reconcile import (
        reconcile_component_plan_after_architecture_change,
    )

    architecture = _architecture()
    content = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_requirements(),
        include_candidates=True,
    )
    candidate_id = content["candidates"][0]["candidateId"]
    role_id = content["candidates"][0]["componentRoleId"]
    approved = apply_component_plan_operation(
        content,
        operation="approve-component-selection",
        message="Approve the fixture candidate",
        architecture_content=architecture,
        target_candidate_id=candidate_id,
    )
    # Unrelated FA change: add an analysis node that does not disturb sensing binding.
    expanded = {
        "nodes": [
            *architecture["nodes"],
            {
                "nodeId": "node_ANALYSISNODE000000001",
                "name": "Analysis summaries",
                "functionalType": "analysis",
                "responsibilities": ["Aggregate stored measurements"],
                "satisfiesRequirementIds": [],
            },
        ]
    }
    reconciled = reconcile_component_plan_after_architecture_change(
        approved,
        architecture_content=expanded,
        requirement_set_content=_requirements(),
    )
    surviving = [
        s
        for s in reconciled["selectionDecisions"]
        if s.get("componentRoleId") == role_id and s.get("selectionState") == "approved"
    ]
    assert surviving
    assert surviving[0]["selectedCandidateId"] == candidate_id
    assert any(r["componentRoleId"] == role_id for r in reconciled["componentRoles"])


@pytest.mark.parametrize(
    "part, category, expected",
    [
        ("MPU6050", "sensor", "MPU6050"),
        ("MPU-6050", "sensor", "MPU6050"),
        ("mpu-6050", "sensor", "MPU6050"),
        ("BME280", "sensor", "FX-ENV-100"),
        ("MPU-6050X", "sensor", "FX-ENV-100"),
        ("ESP32-DEVKIT-V1", "compute", "ESP32-DEVKIT-V1"),
        ("ESP32 DevKit V1", "compute", "ESP32-DEVKIT-V1"),
        ("ESP32 DevKitV1", "compute", "ESP32-DEVKIT-V1"),
        ("esp32 devkit", "compute", "ESP32-DEVKIT-V1"),
        ("ESP32-DevKit", "compute", "ESP32-DEVKIT-V1"),
        ("ESP32-S3", "compute", "FX-MCU-32"),
        ("ESP32-DEVKIT-V2", "compute", "FX-MCU-32"),
    ],
)
def test_propose_candidates_preserves_supported_user_names(
    part: str, category: str, expected: str
) -> None:
    candidates = propose_candidates_for_roles(
        [{"componentRoleId": "role_motion", "category": category, "name": "Motion sensing"}],
        user_message=f"Build a monitor using {part}.",
    )
    preferred, fallback = candidates
    assert preferred["partNumber"] == expected
    assert preferred["candidateState"] == "preferred"
    assert preferred["source"] == ("fixture" if expected.startswith("FX-") else "user-provided")
    assert all(c["evidenceStatus"] == "unverified" for c in candidates)
    assert all(c["evidenceReferences"] == [] for c in candidates)
    assert fallback["source"] == "fixture"
    assert fallback["candidateState"] == "proposed"
