"""Project package store protocol."""

from __future__ import annotations

from typing import Any, Protocol


class ProjectPackageStore(Protocol):
    def save_initialization_package(self, package: dict[str, Any]) -> None:
        """Atomically persist a validated initialization package."""

    def save_modification_package(
        self,
        package: dict[str, Any],
        *,
        dependencies: list[dict[str, Any]] | None = None,
        new_artifact_revisions: list[dict[str, Any]] | None = None,
    ) -> None:
        """Atomically persist a validated modification package and revisions."""

    def get_current_state(self, project_id: str) -> dict[str, Any]:
        """Return the current project package (ProjectCurrentState shape)."""

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        """Return current artifact revisions only."""

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Return current or specific artifact revision."""

    def get_history(self, project_id: str, *, limit: int = 100) -> dict[str, Any]:
        """Return lightweight project history."""

    def list_dependencies(self, project_id: str) -> list[dict[str, Any]]:
        """Return artifact dependency records for the project."""
