"""In-memory project package store with atomic save semantics."""

from __future__ import annotations

import copy
import threading
from typing import Any

from nexus_persistence.dependencies import seed_default_dependencies
from nexus_persistence.errors import (
    ArtifactNotFoundError,
    ArtifactVersionNotFoundError,
    ProjectNotFoundError,
    ProjectPersistenceError,
)


def _require(package: dict[str, Any], key: str) -> Any:
    if key not in package:
        raise ProjectPersistenceError(f"Package missing required field: {key}")
    return package[key]


class InMemoryProjectStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._projects: dict[str, dict[str, Any]] = {}
        self._turns: dict[str, dict[str, Any]] = {}
        self._turns_by_project: dict[str, list[str]] = {}
        self._routes: dict[str, dict[str, Any]] = {}
        self._routes_by_turn: dict[str, str] = {}
        self._runs: dict[str, dict[str, Any]] = {}
        self._runs_by_turn: dict[str, str] = {}
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._artifact_index: dict[tuple[str, str, int], str] = {}
        self._issues: dict[str, dict[str, Any]] = {}
        self._issues_by_project: dict[str, list[str]] = {}
        self._questions: dict[str, dict[str, Any]] = {}
        self._questions_by_project: dict[str, list[str]] = {}
        self._vera: dict[str, dict[str, Any]] = {}
        self._vera_by_turn: dict[str, str] = {}
        self._dependencies: dict[str, list[dict[str, Any]]] = {}

    def save_initialization_package(self, package: dict[str, Any]) -> None:
        with self._lock:
            try:
                self._commit_package(copy.deepcopy(package), replace_issues=True)
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
        with self._lock:
            project = _require(package, "project")
            project_id = project["projectId"]
            if project_id not in self._projects:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            # Snapshot for rollback
            snapshot = self._snapshot()
            try:
                for art in new_artifact_revisions or []:
                    self._store_artifact(copy.deepcopy(art))
                self._commit_package(
                    copy.deepcopy(package),
                    replace_issues=True,
                    skip_existing_artifacts=True,
                )
                if dependencies is not None:
                    self._dependencies[project_id] = copy.deepcopy(dependencies)
            except Exception as exc:  # noqa: BLE001
                self._restore(snapshot)
                if isinstance(exc, ProjectNotFoundError | ProjectPersistenceError):
                    raise
                raise ProjectPersistenceError("Failed to persist project modification.") from exc

    def get_current_state(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            turn_ids = self._turns_by_project.get(project_id, [])
            if not turn_ids:
                raise ProjectNotFoundError(f"Project has no turns: {project_id}")
            turn_id = turn_ids[-1]
            turn = self._turns[turn_id]
            route_id = self._routes_by_turn[turn_id]
            run_id = self._runs_by_turn[turn_id]
            vera_key = self._vera_by_turn[turn_id]
            artifacts = self.get_artifacts(project_id)
            issue_ids = self._issues_by_project.get(project_id, [])
            question_ids = self._questions_by_project.get(project_id, [])
            return {
                "schemaVersion": "1.0.0",
                "project": copy.deepcopy(project),
                "userTurn": copy.deepcopy(turn),
                "turnRoute": copy.deepcopy(self._routes[route_id]),
                "workflowRun": copy.deepcopy(self._runs[run_id]),
                "artifacts": copy.deepcopy(artifacts),
                "validationIssues": [copy.deepcopy(self._issues[i]) for i in issue_ids],
                "openQuestions": [copy.deepcopy(self._questions[q]) for q in question_ids],
                "veraResponse": copy.deepcopy(self._vera[vera_key]),
                "dependencies": copy.deepcopy(self._dependencies.get(project_id, [])),
                "previousTurnIds": list(turn_ids[:-1]),
            }

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            result: list[dict[str, Any]] = []
            for ref in project.get("currentArtifactReferences", []):
                key = (project_id, ref["artifactType"], int(ref["artifactVersion"]))
                art_id = self._artifact_index.get(key)
                if art_id is None:
                    art_id = ref.get("artifactId")
                art = self._artifacts.get(art_id) if art_id else None
                if art is None:
                    raise ArtifactNotFoundError(
                        f"Current artifact missing for type {ref['artifactType']}"
                    )
                result.append(copy.deepcopy(art))
            return result

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if project_id not in self._projects:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            if version is None:
                for art in self.get_artifacts(project_id):
                    if art["artifactType"] == artifact_type:
                        return art
                raise ArtifactNotFoundError(f"Artifact type not found: {artifact_type}")
            key = (project_id, artifact_type, version)
            art_id = self._artifact_index.get(key)
            if art_id is None:
                raise ArtifactVersionNotFoundError(
                    f"Artifact version not found: {artifact_type} v{version}"
                )
            return copy.deepcopy(self._artifacts[art_id])

    def get_history(self, project_id: str, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            if project_id not in self._projects:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            limit = max(1, min(limit, 500))
            turn_ids = self._turns_by_project.get(project_id, [])[-limit:]
            turns = [
                {
                    "turnId": tid,
                    "timestamp": self._turns[tid]["timestamp"],
                    "rawUserMessage": self._turns[tid]["rawUserMessage"],
                }
                for tid in turn_ids
            ]
            workflow_runs = []
            vera_responses = []
            for tid in turn_ids:
                run = self._runs[self._runs_by_turn[tid]]
                workflow_runs.append(
                    {
                        "workflowRunId": run["workflowRunId"],
                        "turnId": tid,
                        "workflowType": run["workflowType"],
                        "status": run["runStatus"],
                        "startedAt": run["startTime"],
                        "completedAt": run.get("completionTime") or run.get("endTime"),
                    }
                )
                vera = self._vera[self._vera_by_turn[tid]]
                vera_responses.append(
                    {
                        "turnId": tid,
                        "timestamp": vera.get("createdAt") or self._turns[tid]["timestamp"],
                        "userFacingMessage": vera["userFacingMessage"],
                    }
                )
            revisions = []
            for art in self._artifacts.values():
                if art.get("projectId") != project_id:
                    continue
                revisions.append(
                    {
                        "artifactId": art["artifactId"],
                        "artifactType": art["artifactType"],
                        "artifactVersion": art["artifactVersion"],
                        "lifecycleStatus": art["lifecycleStatus"],
                        "createdAt": art["createdAt"],
                        "sourceTurnId": art["sourceTurnId"],
                        **(
                            {
                                "supersedesArtifactId": art["supersedesArtifactId"],
                                "supersedesArtifactVersion": art["supersedesArtifactVersion"],
                            }
                            if art.get("supersedesArtifactId")
                            else {}
                        ),
                    }
                )
            revisions.sort(key=lambda r: (r["artifactType"], r["artifactVersion"]))
            return {
                "schemaVersion": "1.0.0",
                "projectId": project_id,
                "turns": turns,
                "workflowRuns": workflow_runs,
                "artifactRevisions": revisions[-limit:],
                "veraResponses": vera_responses,
            }

    def list_dependencies(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            if project_id not in self._projects:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            return copy.deepcopy(self._dependencies.get(project_id, []))

    def save_workflow_run(self, workflow_run: dict[str, Any]) -> None:
        """Persist a standalone workflow run (e.g. failed initialization)."""
        with self._lock:
            self._runs[workflow_run["workflowRunId"]] = copy.deepcopy(workflow_run)
            turn_id = workflow_run.get("turnId")
            if turn_id:
                self._runs_by_turn[turn_id] = workflow_run["workflowRunId"]

    def _commit_package(
        self,
        package: dict[str, Any],
        *,
        replace_issues: bool,
        skip_existing_artifacts: bool = False,
    ) -> None:
        project = _require(package, "project")
        turn = _require(package, "userTurn")
        route = _require(package, "turnRoute")
        run = _require(package, "workflowRun")
        artifacts = _require(package, "artifacts")
        issues = package.get("validationIssues") or []
        questions = package.get("openQuestions") or []
        vera = _require(package, "veraResponse")
        project_id = project["projectId"]
        turn_id = turn["turnId"]

        self._projects[project_id] = project
        self._turns[turn_id] = turn
        self._turns_by_project.setdefault(project_id, [])
        if turn_id not in self._turns_by_project[project_id]:
            self._turns_by_project[project_id].append(turn_id)
        self._routes[route["routeId"]] = route
        self._routes_by_turn[turn_id] = route["routeId"]
        self._runs[run["workflowRunId"]] = run
        self._runs_by_turn[turn_id] = run["workflowRunId"]

        for art in artifacts:
            if skip_existing_artifacts and art["artifactId"] in self._artifacts:
                continue
            self._store_artifact(art)

        if replace_issues:
            for old in self._issues_by_project.get(project_id, []):
                self._issues.pop(old, None)
            self._issues_by_project[project_id] = []
            for old in self._questions_by_project.get(project_id, []):
                self._questions.pop(old, None)
            self._questions_by_project[project_id] = []

        for issue in issues:
            iid = issue["issueId"]
            self._issues[iid] = issue
            self._issues_by_project.setdefault(project_id, [])
            if iid not in self._issues_by_project[project_id]:
                self._issues_by_project[project_id].append(iid)
        for question in questions:
            qid = question["questionId"]
            self._questions[qid] = question
            self._questions_by_project.setdefault(project_id, [])
            if qid not in self._questions_by_project[project_id]:
                self._questions_by_project[project_id].append(qid)

        vera_key = vera.get("responseId") or turn_id
        self._vera[vera_key] = vera
        self._vera_by_turn[turn_id] = vera_key

        if project_id not in self._dependencies:
            deps = package.get("dependencies") or seed_default_dependencies(project_id)
            self._dependencies[project_id] = copy.deepcopy(deps)

    def _store_artifact(self, art: dict[str, Any]) -> None:
        art_id = art["artifactId"]
        key = (art["projectId"], art["artifactType"], int(art["artifactVersion"]))
        existing = self._artifact_index.get(key)
        if existing and existing != art_id:
            raise ProjectPersistenceError(
                f"Duplicate artifact version for {art['artifactType']} v{art['artifactVersion']}"
            )
        self._artifacts[art_id] = art
        self._artifact_index[key] = art_id

    def _snapshot(self) -> dict[str, Any]:
        return {
            "projects": copy.deepcopy(self._projects),
            "turns": copy.deepcopy(self._turns),
            "turns_by_project": copy.deepcopy(self._turns_by_project),
            "routes": copy.deepcopy(self._routes),
            "routes_by_turn": copy.deepcopy(self._routes_by_turn),
            "runs": copy.deepcopy(self._runs),
            "runs_by_turn": copy.deepcopy(self._runs_by_turn),
            "artifacts": copy.deepcopy(self._artifacts),
            "artifact_index": copy.deepcopy(self._artifact_index),
            "issues": copy.deepcopy(self._issues),
            "issues_by_project": copy.deepcopy(self._issues_by_project),
            "questions": copy.deepcopy(self._questions),
            "questions_by_project": copy.deepcopy(self._questions_by_project),
            "vera": copy.deepcopy(self._vera),
            "vera_by_turn": copy.deepcopy(self._vera_by_turn),
            "dependencies": copy.deepcopy(self._dependencies),
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self._projects = snapshot["projects"]
        self._turns = snapshot["turns"]
        self._turns_by_project = snapshot["turns_by_project"]
        self._routes = snapshot["routes"]
        self._routes_by_turn = snapshot["routes_by_turn"]
        self._runs = snapshot["runs"]
        self._runs_by_turn = snapshot["runs_by_turn"]
        self._artifacts = snapshot["artifacts"]
        self._artifact_index = snapshot["artifact_index"]
        self._issues = snapshot["issues"]
        self._issues_by_project = snapshot["issues_by_project"]
        self._questions = snapshot["questions"]
        self._questions_by_project = snapshot["questions_by_project"]
        self._vera = snapshot["vera"]
        self._vera_by_turn = snapshot["vera_by_turn"]
        self._dependencies = snapshot["dependencies"]
