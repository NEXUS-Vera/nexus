"""Behavioral contract tests for ProjectPackageStore implementations."""

from __future__ import annotations

import copy
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from nexus_persistence.errors import ProjectNotFoundError, ProjectPersistenceError
from nexus_persistence.factory import build_project_store
from nexus_persistence.memory.store import InMemoryProjectStore
from nexus_persistence.protocol import ProjectPackageStore

try:
    from nexus_persistence.postgres.models import Base
    from nexus_persistence.postgres.session import create_db_engine, create_session_factory
    from nexus_persistence.postgres.store import PostgresProjectStore
except Exception:  # noqa: BLE001
    PostgresProjectStore = None  # type: ignore[misc, assignment]


def _actor() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "actorId": "actor_TESTUSER0000000001",
        "actorType": "user",
        "displayName": "User",
    }


def _minimal_package(project_id: str = "proj_TESTPROJECT00000001") -> dict[str, Any]:
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
                "content": _content_for(atype),
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "project": {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "title": "Test Project",
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
            "rawUserMessage": "I want to build a greenhouse monitor.",
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
            "userFacingMessage": "Project initialized.",
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


def _content_for(atype: str) -> dict[str, Any]:
    if atype == "project-brief":
        return {
            "summary": "Test brief",
            "problemStatement": "Test problem",
            "goals": ["Goal"],
            "constraints": [],
            "assumptions": [],
            "outOfScope": [],
            "successCriteria": ["Success"],
        }
    if atype == "requirement-set":
        return {"requirements": []}
    if atype == "functional-architecture":
        return {
            "architectureMaturity": "functional",
            "nodes": [],
            "edges": [],
            "requirementCoverage": [],
        }
    return {
        "actionType": "ask-user",
        "title": "Next",
        "rationale": "Because",
        "completionCriteria": ["Done"],
        "blockingIssueIds": [],
        "relatedOpenQuestionIds": [],
        "relatedRequirementIds": [],
    }


@pytest.fixture
def memory_store() -> InMemoryProjectStore:
    return InMemoryProjectStore()


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest) -> Iterator[ProjectPackageStore]:
    """Run every behavioural contract test against each supported local backend."""
    if request.param == "memory":
        yield InMemoryProjectStore()
        return
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield PostgresProjectStore(create_session_factory(engine))
    finally:
        engine.dispose()


def test_save_and_get_current_state(store: ProjectPackageStore) -> None:
    package = _minimal_package()
    store.save_initialization_package(package)
    state = store.get_current_state(package["project"]["projectId"])
    assert state["project"]["projectId"] == package["project"]["projectId"]
    assert len(state["artifacts"]) == 4
    assert len(store.list_dependencies(package["project"]["projectId"])) >= 1


def test_project_not_found(store: ProjectPackageStore) -> None:
    with pytest.raises(ProjectNotFoundError) as exc:
        store.get_current_state("proj_DOESNOTEXIST00001")
    assert exc.value.code == "PROJECT_NOT_FOUND"


def test_immutable_artifact_history(store: ProjectPackageStore) -> None:
    package = _minimal_package()
    store.save_initialization_package(package)
    project_id = package["project"]["projectId"]
    old_req = next(a for a in package["artifacts"] if a["artifactType"] == "requirement-set")
    new_turn = "turn_TESTTURN00000000002"
    new_run = "run_TESTRUN000000000002"
    new_req = copy.deepcopy(old_req)
    new_req["artifactId"] = "art_TESTREQV2XXXXXXXXXXXX"
    new_req["artifactVersion"] = 2
    new_req["supersedesArtifactId"] = old_req["artifactId"]
    new_req["supersedesArtifactVersion"] = 1
    new_req["sourceTurnId"] = new_turn
    new_req["workflowRunId"] = new_run
    new_req["lifecycleStatus"] = "ready"

    mod = copy.deepcopy(package)
    mod["project"]["currentStateVersion"] = 2
    mod["project"]["updatedAt"] = "2026-07-29T01:00:00Z"
    mod["project"]["currentArtifactReferences"] = [
        ref
        if ref["artifactType"] != "requirement-set"
        else {
            "artifactType": "requirement-set",
            "artifactId": new_req["artifactId"],
            "artifactVersion": 2,
            "contentSchemaVersion": "1.0.0",
        }
        for ref in mod["project"]["currentArtifactReferences"]
    ]
    mod["userTurn"] = {
        "schemaVersion": "1.0.0",
        "turnId": new_turn,
        "projectId": project_id,
        "rawUserMessage": "It should run for six months on battery.",
        "actor": _actor(),
        "timestamp": "2026-07-29T01:00:00Z",
        "parentTurnId": package["userTurn"]["turnId"],
    }
    mod["turnRoute"] = {
        **package["turnRoute"],
        "routeId": "route_TESTROUTE000000002",
        "turnId": new_turn,
        "routeType": "project-modification",
        "projectOperation": "change-requirement",
    }
    mod["workflowRun"] = {
        **package["workflowRun"],
        "workflowRunId": new_run,
        "turnId": new_turn,
        "workflowType": "embedded-project-modification",
        "startTime": "2026-07-29T01:00:00Z",
        "endTime": "2026-07-29T01:00:01Z",
    }
    mod["artifacts"] = [
        new_req if a["artifactType"] == "requirement-set" else a for a in package["artifacts"]
    ]
    mod["veraResponse"] = {
        **package["veraResponse"],
        "turnId": new_turn,
        "userFacingMessage": "Updated runtime requirement.",
        "createdAt": "2026-07-29T01:00:01Z",
    }

    store.save_modification_package(mod, new_artifact_revisions=[new_req])
    history = store.get_history(project_id)
    req_revs = [r for r in history["artifactRevisions"] if r["artifactType"] == "requirement-set"]
    assert {r["artifactVersion"] for r in req_revs} == {1, 2}
    current = store.get_artifacts(project_id)
    cur_req = next(a for a in current if a["artifactType"] == "requirement-set")
    assert cur_req["artifactVersion"] == 2
    v1 = store.get_artifact(project_id, "requirement-set", version=1)
    assert v1["artifactId"] == old_req["artifactId"]


def test_cross_project_isolation(store: ProjectPackageStore) -> None:
    a = _minimal_package("proj_TESTPROJECTAAAA0001")
    b = _minimal_package("proj_TESTPROJECTBBBB0001")
    # uniquify nested IDs for b
    b["userTurn"]["turnId"] = "turn_TESTTURNBBBB00000001"
    b["userTurn"]["projectId"] = b["project"]["projectId"]
    b["turnRoute"]["routeId"] = "route_TESTROUTEBBBB00001"
    b["turnRoute"]["turnId"] = b["userTurn"]["turnId"]
    b["workflowRun"]["workflowRunId"] = "run_TESTRUNBBBB00000001"
    b["workflowRun"]["projectId"] = b["project"]["projectId"]
    b["workflowRun"]["turnId"] = b["userTurn"]["turnId"]
    for art in b["artifacts"]:
        art["projectId"] = b["project"]["projectId"]
        art["artifactId"] = art["artifactId"].replace("TESTART", "TESTBBB")
        art["sourceTurnId"] = b["userTurn"]["turnId"]
        art["workflowRunId"] = b["workflowRun"]["workflowRunId"]
    for ref in b["project"]["currentArtifactReferences"]:
        ref["artifactId"] = next(
            a["artifactId"] for a in b["artifacts"] if a["artifactType"] == ref["artifactType"]
        )
    b["veraResponse"]["projectId"] = b["project"]["projectId"]
    b["veraResponse"]["turnId"] = b["userTurn"]["turnId"]

    store.save_initialization_package(a)
    store.save_initialization_package(b)
    assert (
        store.get_current_state(a["project"]["projectId"])["project"]["projectId"]
        != b["project"]["projectId"]
    )


def test_memory_rollback_on_failure(store: ProjectPackageStore) -> None:
    package = _minimal_package()
    store.save_initialization_package(package)
    project_id = package["project"]["projectId"]
    before = store.get_current_state(project_id)
    bad = copy.deepcopy(package)
    bad["project"]["projectId"] = project_id
    # Force failure by omitting userTurn
    bad.pop("userTurn")
    with pytest.raises(ProjectPersistenceError):
        store.save_modification_package(bad)
    after = store.get_current_state(project_id)
    assert after["project"]["currentStateVersion"] == before["project"]["currentStateVersion"]


@pytest.mark.skipif(
    not os.environ.get("NEXUS_TEST_DATABASE_URL") or PostgresProjectStore is None,
    reason="Postgres integration requires NEXUS_TEST_DATABASE_URL",
)
def test_postgres_store_contract() -> None:
    url = os.environ["NEXUS_TEST_DATABASE_URL"]
    engine = create_db_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    pg_store = PostgresProjectStore(create_session_factory(engine))
    package = _minimal_package("proj_TESTPGPROJECT000001")
    # uniquify
    package["userTurn"]["projectId"] = package["project"]["projectId"]
    for art in package["artifacts"]:
        art["projectId"] = package["project"]["projectId"]
    package["workflowRun"]["projectId"] = package["project"]["projectId"]
    package["veraResponse"]["projectId"] = package["project"]["projectId"]
    pg_store.save_initialization_package(package)
    state = pg_store.get_current_state(package["project"]["projectId"])
    assert len(state["artifacts"]) == 4


def test_sqlite_store_persists_across_connections(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'nexus.db'}"
    package = _minimal_package("proj_TESTSQLITEFILE00001")
    project_id = package["project"]["projectId"]

    writer = build_project_store(backend="sqlite", database_url=database_url)
    writer.save_initialization_package(package)
    del writer

    reader = build_project_store(backend="sqlite", database_url=database_url)
    state = reader.get_current_state(project_id)

    assert state["project"] == package["project"]
    assert state["userTurn"] == package["userTurn"]
    assert state["artifacts"] == package["artifacts"]
