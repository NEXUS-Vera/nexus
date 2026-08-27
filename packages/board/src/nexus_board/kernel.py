"""Project kernel wiring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nexus_persistence.file_store.memory import InMemoryFileStore
from nexus_persistence.file_store.protocol import FileStore

from nexus_board.execution.job_service import ExecutionJobService
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.execution.runtime_factory import build_execution_runtime
from nexus_board.execution.scheduler import SchedulerConfig
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
from nexus_board.services.execution_service import CapabilityExecutor, ExecutionService
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits
from nexus_board.services.filesystem_service import FilesystemWorkspaceService
from nexus_board.services.graph_service import ProjectGraphService
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService
from nexus_board.services.retention import RetentionPolicy, RetentionService
from nexus_board.services.workspace_runtime import WorkspaceRuntimeService
from nexus_board.services.workspace_service import WorkspaceService
from nexus_board.services.verification_service import VerificationService


class ProjectKernel:
    def __init__(
        self,
        *,
        project_store: Any,
        kernel_store: Any,
        artifact_types: ArtifactTypeRegistry | None = None,
        capabilities: RuntimeCapabilityRegistry | None = None,
        providers: ExternalProviderRegistry | None = None,
        capability_executors: Mapping[str, CapabilityExecutor] | None = None,
        file_store: FileStore | None = None,
        filesystem_limits: WorkspaceFilesystemLimits | None = None,
        execution_limits: ExecutionLimits | None = None,
        scheduler_config: SchedulerConfig | None = None,
        execution_runtime: Any | None = None,
        retention_policy: RetentionPolicy | None = None,
        firmware_patch_generator: Any | None = None,
        analysis_patch_generator: Any | None = None,
        auto_start_scheduler: bool = True,
        recover_jobs_on_start: bool = True,
    ) -> None:
        self.project_store = project_store
        self.kernel_store = kernel_store
        self.artifact_types = artifact_types or default_artifact_type_registry()
        self.capabilities = capabilities or default_runtime_capability_registry()
        self.providers = providers or default_external_provider_registry()
        self.file_store = file_store if file_store is not None else InMemoryFileStore()
        self.ledger = ProjectLedgerService(kernel_store)
        self.graph = ProjectGraphService(kernel_store)
        self.projection = ProjectBoardProjectionService(kernel_store, project_store)
        self.filesystem = FilesystemWorkspaceService(
            kernel_store,
            project_store,
            self.file_store,
            self.projection,
            limits=filesystem_limits,
        )
        self.workspaces = WorkspaceService(
            kernel_store,
            project_store,
            self.artifact_types,
            self.ledger,
            self.projection,
            filesystem=self.filesystem,
        )
        runtime = execution_runtime if execution_runtime is not None else build_execution_runtime()
        self.jobs = ExecutionJobService(
            kernel_store,
            project_store,
            self.file_store,
            self.ledger,
            self.projection,
            runtime=runtime,
            default_limits=execution_limits,
            scheduler_config=scheduler_config,
            auto_start=auto_start_scheduler,
            recover_on_start=recover_jobs_on_start,
        )
        self.retention = RetentionService(
            kernel_store,
            self.file_store,
            policy=retention_policy,
        )
        self.executions = ExecutionService(
            kernel_store,
            project_store,
            self.artifact_types,
            self.capabilities,
            self.ledger,
            self.projection,
            capability_executors,
            job_service=self.jobs,
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
        self.workspace_runtime = WorkspaceRuntimeService(
            kernel_store=kernel_store,
            project_store=project_store,
            artifact_types=self.artifact_types,
            workspaces=self.workspaces,
            filesystem=self.filesystem,
            executions=self.executions,
            ledger=self.ledger,
            firmware_patch_generator=firmware_patch_generator,
            analysis_patch_generator=analysis_patch_generator,
        )
        self.verification = VerificationService(
            kernel_store=kernel_store,
            project_store=project_store,
            workspaces=self.workspaces,
            commands=self.commands,
            ledger=self.ledger,
            projection=self.projection,
            file_store=self.file_store,
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
