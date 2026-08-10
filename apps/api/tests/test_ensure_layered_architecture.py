"""API test: ensure layered architecture for a pre-Phase-13 persisted project."""

from __future__ import annotations

import copy

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import _store, app
from nexus_board.ids import new_id, utc_now_iso


def _actor() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "actorId": new_id("actor"),
        "actorType": "user",
        "displayName": "User",
    }


def _seed_pre_phase13_project() -> str:
    """Persist FA + component-plan without electrical/physical (pre-Phase-13 shape)."""
    project_id = new_id("proj")
    turn_id = new_id("turn")
    route_id = new_id("route")
    run_id = new_id("run")
    now = utc_now_iso()
    actor = _actor()

    def art(atype: str, content: dict) -> dict:
        return {
            "schemaVersion": "1.0.0",
            "artifactId": new_id("art"),
            "projectId": project_id,
            "artifactType": atype,
            "artifactVersion": 1,
            "contentSchemaVersion": "1.0.0",
            "lifecycleStatus": "ready",
            "evidenceStatus": "unverified",
            "approvalStatus": "proposed",
            "createdBy": actor,
            "createdAt": now,
            "updatedAt": now,
            "sourceTurnId": turn_id,
            "workflowRunId": run_id,
            "content": content,
        }

    arts = [
        art(
            "project-brief",
            {
                "title": "Brief",
                "summary": "Summary",
                "goals": ["g1"],
                "constraints": [],
                "successCriteria": [],
            },
        ),
        art(
            "requirement-set",
            {
                "requirements": [
                    {
                        "requirementId": "req_1",
                        "statement": "Must sense",
                        "priority": "must",
                        "status": "proposed",
                    }
                ]
            },
        ),
        art(
            "functional-architecture",
            {
                "architectureId": "arch_pre13_api",
                "summary": "Pre-13",
                "systemBoundary": "Boundary",
                "architectureMaturity": "provisional",
                "nodes": [
                    {
                        "nodeId": "node_SENSINGNODE0000000001",
                        "name": "Sensing",
                        "functionalType": "sensing",
                        "responsibilities": ["Sense"],
                        "satisfiesRequirementIds": ["req_1"],
                    },
                    {
                        "nodeId": "node_COMPUTENODE0000000001",
                        "name": "Compute",
                        "functionalType": "processing",
                        "responsibilities": ["Compute"],
                        "satisfiesRequirementIds": ["req_1"],
                    },
                ],
                "edges": [
                    {
                        "edgeId": "edge_1",
                        "fromNodeId": "node_SENSINGNODE0000000001",
                        "toNodeId": "node_COMPUTENODE0000000001",
                        "flowType": "data",
                        "description": "flow",
                    }
                ],
                "interfaces": [],
                "requirementCoverage": {"coveredRequirementIds": ["req_1"]},
            },
        ),
        art(
            "component-plan",
            {
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
                    }
                ],
                "candidates": [],
                "selectionDecisions": [],
            },
        ),
        art(
            "next-action",
            {
                "title": "Next",
                "priority": "high",
                "recommendedAction": "Continue",
                "blockingIssueIds": [],
                "openQuestionIds": [],
            },
        ),
    ]
    package = {
        "schemaVersion": "1.0.0",
        "project": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "title": "Pre-13 Project",
            "domain": "embedded-products",
            "projectPhase": "concept",
            "currentStateVersion": 1,
            "autonomyMode": "collaborate",
            "currentArtifactReferences": [
                {
                    "artifactType": a["artifactType"],
                    "artifactId": a["artifactId"],
                    "artifactVersion": 1,
                    "contentSchemaVersion": "1.0.0",
                }
                for a in arts
            ],
            "openQuestionReferences": [],
            "blockerOrValidationIssueReferences": [],
            "createdAt": now,
            "updatedAt": now,
        },
        "userTurn": {
            "schemaVersion": "1.0.0",
            "turnId": turn_id,
            "projectId": project_id,
            "rawUserMessage": "Initialize",
            "actor": actor,
            "timestamp": now,
        },
        "turnRoute": {
            "schemaVersion": "1.0.0",
            "routeId": route_id,
            "turnId": turn_id,
            "supported": True,
            "routeType": "project-initialization",
            "domain": "embedded-products",
            "projectOperation": "create-project",
            "complexity": "medium",
            "autonomyMode": "collaborate",
            "chairmanRequiredEventually": False,
            "reasons": ["test"],
        },
        "workflowRun": {
            "schemaVersion": "1.0.0",
            "workflowRunId": run_id,
            "turnId": turn_id,
            "projectId": project_id,
            "status": "completed",
            "startedAt": now,
            "completedAt": now,
        },
        "artifacts": arts,
        "validationIssues": [],
        "openQuestions": [],
        "veraResponse": {
            "schemaVersion": "1.0.0",
            "responseId": new_id("vera"),
            "turnId": turn_id,
            "userFacingMessage": "Pre-13 project seeded.",
            "createdArtifactReferences": [],
        },
    }
    _store.save_initialization_package(copy.deepcopy(package))
    return project_id


@pytest.mark.asyncio
async def test_ensure_layered_architecture_api_idempotent() -> None:
    project_id = _seed_pre_phase13_project()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        before = await client.get(f"/v1/projects/{project_id}")
        assert before.status_code == 200
        types_before = {a["artifactType"] for a in before.json()["artifacts"]}
        assert "electrical-architecture" not in types_before
        assert "physical-architecture" not in types_before

        first = await client.post(
            f"/v1/projects/{project_id}/ensure-layered-architecture",
            json={"requestedBy": _actor()},
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert set(body["createdArtifactTypes"]) == {
            "electrical-architecture",
            "physical-architecture",
        }
        types_after = {a["artifactType"] for a in body["currentState"]["artifacts"]}
        assert "electrical-architecture" in types_after
        assert "physical-architecture" in types_after

        second = await client.post(
            f"/v1/projects/{project_id}/ensure-layered-architecture",
            json={"requestedBy": _actor()},
        )
        assert second.status_code == 200, second.text
        assert second.json()["createdArtifactTypes"] == []

        ws = await client.get(
            f"/v1/projects/{project_id}/artifacts/functional-architecture/workspace"
        )
        assert ws.status_code == 200, ws.text
        assert ws.json()["workspace"]["artifactType"] == "functional-architecture"
