"""PostgreSQL-backed project package store."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus_persistence.dependencies import seed_default_dependencies
from nexus_persistence.errors import (
    ArtifactNotFoundError,
    ArtifactVersionNotFoundError,
    ProjectNotFoundError,
    ProjectPersistenceError,
)
from nexus_persistence.postgres.models import (
    ArtifactDependencyRow,
    ArtifactRevisionRow,
    OpenQuestionRow,
    ProjectRow,
    TurnRouteRow,
    UserTurnRow,
    ValidationIssueRow,
    VeraResponseRow,
    WorkflowRunRow,
)


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class PostgresProjectStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save_initialization_package(self, package: dict[str, Any]) -> None:
        try:
            with self._session_factory() as session:
                try:
                    self._write_package(session, package)

                    session.commit()
                except Exception:
                    session.rollback()
                    raise
        except ProjectPersistenceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProjectPersistenceError("Failed to persist project package.") from exc

    def save_modification_package(
        self,
        package: dict[str, Any],
        *,
        dependencies: list[dict[str, Any]] | None = None,
        new_artifact_revisions: list[dict[str, Any]] | None = None,
    ) -> None:
        project_id = package["project"]["projectId"]
        try:
            with self._session_factory() as session:
                try:
                    exists = session.get(ProjectRow, project_id)
                    if exists is None:
                        raise ProjectNotFoundError(f"Project not found: {project_id}")
                    for art in new_artifact_revisions or []:
                        self._upsert_artifact(session, art)
                    self._write_package(session, package)
                    if dependencies is not None:
                        existing = session.scalars(
                            select(ArtifactDependencyRow).where(
                                ArtifactDependencyRow.project_id == project_id
                            )
                        ).all()
                        for row in existing:
                            session.delete(row)
                        for dep in dependencies:
                            session.add(
                                ArtifactDependencyRow(
                                    dependency_id=dep["dependencyId"],
                                    project_id=project_id,
                                    payload=dep,
                                    created_at=_parse_dt(dep["createdAt"]),
                                )
                            )
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
        except (ProjectNotFoundError, ProjectPersistenceError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProjectPersistenceError("Failed to persist project modification.") from exc

    def get_current_state(self, project_id: str) -> dict[str, Any]:
        try:
            with self._session_factory() as session:
                project_row = session.get(ProjectRow, project_id)
                if project_row is None:
                    raise ProjectNotFoundError(f"Project not found: {project_id}")
                turns = session.scalars(
                    select(UserTurnRow)
                    .where(UserTurnRow.project_id == project_id)
                    .order_by(UserTurnRow.timestamp.asc())
                ).all()
                if not turns:
                    raise ProjectNotFoundError(f"Project has no turns: {project_id}")
                latest = turns[-1]
                route = session.scalars(
                    select(TurnRouteRow).where(TurnRouteRow.turn_id == latest.turn_id)
                ).first()
                run = session.scalars(
                    select(WorkflowRunRow).where(WorkflowRunRow.turn_id == latest.turn_id)
                ).first()
                vera = session.scalars(
                    select(VeraResponseRow).where(VeraResponseRow.turn_id == latest.turn_id)
                ).first()
                if route is None or run is None or vera is None:
                    raise ProjectPersistenceError("Project package is incomplete.")
                artifacts = self._current_artifacts(session, project_row.payload)
                issues = [
                    row.payload
                    for row in session.scalars(
                        select(ValidationIssueRow).where(
                            ValidationIssueRow.project_id == project_id
                        )
                    ).all()
                ]
                questions = [
                    row.payload
                    for row in session.scalars(
                        select(OpenQuestionRow).where(OpenQuestionRow.project_id == project_id)
                    ).all()
                ]
                deps = [
                    row.payload
                    for row in session.scalars(
                        select(ArtifactDependencyRow).where(
                            ArtifactDependencyRow.project_id == project_id
                        )
                    ).all()
                ]
                return {
                    "schemaVersion": "1.0.0",
                    "project": project_row.payload,
                    "userTurn": latest.payload,
                    "turnRoute": route.payload,
                    "workflowRun": run.payload,
                    "artifacts": artifacts,
                    "validationIssues": issues,
                    "openQuestions": questions,
                    "veraResponse": vera.payload,
                    "dependencies": deps,
                    "previousTurnIds": [t.turn_id for t in turns[:-1]],
                }
        except (ProjectNotFoundError, ProjectPersistenceError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProjectPersistenceError("Failed to retrieve project.") from exc

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        state = self.get_current_state(project_id)
        return list(state["artifacts"])

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            if session.get(ProjectRow, project_id) is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            if version is None:
                for art in self.get_artifacts(project_id):
                    if art["artifactType"] == artifact_type:
                        return art
                raise ArtifactNotFoundError(f"Artifact type not found: {artifact_type}")
            row = session.scalars(
                select(ArtifactRevisionRow).where(
                    ArtifactRevisionRow.project_id == project_id,
                    ArtifactRevisionRow.artifact_type == artifact_type,
                    ArtifactRevisionRow.artifact_version == version,
                )
            ).first()
            if row is None:
                raise ArtifactVersionNotFoundError(
                    f"Artifact version not found: {artifact_type} v{version}"
                )
            return row.payload

    def get_history(self, project_id: str, *, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(limit, 500))
        with self._session_factory() as session:
            if session.get(ProjectRow, project_id) is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            turns = session.scalars(
                select(UserTurnRow)
                .where(UserTurnRow.project_id == project_id)
                .order_by(UserTurnRow.timestamp.asc())
            ).all()[-limit:]
            turn_items = [
                {
                    "turnId": t.turn_id,
                    "timestamp": t.payload["timestamp"],
                    "rawUserMessage": t.payload["rawUserMessage"],
                }
                for t in turns
            ]
            workflow_runs = []
            vera_responses = []
            for t in turns:
                run = session.scalars(
                    select(WorkflowRunRow).where(WorkflowRunRow.turn_id == t.turn_id)
                ).first()
                vera = session.scalars(
                    select(VeraResponseRow).where(VeraResponseRow.turn_id == t.turn_id)
                ).first()
                if run:
                    workflow_runs.append(
                        {
                            "workflowRunId": run.run_id,
                            "turnId": t.turn_id,
                            "workflowType": run.payload["workflowType"],
                            "status": run.payload["runStatus"],
                            "startedAt": run.payload["startTime"],
                            "completedAt": run.payload.get("completionTime")
                            or run.payload.get("endTime"),
                        }
                    )
                if vera:
                    vera_responses.append(
                        {
                            "turnId": t.turn_id,
                            "timestamp": vera.payload.get("createdAt") or t.payload["timestamp"],
                            "userFacingMessage": vera.payload["userFacingMessage"],
                        }
                    )
            revisions = []
            for row in session.scalars(
                select(ArtifactRevisionRow)
                .where(ArtifactRevisionRow.project_id == project_id)
                .order_by(
                    ArtifactRevisionRow.artifact_type.asc(),
                    ArtifactRevisionRow.artifact_version.asc(),
                )
            ).all():
                item = {
                    "artifactId": row.artifact_id,
                    "artifactType": row.artifact_type,
                    "artifactVersion": row.artifact_version,
                    "lifecycleStatus": row.payload["lifecycleStatus"],
                    "createdAt": row.payload["createdAt"],
                    "sourceTurnId": row.source_turn_id,
                }
                if row.supersedes_artifact_id:
                    item["supersedesArtifactId"] = row.supersedes_artifact_id
                    item["supersedesArtifactVersion"] = row.payload.get("supersedesArtifactVersion")
                revisions.append(item)
            return {
                "schemaVersion": "1.0.0",
                "projectId": project_id,
                "turns": turn_items,
                "workflowRuns": workflow_runs,
                "artifactRevisions": revisions[-limit:],
                "veraResponses": vera_responses,
            }

    def list_dependencies(self, project_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            if session.get(ProjectRow, project_id) is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            return [
                row.payload
                for row in session.scalars(
                    select(ArtifactDependencyRow).where(
                        ArtifactDependencyRow.project_id == project_id
                    )
                ).all()
            ]

    def save_workflow_run(self, workflow_run: dict[str, Any]) -> None:
        with self._session_factory() as session:
            try:
                if session.get(WorkflowRunRow, workflow_run["workflowRunId"]) is None:
                    session.add(
                        WorkflowRunRow(
                            run_id=workflow_run["workflowRunId"],
                            project_id=workflow_run["projectId"],
                            turn_id=workflow_run["turnId"],
                            payload=workflow_run,
                        )
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def _write_package(self, session: Session, package: dict[str, Any]) -> None:
        project = package["project"]
        turn = package["userTurn"]
        route = package["turnRoute"]
        run = package["workflowRun"]
        artifacts = package["artifacts"]
        issues = package.get("validationIssues") or []
        questions = package.get("openQuestions") or []
        vera = package["veraResponse"]
        project_id = project["projectId"]

        row = session.get(ProjectRow, project_id)
        if row is None:
            session.add(
                ProjectRow(
                    project_id=project_id,
                    title=project["title"],
                    domain=project["domain"],
                    project_phase=project["projectPhase"],
                    autonomy_mode=project["autonomyMode"],
                    current_state_version=int(project["currentStateVersion"]),
                    payload=project,
                    created_at=_parse_dt(project["createdAt"]),
                    updated_at=_parse_dt(project["updatedAt"]),
                )
            )
        else:
            row.title = project["title"]
            row.project_phase = project["projectPhase"]
            row.autonomy_mode = project["autonomyMode"]
            row.current_state_version = int(project["currentStateVersion"])
            row.payload = project
            row.updated_at = _parse_dt(project["updatedAt"])

        # Ensure project exists before turns (FK).
        session.flush()

        if session.get(UserTurnRow, turn["turnId"]) is None:
            session.add(
                UserTurnRow(
                    turn_id=turn["turnId"],
                    project_id=project_id,
                    parent_turn_id=turn.get("parentTurnId"),
                    timestamp=_parse_dt(turn["timestamp"]),
                    payload=turn,
                )
            )
        # Flush so turn_routes / workflow_runs FK checks see the new turn row.
        session.flush()
        if session.get(TurnRouteRow, route["routeId"]) is None:
            session.add(
                TurnRouteRow(
                    route_id=route["routeId"],
                    project_id=project_id,
                    turn_id=turn["turnId"],
                    payload=route,
                )
            )
        if session.get(WorkflowRunRow, run["workflowRunId"]) is None:
            session.add(
                WorkflowRunRow(
                    run_id=run["workflowRunId"],
                    project_id=project_id,
                    turn_id=turn["turnId"],
                    payload=run,
                )
            )

        for art in artifacts:
            self._upsert_artifact(session, art)

        for old_issue in session.scalars(
            select(ValidationIssueRow).where(ValidationIssueRow.project_id == project_id)
        ).all():
            session.delete(old_issue)
        for old_question in session.scalars(
            select(OpenQuestionRow).where(OpenQuestionRow.project_id == project_id)
        ).all():
            session.delete(old_question)

        for issue in issues:
            session.add(
                ValidationIssueRow(issue_id=issue["issueId"], project_id=project_id, payload=issue)
            )
        for question in questions:
            session.add(
                OpenQuestionRow(
                    question_id=question["questionId"],
                    project_id=project_id,
                    status=question["status"],
                    payload=question,
                )
            )

        vera_key = vera.get("responseId") or turn["turnId"]
        existing_vera = session.get(VeraResponseRow, vera_key)
        if existing_vera is None:
            session.add(
                VeraResponseRow(
                    response_key=vera_key,
                    project_id=project_id,
                    turn_id=turn["turnId"],
                    payload=vera,
                )
            )

        dep_count = session.scalars(
            select(ArtifactDependencyRow).where(ArtifactDependencyRow.project_id == project_id)
        ).first()
        if dep_count is None:
            deps = package.get("dependencies") or seed_default_dependencies(project_id)
            for dep in deps:
                session.add(
                    ArtifactDependencyRow(
                        dependency_id=dep["dependencyId"],
                        project_id=project_id,
                        payload=dep,
                        created_at=_parse_dt(dep["createdAt"]),
                    )
                )

    def _upsert_artifact(self, session: Session, art: dict[str, Any]) -> None:
        existing = session.get(ArtifactRevisionRow, art["artifactId"])
        if existing is not None:
            return
        session.add(
            ArtifactRevisionRow(
                artifact_id=art["artifactId"],
                project_id=art["projectId"],
                artifact_type=art["artifactType"],
                artifact_version=int(art["artifactVersion"]),
                source_turn_id=art["sourceTurnId"],
                workflow_run_id=art["workflowRunId"],
                supersedes_artifact_id=art.get("supersedesArtifactId"),
                created_at=_parse_dt(art["createdAt"]),
                payload=art,
            )
        )

    def _current_artifacts(
        self, session: Session, project_payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for ref in project_payload.get("currentArtifactReferences", []):
            row = session.scalars(
                select(ArtifactRevisionRow).where(
                    ArtifactRevisionRow.project_id == project_payload["projectId"],
                    ArtifactRevisionRow.artifact_type == ref["artifactType"],
                    ArtifactRevisionRow.artifact_version == int(ref["artifactVersion"]),
                )
            ).first()
            if row is None:
                row = session.get(ArtifactRevisionRow, ref["artifactId"])
            if row is None:
                raise ArtifactNotFoundError(
                    f"Current artifact missing for type {ref['artifactType']}"
                )
            result.append(row.payload)
        return result
