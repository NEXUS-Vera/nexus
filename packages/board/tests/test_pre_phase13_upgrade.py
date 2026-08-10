"""API/board tests for pre-Phase-13 project upgrade and workspace resolve."""

from __future__ import annotations

from helpers import actor, build_test_kernel, minimal_package
from nexus_board.ids import new_id, utc_now_iso
from nexus_embedded_systems.workflows.layered_architecture import (
    ensure_layered_architecture_artifacts,
)


def _pre_phase13_package_with_component_plan() -> dict:
    """Persisted-style package: FA + component-plan, no electrical/physical."""
    package = minimal_package()
    project_id = package["project"]["projectId"]
    turn_id = package["userTurn"]["turnId"]
    run_id = package["workflowRun"]["workflowRunId"]
    now = utc_now_iso()
    fa = next(a for a in package["artifacts"] if a["artifactType"] == "functional-architecture")
    fa["content"] = {
        "architectureId": "arch_pre13",
        "summary": "Pre-13 architecture",
        "systemBoundary": "Test boundary",
        "architectureMaturity": "provisional",
        "nodes": [
            {
                "nodeId": "node_SENSINGNODE0000000001",
                "name": "Sensing",
                "functionalType": "sensing",
                "responsibilities": ["Sense temperature"],
                "satisfiesRequirementIds": ["req_1"],
            },
            {
                "nodeId": "node_COMPUTENODE0000000001",
                "name": "Compute",
                "functionalType": "processing",
                "responsibilities": ["Process readings"],
                "satisfiesRequirementIds": ["req_1"],
            },
        ],
        "edges": [
            {
                "edgeId": "edge_1",
                "fromNodeId": "node_SENSINGNODE0000000001",
                "toNodeId": "node_COMPUTENODE0000000001",
                "flowType": "data",
                "description": "sense to compute",
            }
        ],
        "interfaces": [],
        "requirementCoverage": {"coveredRequirementIds": ["req_1"]},
    }
    plan = {
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
        "sourceTurnId": turn_id,
        "workflowRunId": run_id,
        "content": {
            "selectionState": "draft",
            "candidateCount": 0,
            "constraintSummary": "pre-13",
            "unresolvedCompatibilityChecks": [],
            "approvalStatus": "not-required",
            "componentRoles": [
                {
                    "componentRoleId": "role_sensor",
                    "name": "Sensor",
                    "category": "sensing",
                    "architectureNodeIds": ["node_SENSINGNODE0000000001"],
                    "requirementIds": ["req_1"],
                    "selectionState": "unresolved",
                },
                {
                    "componentRoleId": "role_mcu",
                    "name": "MCU",
                    "category": "processing",
                    "architectureNodeIds": ["node_COMPUTENODE0000000001"],
                    "requirementIds": ["req_1"],
                    "selectionState": "unresolved",
                },
            ],
            "candidates": [],
            "selectionDecisions": [],
        },
    }
    package["artifacts"].append(plan)
    package["project"]["currentArtifactReferences"].append(
        {
            "artifactType": "component-plan",
            "artifactId": plan["artifactId"],
            "artifactVersion": 1,
            "contentSchemaVersion": "1.0.0",
        }
    )
    return package


def test_ensure_layered_is_idempotent_for_pre_phase13_package() -> None:
    package = _pre_phase13_package_with_component_plan()
    project_id = package["project"]["projectId"]
    first = ensure_layered_architecture_artifacts(
        project_id=project_id,
        artifacts=list(package["artifacts"]),
        actor=actor(),
    )
    assert first["skippedReason"] is None
    created_types = {a["artifactType"] for a in first["created"]}
    assert created_types == {"electrical-architecture", "physical-architecture"}
    assert all(isinstance((a.get("content") or {}).get("nodes"), list) for a in first["created"])

    second = ensure_layered_architecture_artifacts(
        project_id=project_id,
        artifacts=list(first["artifacts"]),
        actor=actor(),
    )
    assert second["created"] == []
    types = [a["artifactType"] for a in second["artifacts"]]
    assert types.count("electrical-architecture") == 1
    assert types.count("physical-architecture") == 1


def test_workspace_create_if_missing_for_existing_artifact() -> None:
    kernel, project_store, _, project_id = build_test_kernel()
    art = project_store.get_artifact(project_id, "functional-architecture")
    assert kernel.workspaces.get_or_none(project_id, "functional-architecture") is None
    created = kernel.workspaces.create_if_missing(
        project_id=project_id,
        artifact_type="functional-architecture",
        actor=actor(),
    )
    assert created["workspace"]["artifactId"] == art["artifactId"]
    again = kernel.workspaces.create_if_missing(
        project_id=project_id,
        artifact_type="functional-architecture",
        actor=actor(),
    )
    assert again["workspace"]["workspaceId"] == created["workspace"]["workspaceId"]
