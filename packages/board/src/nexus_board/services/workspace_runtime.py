"""Application-facing Workspace Runtime facade (Phase 14D).

product workspaces) can use filesystem, snapshots, sandboxed execution, logs,
cancellation, and declared outputs without importing runtime/storage internals.

This is orchestration only — not a second scheduler, filesystem, or runtime.
"""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.errors import (
    BoardError,
    CommandValidationError,
    RegistryError,
)
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.registries.artifact_types import ArtifactTypeRegistry
from nexus_board.services.execution_service import ExecutionService
from nexus_board.services.filesystem_service import (
    FilesystemWorkspaceService,
    is_filesystem_workspace,
)
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.workspace_service import WorkspaceService

CAPABILITY_FILESYSTEM = "file-workspace"
CAPABILITY_SANDBOX = "sandbox-execution"
CAPABILITY_SNAPSHOTS = "filesystem-snapshots"  # derived when file-workspace is present


class WorkspaceRuntimeCapabilityError(BoardError):
    code = "WORKSPACE_RUNTIME_CAPABILITY_DENIED"


class WorkspaceRuntimeBindingError(BoardError):
    code = "WORKSPACE_RUNTIME_BINDING_FAILED"


class _KernelStore(Protocol):
    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None: ...

    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def get_workspace_file(self, workspace_id: str, path: str) -> dict[str, Any] | None: ...

    def list_workspace_files(self, workspace_id: str) -> list[dict[str, Any]]: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...


def _actor_or_system(actor: dict[str, Any] | None) -> dict[str, Any]:
    if actor is not None:
        return actor
    return {
        "schemaVersion": "1.0.0",
        "actorId": "actor_SYSTEM",
        "actorType": "system",
        "displayName": "System",
    }


class WorkspaceRuntimeService:
    """Stable Phase 14 handoff surface for application workspaces."""

    def __init__(
        self,
        *,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        artifact_types: ArtifactTypeRegistry,
        workspaces: WorkspaceService,
        filesystem: FilesystemWorkspaceService,
        executions: ExecutionService,
        ledger: ProjectLedgerService | None = None,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._types = artifact_types
        self._workspaces = workspaces
        self._filesystem = filesystem
        self._executions = executions
        self._ledger = ledger

    # --- binding / capabilities -------------------------------------------------

    def resolve_binding(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any] | None = None,
        create_if_missing: bool = True,
    ) -> dict[str, Any]:
        """Resolve the durable artifact ↔ filesystem-workspace relationship.

        Workspaces are keyed by ``(projectId, artifactType)`` and survive
        accepted artifact revision changes. They are not recreated per revision.
        """
        del actor  # reserved for future authn; binding itself is deterministic
        try:
            definition = self._types.get(artifact_type)
        except RegistryError as exc:
            raise WorkspaceRuntimeBindingError(str(exc)) from exc

        required = list(definition.get("requiredCapabilities") or [])
        caps = {
            "filesystem": CAPABILITY_FILESYSTEM in required,
            "snapshots": CAPABILITY_FILESYSTEM in required,
            "execution": CAPABILITY_SANDBOX in required,
            "logs": CAPABILITY_SANDBOX in required,
        }
        existing = self._workspaces.get_or_none(project_id, artifact_type)
        if existing is None:
            if not create_if_missing:
                raise WorkspaceRuntimeBindingError(
                    f"No workspace for artifact type {artifact_type}"
                )
            created = self._workspaces.create_if_missing(
                project_id=project_id,
                artifact_type=artifact_type,
                actor=_actor_or_system(None),
            )
            workspace = created["workspace"]
            draft = created["draft"]
        else:
            workspace = existing["workspace"]
            draft = existing["draft"]

        # Capabilities remain registry-driven; filesystem ops still gate on them.
        filesystem_enabled = bool(caps["filesystem"] and is_filesystem_workspace(workspace))
        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "artifactId": workspace["artifactId"],
            "artifactType": artifact_type,
            "workspaceId": workspace["workspaceId"],
            "workspaceType": workspace.get("workspaceType"),
            "baseArtifactVersion": workspace.get("baseArtifactVersion"),
            "baseProjectStateVersion": workspace.get("baseProjectStateVersion"),
            "currentSnapshotId": workspace.get("currentSnapshotId"),
            "capabilities": caps,
            "requiredCapabilities": required,
            "workspace": workspace,
            "draft": draft,
            "filesystemEnabled": filesystem_enabled,
        }

    def _require_binding(
        self,
        *,
        project_id: str,
        artifact_type: str,
        capability: str | None = None,
    ) -> dict[str, Any]:
        binding = self.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=True,
        )
        if capability == "filesystem" and not binding["capabilities"]["filesystem"]:
            raise WorkspaceRuntimeCapabilityError("Filesystem capability not enabled")
        if capability == "execution" and not binding["capabilities"]["execution"]:
            raise WorkspaceRuntimeCapabilityError("Sandbox execution capability not enabled")
        if capability == "snapshots" and not binding["capabilities"]["snapshots"]:
            raise WorkspaceRuntimeCapabilityError("Snapshot capability not enabled")
        return binding

    # --- filesystem ------------------------------------------------------------

    def list_files(self, *, project_id: str, artifact_type: str) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="filesystem"
        )
        files = self._filesystem.list_files(binding["workspaceId"])
        return {"binding": _public_binding(binding), "files": files}

    def read_file(self, *, project_id: str, artifact_type: str, path: str) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="filesystem"
        )
        result = self._filesystem.read_file(binding["workspaceId"], path)
        return {"binding": _public_binding(binding), **result}

    def write_file(
        self,
        *,
        project_id: str,
        artifact_type: str,
        path: str,
        content: bytes,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        origin: str | None = None,
        write_policy: str | None = None,
        generated_from: str | None = None,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="filesystem"
        )
        result = self._filesystem.write_file(
            workspace_id=binding["workspaceId"],
            path=path,
            content=content,
            actor=actor,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            origin=origin,
            write_policy=write_policy,
            generated_from=generated_from,
            media_type=media_type,
        )
        return {"binding": _public_binding(binding), **result}

    def delete_file(
        self,
        *,
        project_id: str,
        artifact_type: str,
        path: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="filesystem"
        )
        result = self._filesystem.delete_file(
            workspace_id=binding["workspaceId"],
            path=path,
            actor=actor,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
        )
        return {"binding": _public_binding(binding), **result}

    # --- snapshots -------------------------------------------------------------

    def create_snapshot(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        reason: str | None = None,
    ) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="snapshots"
        )
        result = self._workspaces.create_snapshot(
            workspace_id=binding["workspaceId"],
            actor=actor,
            reason=reason or "workspace-runtime",
        )
        return {"binding": _public_binding(binding), **result}

    def list_snapshots(self, *, project_id: str, artifact_type: str) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="snapshots"
        )
        snapshots = self._kernel.list_snapshots(binding["workspaceId"])
        return {"binding": _public_binding(binding), "snapshots": snapshots}

    def restore_snapshot(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="snapshots"
        )
        result = self._workspaces.restore_snapshot(
            workspace_id=binding["workspaceId"],
            snapshot_id=snapshot_id,
            actor=actor,
        )
        return {"binding": _public_binding(binding), **result}

    # --- execution -------------------------------------------------------------

    def start_execution(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        actor: dict[str, Any],
        command_spec: dict[str, Any],
        base_artifact_version: int | None = None,
        base_project_state_version: int | None = None,
        max_duration_ms: int | None = None,
        execution_kind: str = "sandbox-execution",
    ) -> dict[str, Any]:
        """Start a validated sandbox execution against an immutable snapshot.

        ``command_spec`` must be an approved ExecutionCommandSpec. Product
        operations such as future ``firmware.compile`` should map to approved
        specs internally — callers must not treat this as a remote shell.
        """
        if execution_kind != "sandbox-execution":
            raise CommandValidationError(
                f"Unsupported executionKind={execution_kind}; only sandbox-execution in Phase 14D"
            )
        binding = self._require_binding(
            project_id=project_id, artifact_type=artifact_type, capability="execution"
        )
        if not isinstance(command_spec, dict):
            raise CommandValidationError("commandSpec is required")
        workspace = binding["workspace"]
        project = self._projects.get_project(project_id)
        result = self._executions.execute(
            project_id=project_id,
            artifact_id=workspace["artifactId"],
            artifact_type=artifact_type,
            workspace_id=workspace["workspaceId"],
            snapshot_id=snapshot_id,
            capability=CAPABILITY_SANDBOX,
            actor=actor,
            base_artifact_version=int(
                base_artifact_version
                if base_artifact_version is not None
                else workspace["baseArtifactVersion"]
            ),
            base_project_state_version=int(
                base_project_state_version
                if base_project_state_version is not None
                else project["currentStateVersion"]
            ),
            causation_id=new_id("cmd"),
            max_duration_ms=max_duration_ms,
            options={"commandSpec": command_spec},
        )
        return {
            "binding": _public_binding(binding),
            "executionRun": result["executionRun"],
            "executionJob": result.get("executionJob"),
            "accepted": result.get("accepted", True),
            "startedAt": utc_now_iso(),
        }

    def get_execution(self, *, project_id: str, execution_run_id: str) -> dict[str, Any]:
        run = self._executions.get_run(execution_run_id)
        if run["projectId"] != project_id:
            raise BoardError("Execution not found", code="EXECUTION_NOT_FOUND")
        job = self._executions.get_job_for_run(execution_run_id)
        return {"executionRun": run, "executionJob": job}

    def list_logs(
        self,
        *,
        project_id: str,
        execution_run_id: str,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        run = self._executions.get_run(execution_run_id)
        if run["projectId"] != project_id:
            raise BoardError("Execution not found", code="EXECUTION_NOT_FOUND")
        return self._executions.list_logs(
            execution_run_id, after_sequence=after_sequence, limit=limit
        )

    def cancel_execution(
        self, *, project_id: str, execution_run_id: str, actor: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        run = self._executions.get_run(execution_run_id)
        if run["projectId"] != project_id:
            raise BoardError("Execution not found", code="EXECUTION_NOT_FOUND")
        return self._executions.cancel(execution_run_id, actor=actor)

    def get_output(self, *, project_id: str, output_id: str) -> dict[str, Any]:
        output = self._executions.get_output(output_id)
        if output["projectId"] != project_id:
            raise BoardError("Output not found", code="OUTPUT_NOT_FOUND")
        return output

    def list_outputs_for_run(self, *, project_id: str, execution_run_id: str) -> dict[str, Any]:
        run = self._executions.get_run(execution_run_id)
        if run["projectId"] != project_id:
            raise BoardError("Execution not found", code="EXECUTION_NOT_FOUND")
        outputs = []
        for output_id in run.get("outputReferences") or []:
            outputs.append(self._executions.get_output(output_id))
        return {"executionRunId": execution_run_id, "outputs": outputs}


def _public_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": binding["schemaVersion"],
        "projectId": binding["projectId"],
        "artifactId": binding["artifactId"],
        "artifactType": binding["artifactType"],
        "workspaceId": binding["workspaceId"],
        "workspaceType": binding.get("workspaceType"),
        "baseArtifactVersion": binding.get("baseArtifactVersion"),
        "baseProjectStateVersion": binding.get("baseProjectStateVersion"),
        "currentSnapshotId": binding.get("currentSnapshotId"),
        "capabilities": binding["capabilities"],
        "requiredCapabilities": binding["requiredCapabilities"],
        "filesystemEnabled": binding["filesystemEnabled"],
    }
