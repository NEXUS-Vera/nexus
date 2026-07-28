"""In-memory repositories for fixture-backed initialization results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryInitializationStore:
    projects: dict[str, dict[str, Any]] = field(default_factory=dict)
    turns: dict[str, dict[str, Any]] = field(default_factory=dict)
    workflow_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    packages: dict[str, dict[str, Any]] = field(default_factory=dict)

    def save_project(self, project: dict[str, Any]) -> None:
        project_id = project["projectId"]
        self.projects[project_id] = project

    def save_turn(self, turn: dict[str, Any]) -> None:
        self.turns[turn["turnId"]] = turn

    def save_workflow_run(self, workflow_run: dict[str, Any]) -> None:
        self.workflow_runs[workflow_run["workflowRunId"]] = workflow_run

    def save_artifacts(self, artifacts: list[dict[str, Any]]) -> None:
        for artifact in artifacts:
            self.artifacts[artifact["artifactId"]] = artifact

    def save_package(self, project_id: str, package: dict[str, Any]) -> None:
        self.packages[project_id] = package

    def get_project_package(self, project_id: str) -> dict[str, Any] | None:
        return self.packages.get(project_id)
