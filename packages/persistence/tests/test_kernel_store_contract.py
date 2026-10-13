"""Contract tests for ProjectKernelStore implementations."""

from __future__ import annotations

import copy
import os
from typing import Any

import pytest
from nexus_persistence.errors import (
    LedgerImmutableError,
    ProjectStateConflictError,
    SnapshotImmutableError,
)
from nexus_persistence.memory.kernel_store import InMemoryKernelStore
from nexus_persistence.memory.store import InMemoryProjectStore

try:
    from nexus_persistence.postgres.kernel_store import PostgresKernelStore
    from nexus_persistence.postgres.models import Base
    from nexus_persistence.postgres.session import create_db_engine, create_session_factory
    from nexus_persistence.postgres.store import PostgresProjectStore
except Exception:  # noqa: BLE001
    PostgresKernelStore = None  # type: ignore[misc, assignment]


def _actor() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "actorId": "actor_TESTUSER0000000001",
        "actorType": "user",
        "displayName": "User",
    }


def _minimal_package(project_id: str) -> dict[str, Any]:
    turn_id = "turn_TESTTURN00000000001"
    route_id = "route_TESTROUTE000000001"
    run_id = "run_TESTRUN000000000001"
    arts = []
    for i, atype in enumerate(
        ["project-brief", "requirement-set", "functional-architecture", "next-action"],
        start=1,
    ):
        arts.append(
            {
                "schemaVersion": "1.0.0",
                "artifactId": f"art_TESTART{atype.replace('-', '').upper()[:8]}{i:016d}",
                "projectId": project_id,
                "artifactType": atype,
                "artifactVersion": 1,
                "contentSchemaVersion": "1.0.0",
                "lifecycleStatus": "ready",
                "evidenceStatus": "unverified",
                "approvalStatus": "proposed",
                "createdBy": _actor(),
                "createdAt": "2026-07-29T00:00:00Z",
                "updatedAt": "2026-07-29T00:00:00Z",
                "sourceTurnId": turn_id,
                "workflowRunId": run_id,
                "content": {"title": atype},
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "project": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "title": "Kernel Store Project",
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
            "createdAt": "2026-07-29T00:00:00Z",
            "updatedAt": "2026-07-29T00:00:00Z",
        },
        "userTurn": {
            "schemaVersion": "1.0.0",
            "turnId": turn_id,
            "projectId": project_id,
            "rawUserMessage": "hi",
            "actor": _actor(),
            "timestamp": "2026-07-29T00:00:00Z",
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
            "reasons": ["fixture-test"],
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
            "startTime": "2026-07-29T00:00:00Z",
            "endTime": "2026-07-29T00:00:01Z",
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
            "createdAt": "2026-07-29T00:00:01Z",
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


@pytest.fixture(params=["memory", "postgres"])
def stores(request: pytest.FixtureRequest) -> Any:
    if request.param == "memory":
        memory_project = InMemoryProjectStore()
        yield memory_project, InMemoryKernelStore(project_store=memory_project)
        return
    url = os.environ.get("NEXUS_TEST_DATABASE_URL")
    if not url or PostgresKernelStore is None:
        pytest.skip("NEXUS_TEST_DATABASE_URL not set")
    engine = create_db_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    pg_project = PostgresProjectStore(factory)
    pg_kernel = PostgresKernelStore(factory, project_store=pg_project)
    yield pg_project, pg_kernel
    Base.metadata.drop_all(engine)


def test_immutable_snapshots_and_events(stores: Any) -> None:
    project_store, kernel_store = stores
    package = _minimal_package("proj_KERNELTEST00000001")
    project_store.save_initialization_package(copy.deepcopy(package))
    art = package["artifacts"][1]
    workspace = {
        "schemaVersion": "1.0.0",
        "workspaceId": "ws_KERNELTESTWORK000001",
        "projectId": package["project"]["projectId"],
        "artifactId": art["artifactId"],
        "artifactType": "requirement-set",
        "workspaceType": "structured-document",
        "status": "ready",
        "baseArtifactVersion": 1,
        "baseProjectStateVersion": 1,
        "createdBy": _actor(),
        "createdAt": "2026-08-04T12:00:00Z",
        "updatedAt": "2026-08-04T12:00:00Z",
        "runtimeCapabilityRequirements": [],
        "externalWorkspaceReferences": [],
    }
    draft = {
        "schemaVersion": "1.0.0",
        "workspaceId": workspace["workspaceId"],
        "draftVersion": 1,
        "baseArtifactVersion": 1,
        "baseProjectStateVersion": 1,
        "content": {"note": "d"},
        "validationState": "unvalidated",
        "createdAt": "2026-08-04T12:00:00Z",
        "updatedAt": "2026-08-04T12:00:00Z",
        "updatedBy": _actor(),
    }
    kernel_store.create_workspace(workspace, draft)
    snapshot = {
        "schemaVersion": "1.0.0",
        "snapshotId": "snap_KERNELTESTSNAP00001",
        "workspaceId": workspace["workspaceId"],
        "projectId": workspace["projectId"],
        "artifactId": art["artifactId"],
        "snapshotVersion": 1,
        "baseArtifactVersion": 1,
        "baseProjectStateVersion": 1,
        "content": {"kind": "structured", "structuredContent": {"note": "s"}},
        "contentDigest": "sha256:x",
        "createdBy": _actor(),
        "createdAt": "2026-08-04T12:00:00Z",
        "reason": "test",
    }
    kernel_store.create_snapshot(snapshot)
    with pytest.raises(SnapshotImmutableError):
        kernel_store.update_snapshot({**snapshot, "reason": "nope"})
    event = {
        "schemaVersion": "1.0.0",
        "eventId": "evt_KERNELTESTEVENT00001",
        "projectId": workspace["projectId"],
        "eventType": "workspace.snapshot-created",
        "occurredAt": "2026-08-04T12:00:00Z",
        "actor": _actor(),
        "subject": {"subjectType": "snapshot", "subjectId": snapshot["snapshotId"]},
        "payload": {"snapshotId": snapshot["snapshotId"]},
    }
    kernel_store.append_project_event(event)
    with pytest.raises(LedgerImmutableError):
        kernel_store.update_project_event(event)


def test_accept_transaction_rollback_on_conflict(stores: Any) -> None:
    project_store, kernel_store = stores
    package = _minimal_package("proj_KERNELTEST00000002")
    project_store.save_initialization_package(copy.deepcopy(package))
    art = package["artifacts"][1]
    proposal = {
        "schemaVersion": "1.0.0",
        "proposalId": "prop_KERNELTESTPROP00001",
        "projectId": package["project"]["projectId"],
        "artifactId": art["artifactId"],
        "artifactType": "requirement-set",
        "workspaceId": "ws_KERNELTESTWORK000002",
        "snapshotId": "snap_KERNELTESTSNAP00002",
        "baseArtifactVersion": 1,
        "baseProjectStateVersion": 99,
        "status": "proposed",
        "proposedBy": _actor(),
        "proposedAt": "2026-08-04T12:00:00Z",
        "consequenceLevel": "low",
        "approvalRequirement": {
            "schemaVersion": "1.0.0",
            "required": False,
            "reason": "low",
            "consequenceLevel": "low",
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": True,
        },
    }
    kernel_store.create_proposal(proposal)
    new_artifact = {
        **art,
        "artifactId": "art_KERNELTESTNEW00000001",
        "artifactVersion": 2,
        "supersedesArtifactId": art["artifactId"],
        "supersedesArtifactVersion": 1,
    }
    with pytest.raises(ProjectStateConflictError):
        kernel_store.accept_proposal_transaction(
            {
                "proposal": proposal,
                "new_artifact": new_artifact,
                "next_state_version": 2,
                "updated_at": "2026-08-04T12:01:00Z",
                "events": [],
                "graph_nodes": [],
                "graph_edges": [],
            }
        )
    still = project_store.get_artifact(package["project"]["projectId"], "requirement-set")
    assert still["artifactVersion"] == 1
    assert kernel_store.get_proposal(proposal["proposalId"])["status"] == "proposed"


def test_cross_project_isolation(stores: Any) -> None:
    project_store, kernel_store = stores
    p1 = _minimal_package("proj_KERNELTEST00000003")
    p2 = _minimal_package("proj_KERNELTEST00000004")
    # uniquify nested ids for second package
    p2["userTurn"]["turnId"] = "turn_TESTTURN00000000002"
    p2["userTurn"]["projectId"] = p2["project"]["projectId"]
    p2["turnRoute"]["routeId"] = "route_TESTROUTE000000002"
    p2["turnRoute"]["turnId"] = p2["userTurn"]["turnId"]
    p2["workflowRun"]["workflowRunId"] = "run_TESTRUN000000000002"
    p2["workflowRun"]["turnId"] = p2["userTurn"]["turnId"]
    p2["workflowRun"]["projectId"] = p2["project"]["projectId"]
    p2["veraResponse"]["turnId"] = p2["userTurn"]["turnId"]
    p2["veraResponse"]["projectId"] = p2["project"]["projectId"]
    for i, art in enumerate(p2["artifacts"], start=1):
        art["artifactId"] = f"art_TESTB{i:024d}"
        art["projectId"] = p2["project"]["projectId"]
        art["sourceTurnId"] = p2["userTurn"]["turnId"]
        art["workflowRunId"] = p2["workflowRun"]["workflowRunId"]
    p2["project"]["currentArtifactReferences"] = [
        {
            "artifactType": a["artifactType"],
            "artifactId": a["artifactId"],
            "artifactVersion": 1,
            "contentSchemaVersion": "1.0.0",
        }
        for a in p2["artifacts"]
    ]
    project_store.save_initialization_package(copy.deepcopy(p1))
    project_store.save_initialization_package(copy.deepcopy(p2))

    for package in (p1, p2):
        ws = {
            "schemaVersion": "1.0.0",
            "workspaceId": f"ws_{package['project']['projectId'][-16:]}XXXX",
            "projectId": package["project"]["projectId"],
            "artifactId": package["artifacts"][0]["artifactId"],
            "artifactType": "project-brief",
            "workspaceType": "structured-document",
            "status": "ready",
            "baseArtifactVersion": 1,
            "baseProjectStateVersion": 1,
            "createdBy": _actor(),
            "createdAt": "2026-08-04T12:00:00Z",
            "updatedAt": "2026-08-04T12:00:00Z",
            "runtimeCapabilityRequirements": [],
            "externalWorkspaceReferences": [],
        }
        draft = {
            "schemaVersion": "1.0.0",
            "workspaceId": ws["workspaceId"],
            "draftVersion": 1,
            "baseArtifactVersion": 1,
            "baseProjectStateVersion": 1,
            "content": {},
            "validationState": "unvalidated",
            "createdAt": "2026-08-04T12:00:00Z",
            "updatedAt": "2026-08-04T12:00:00Z",
            "updatedBy": _actor(),
        }
        kernel_store.create_workspace(ws, draft)
        kernel_store.append_project_event(
            {
                "schemaVersion": "1.0.0",
                "eventId": f"evt_{package['project']['projectId'][-16:]}XXXX",
                "projectId": package["project"]["projectId"],
                "eventType": "workspace.created",
                "occurredAt": "2026-08-04T12:00:00Z",
                "actor": _actor(),
                "subject": {"subjectType": "workspace", "subjectId": ws["workspaceId"]},
                "payload": {"workspaceId": ws["workspaceId"]},
            }
        )
        kernel_store.upsert_board_projection(
            {
                "schemaVersion": "1.0.0",
                "projectId": package["project"]["projectId"],
                "projectionVersion": 1,
                "projectStateVersion": 1,
                "projectTitle": package["project"]["title"],
                "currentPhase": "DEFINE",
                "artifactSummaries": [],
                "openQuestionCount": 0,
                "blockingIssueCount": 0,
                "recentExecutionSummaries": [],
                "recentChanges": [],
                "evidenceSummary": {
                    "totalCount": 0,
                    "unverifiedCount": 0,
                    "testedCount": 0,
                    "contradictedCount": 0,
                },
                "updatedAt": "2026-08-04T12:00:00Z",
            }
        )

    events1, _ = kernel_store.list_project_events(p1["project"]["projectId"])
    events2, _ = kernel_store.list_project_events(p2["project"]["projectId"])
    assert all(e["projectId"] == p1["project"]["projectId"] for e in events1)
    assert all(e["projectId"] == p2["project"]["projectId"] for e in events2)
    assert kernel_store.get_board_projection(p1["project"]["projectId"]) is not None
    assert (
        kernel_store.get_board_projection(p1["project"]["projectId"])["projectId"]
        != kernel_store.get_board_projection(p2["project"]["projectId"])["projectId"]
    )
