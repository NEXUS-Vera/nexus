"""Shared helpers for board kernel tests."""

from __future__ import annotations

import copy
from typing import Any

from nexus_board.ids import new_id, utc_now_iso
from nexus_board.kernel import build_project_kernel
from nexus_persistence import InMemoryKernelStore, InMemoryProjectStore


def actor(actor_type: str = "user") -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "actorId": new_id("actor"),
        "actorType": actor_type,
        "displayName": actor_type,
    }


def content_for(atype: str) -> dict[str, Any]:
    if atype == "project-brief":
        return {
            "title": "Brief",
            "summary": "Summary",
            "goals": ["g1"],
            "constraints": [],
            "successCriteria": [],
        }
    if atype == "requirement-set":
        return {
            "requirements": [
                {
                    "requirementId": new_id("req"),
                    "statement": "Must sample temperature",
                    "priority": "must",
                    "status": "proposed",
                }
            ]
        }
    if atype == "functional-architecture":
        return {
            "architectureId": new_id("arch"),
            "summary": "Architecture",
            "nodes": [],
            "edges": [],
            "interfaces": [],
        }
    if atype == "next-action":
        return {
            "title": "Confirm constraints",
            "priority": "high",
            "recommendedAction": "Confirm sampling constraints",
            "blockingIssueIds": [],
            "openQuestionIds": [],
        }
    return {
        "selectionState": "draft",
        "candidateCount": 0,
        "constraintSummary": "Deferred",
        "unresolvedCompatibilityChecks": [],
        "approvalStatus": "not-required",
    }


def minimal_package(project_id: str | None = None) -> dict[str, Any]:
    project_id = project_id or new_id("proj")
    turn_id = new_id("turn")
    route_id = new_id("route")
    run_id = new_id("run")
    now = utc_now_iso()
    arts = []
    for atype in [
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "next-action",
    ]:
        arts.append(
            {
                "schemaVersion": "1.0.0",
                "artifactId": new_id("art"),
                "projectId": project_id,
                "artifactType": atype,
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
                "content": content_for(atype),
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "project": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "title": "Kernel Test Project",
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
            "actor": actor(),
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
            "workflowType": "embedded-project-initialization",
            "projectId": project_id,
            "turnId": turn_id,
            "runStatus": "completed",
            "stepRecords": [
                {
                    "stepId": "s1",
                    "stepType": "complete-workflow",
                    "status": "completed",
                    "attempt": 1,
                }
            ],
            "startTime": now,
            "endTime": now,
            "warnings": [],
            "errorReferences": [],
        },
        "artifacts": arts,
        "validationIssues": [],
        "openQuestions": [],
        "veraResponse": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "turnId": turn_id,
            "userFacingMessage": "ok",
            "createdAt": now,
            "artifactReferences": [
                {
                    "artifactType": a["artifactType"],
                    "artifactId": a["artifactId"],
                    "artifactVersion": 1,
                    "contentSchemaVersion": "1.0.0",
                }
                for a in arts
            ],
            "openQuestionReferences": [],
            "validationIssueReferences": [],
            "nextActionReferences": [],
        },
    }


def build_test_kernel(
    *,
    autonomy_mode: str = "collaborate",
    capability_executors: dict[str, Any] | None = None,
) -> tuple[Any, InMemoryProjectStore, InMemoryKernelStore, str]:
    project_store = InMemoryProjectStore()
    kernel_store = InMemoryKernelStore(project_store=project_store)
    package = minimal_package()
    package["project"]["autonomyMode"] = autonomy_mode
    project_store.save_initialization_package(copy.deepcopy(package))
    project_id = package["project"]["projectId"]
    kernel = build_project_kernel(
        kernel_store,
        project_store=project_store,
        capability_executors=capability_executors,
    )
    return kernel, project_store, kernel_store, project_id


def cmd(
    *,
    command_type: str,
    project_id: str,
    artifact_id: str,
    workspace_id: str | None = None,
    base_artifact_version: int = 1,
    base_project_state_version: int = 1,
    input_data: dict[str, Any] | None = None,
    requested_by: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "commandId": new_id("cmd"),
        "commandType": command_type,
        "projectId": project_id,
        "artifactId": artifact_id,
        "baseArtifactVersion": base_artifact_version,
        "baseProjectStateVersion": base_project_state_version,
        "requestedBy": requested_by or actor(),
        "requestedAt": utc_now_iso(),
        "input": input_data or {},
    }
    if workspace_id is not None:
        body["workspaceId"] = workspace_id
    return body


def acquire_edit_lease(
    kernel: Any,
    *,
    project_id: str,
    artifact_id: str,
    workspace_id: str,
    requested_by: dict[str, Any] | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Acquire a draft edit lease for subsequent update-draft calls."""
    editor = requested_by or actor()
    input_data: dict[str, Any] = {}
    if ttl_seconds is not None:
        input_data["ttlSeconds"] = ttl_seconds
    result: dict[str, Any] = kernel.dispatch(
        cmd(
            command_type="workspace.acquire-edit-lease",
            project_id=project_id,
            artifact_id=artifact_id,
            workspace_id=workspace_id,
            input_data=input_data,
            requested_by=editor,
        )
    )
    return result
