"""Project kernel wiring."""

from __future__ import annotations

from typing import Any

from nexus_board.registries.artifact_types import (
    ArtifactTypeRegistry,
    default_artifact_type_registry,
)
from nexus_board.registries.external_providers import (
    ExternalProviderRegistry,
    default_external_provider_registry,
)
from nexus_board.registries.runtime_capabilities import (
    RuntimeCapabilityRegistry,
    default_runtime_capability_registry,
)
from nexus_board.services.command_service import ArtifactCommandService
from nexus_board.services.execution_service import ExecutionService
from nexus_board.services.graph_service import ProjectGraphService
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService
from nexus_board.services.workspace_service import WorkspaceService


class ProjectKernel:
    def __init__(
        self,
        *,
        project_store: Any,
        kernel_store: Any,
        artifact_types: ArtifactTypeRegistry | None = None,
        capabilities: RuntimeCapabilityRegistry | None = None,
        providers: ExternalProviderRegistry | None = None,
    ) -> None:
        self.project_store = project_store
        self.kernel_store = kernel_store
        self.artifact_types = artifact_types or default_artifact_type_registry()
        self.capabilities = capabilities or default_runtime_capability_registry()
        self.providers = providers or default_external_provider_registry()
        self.ledger = ProjectLedgerService(kernel_store)
        self.graph = ProjectGraphService(kernel_store)
        self.projection = ProjectBoardProjectionService(kernel_store, project_store)
        self.workspaces = WorkspaceService(
            kernel_store,
            project_store,
            self.artifact_types,
            self.ledger,
            self.projection,
        )
        self.executions = ExecutionService(
            kernel_store,
            project_store,
            self.capabilities,
            self.ledger,
            self.projection,
        )
        self.commands = ArtifactCommandService(
            kernel_store,
            project_store,
            self.artifact_types,
            self.workspaces,
            self.executions,
            self.ledger,
            self.projection,
            self.graph,
        )

    def list_artifact_types(self) -> list[dict[str, Any]]:
        return self.artifact_types.list()

    def get_board(self, project_id: str) -> dict[str, Any]:
        return self.projection.get_board(project_id)

    def dispatch(self, command: dict[str, Any]) -> dict[str, Any]:
        return self.commands.dispatch(command)


def build_project_kernel(
    store: Any,
    *,
    project_store: Any | None = None,
    **kwargs: Any,
) -> ProjectKernel:
    """Build a kernel.

    ``store`` may be a kernel store. When ``project_store`` is omitted, the
    kernel store's ``project_store`` attribute is used when present.
    """
    kernel_store = store
    projects = project_store
    if projects is None:
        projects = getattr(kernel_store, "project_store", None)
    if projects is None:
        raise ValueError("project_store is required to build the project kernel")
    return ProjectKernel(project_store=projects, kernel_store=kernel_store, **kwargs)
