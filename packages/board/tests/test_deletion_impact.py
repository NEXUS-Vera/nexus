"""Deletion impact inspect command is read-only and structured."""

from __future__ import annotations

from copy import deepcopy

from helpers import actor, build_test_kernel, cmd
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.services.deletion_impact import inspect_functional_node_deletion_impact


def test_inspect_helper_does_not_mutate_inputs() -> None:
    functional = {
        "nodes": [
            {
                "nodeId": "node_target",
                "satisfiesRequirementIds": ["req_1"],
            },
            {"nodeId": "node_keep", "satisfiesRequirementIds": ["req_2"]},
        ]
    }
    plan = {
        "componentRoles": [
            {
                "componentRoleId": "role_target",
                "architectureNodeIds": ["node_target"],
            },
            {"componentRoleId": "role_keep", "architectureNodeIds": ["node_keep"]},
        ]
    }
    electrical = {
        "nodes": [
            {
                "nodeId": "enode_target",
                "functionalArchitectureNodeIds": ["node_target"],
                "componentRoleIds": ["role_target"],
            },
            {
                "nodeId": "enode_keep",
                "functionalArchitectureNodeIds": ["node_keep"],
                "componentRoleIds": ["role_keep"],
            },
        ],
        "connections": [
            {
                "connectionId": "econn_1",
                "fromNodeId": "enode_target",
                "toNodeId": "enode_keep",
            }
        ],
    }
    physical = {
        "nodes": [
            {"nodeId": "pnode_target", "electricalNodeIds": ["enode_target"]},
            {"nodeId": "pnode_keep", "electricalNodeIds": ["enode_keep"]},
        ],
        "relationships": [],
    }
    before = {
        "functional": deepcopy(functional),
        "plan": deepcopy(plan),
        "electrical": deepcopy(electrical),
        "physical": deepcopy(physical),
    }
    impact = inspect_functional_node_deletion_impact(
        node_id="node_target",
        functional_content=functional,
        component_plan_content=plan,
        electrical_content=electrical,
        physical_content=physical,
    )
    assert impact["blocking"] is True
    assert impact["affectedComponentRoleIds"] == ["role_target"]
    assert impact["affectedElectricalNodeIds"] == ["enode_target"]
    assert impact["affectedElectricalConnectionIds"] == ["econn_1"]
    assert impact["affectedPhysicalNodeIds"] == ["pnode_target"]
    assert "role_keep" not in impact["affectedComponentRoleIds"]
    assert "enode_keep" not in impact["affectedElectricalNodeIds"]
    assert "pnode_keep" not in impact["affectedPhysicalNodeIds"]
    # No silent cascade: inputs unchanged.
    assert functional == before["functional"]
    assert plan == before["plan"]
    assert electrical == before["electrical"]
    assert physical == before["physical"]


def test_inspect_deletion_impact_command_returns_payload() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "functional-architecture")
    now = utc_now_iso()
    project = project_store.get_project(project_id)
    next_state = int(project["currentStateVersion"]) + 1
    revised = {
        **art,
        "artifactId": new_id("art"),
        "artifactVersion": int(art["artifactVersion"]) + 1,
        "content": {
            "architectureId": "arch_delete_guard",
            "summary": "Deletion guard",
            "nodes": [
                {
                    "nodeId": "node_target",
                    "name": "Sensing",
                    "functionalType": "sensing",
                    "responsibilities": ["Sense"],
                    "satisfiesRequirementIds": ["req_1"],
                },
                {
                    "nodeId": "node_keep",
                    "name": "Compute",
                    "functionalType": "processing",
                    "responsibilities": ["Compute"],
                    "satisfiesRequirementIds": ["req_2"],
                },
            ],
            "edges": [
                {
                    "edgeId": "edge_1",
                    "fromNodeId": "node_target",
                    "toNodeId": "node_keep",
                    "flowType": "data",
                    "description": "sense to compute",
                }
            ],
            "interfaces": [],
            "requirementCoverage": {"coveredRequirementIds": ["req_1", "req_2"]},
        },
        "updatedAt": now,
        "supersedesArtifactId": art["artifactId"],
        "supersedesArtifactVersion": art["artifactVersion"],
    }
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=revised,
        next_state_version=next_state,
        updated_at=now,
        expected_artifact_version=art["artifactVersion"],
        expected_project_state_version=project["currentStateVersion"],
    )

    plan_art = {
        "schemaVersion": "1.0.0",
        "artifactId": new_id("art"),
        "projectId": project_id,
        "artifactType": "component-plan",
        "artifactVersion": 1,
        "contentSchemaVersion": "1.0.0",
        "lifecycleStatus": "ready",
        "evidenceStatus": "unverified",
        "approvalStatus": "proposed",
        "createdBy": actor(),
        "createdAt": now,
        "updatedAt": now,
        "sourceTurnId": art["sourceTurnId"],
        "workflowRunId": art["workflowRunId"],
        "content": {
            "selectionState": "draft",
            "candidateCount": 0,
            "constraintSummary": "test",
            "unresolvedCompatibilityChecks": [],
            "approvalStatus": "not-required",
            "componentRoles": [
                {
                    "componentRoleId": "role_target",
                    "name": "Sensor",
                    "category": "sensing",
                    "architectureNodeIds": ["node_target"],
                    "requirementIds": ["req_1"],
                    "selectionState": "unresolved",
                },
                {
                    "componentRoleId": "role_keep",
                    "name": "MCU",
                    "category": "processing",
                    "architectureNodeIds": ["node_keep"],
                    "requirementIds": ["req_2"],
                    "selectionState": "unresolved",
                },
            ],
            "candidates": [],
        },
    }
    project = project_store.get_project(project_id)
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=plan_art,
        next_state_version=int(project["currentStateVersion"]) + 1,
        updated_at=now,
        expected_project_state_version=project["currentStateVersion"],
    )

    electrical_art = {
        "schemaVersion": "1.0.0",
        "artifactId": new_id("art"),
        "projectId": project_id,
        "artifactType": "electrical-architecture",
        "artifactVersion": 1,
        "contentSchemaVersion": "1.0.0",
        "lifecycleStatus": "ready",
        "evidenceStatus": "unverified",
        "approvalStatus": "proposed",
        "createdBy": actor(),
        "createdAt": now,
        "updatedAt": now,
        "sourceTurnId": art["sourceTurnId"],
        "workflowRunId": art["workflowRunId"],
        "content": {
            "architectureId": "earch_1",
            "summary": "Electrical",
            "nodes": [
                {
                    "nodeId": "enode_target",
                    "name": "Sensor",
                    "nodeType": "component-implementation",
                    "functionalArchitectureNodeIds": ["node_target"],
                    "componentRoleIds": ["role_target"],
                    "implementationStatus": "unresolved",
                    "evidenceStatus": "unverified",
                    "selectionState": "none",
                    "interfaces": [],
                    "requirementIds": [],
                },
                {
                    "nodeId": "enode_keep",
                    "name": "MCU",
                    "nodeType": "component-implementation",
                    "functionalArchitectureNodeIds": ["node_keep"],
                    "componentRoleIds": ["role_keep"],
                    "implementationStatus": "unresolved",
                    "evidenceStatus": "unverified",
                    "selectionState": "none",
                    "interfaces": [],
                    "requirementIds": [],
                },
            ],
            "connections": [],
            "powerDomains": [],
            "coverageSummary": {
                "unresolvedNodeCount": 2,
                "unresolvedConnectionCount": 0,
                "provisionalSelectionCount": 0,
            },
        },
    }
    project = project_store.get_project(project_id)
    project_store.apply_accepted_artifact_revision(
        project_id=project_id,
        new_artifact=electrical_art,
        next_state_version=int(project["currentStateVersion"]) + 1,
        updated_at=now,
        expected_project_state_version=project["currentStateVersion"],
    )

    electrical_before = project_store.get_artifact(project_id, "electrical-architecture")
    plan_before = project_store.get_artifact(project_id, "component-plan")
    fa = project_store.get_artifact(project_id, "functional-architecture")

    result = kernel.dispatch(
        cmd(
            command_type="artifact.inspect-deletion-impact",
            project_id=project_id,
            artifact_id=fa["artifactId"],
            input_data={"entityType": "functional-node", "entityId": "node_target"},
            requested_by=actor(),
            base_artifact_version=fa["artifactVersion"],
            base_project_state_version=project_store.get_project(project_id)["currentStateVersion"],
        )
    )
    assert result["status"] == "completed"
    impact = result["resultPayload"]
    assert impact["blocking"] is True
    assert "role_target" in impact["affectedComponentRoleIds"]
    assert "enode_target" in impact["affectedElectricalNodeIds"]
    assert "role_keep" not in impact["affectedComponentRoleIds"]
    assert "enode_keep" not in impact["affectedElectricalNodeIds"]

    electrical_after = project_store.get_artifact(project_id, "electrical-architecture")
    plan_after = project_store.get_artifact(project_id, "component-plan")
    assert electrical_after["artifactVersion"] == electrical_before["artifactVersion"]
    assert plan_after["artifactVersion"] == plan_before["artifactVersion"]
    assert electrical_after["content"] == electrical_before["content"]
