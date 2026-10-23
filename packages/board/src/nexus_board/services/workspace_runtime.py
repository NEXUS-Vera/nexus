"""Application-facing Workspace Runtime facade (Phase 14D).

product workspaces) can use filesystem, snapshots, sandboxed execution, logs,
cancellation, and declared outputs without importing runtime/storage internals.

This is orchestration only — not a second scheduler, filesystem, or runtime.
"""

from __future__ import annotations

from typing import Any, Protocol

from nexus_persistence.errors import FirmwarePatchNotFoundError as StoreFirmwarePatchNotFoundError

from nexus_board.analysis.patch import (
    ANALYSIS_PATCH_GENERATOR_ID,
    ANALYSIS_PATCH_GENERATOR_VERSION,
    assemble_analysis_generation_context,
    generate_analysis_patch_operations,
    validate_analysis_patch_proposal,
)
from nexus_board.analysis.patch import (
    SNAPSHOT_REASON_PATCH_BASE as SNAPSHOT_REASON_ANALYSIS_PATCH_BASE,
)
from nexus_board.analysis.patch import (
    check_patch_apply_staleness as check_analysis_patch_apply_staleness,
)
from nexus_board.analysis.patch import (
    read_snapshot_file_text as read_analysis_snapshot_file_text,
)
from nexus_board.analysis.patch import (
    snapshot_manifest_index as analysis_snapshot_manifest_index,
)
from nexus_board.analysis.scaffold import (
    DEFAULT_ANALYSIS_SCAFFOLD_PROFILE_ID,
    get_analysis_scaffold_profile,
)
from nexus_board.analysis.toolchain import (
    ANALYSIS_RUN_OPERATION,
    SNAPSHOT_REASON_BEFORE_RUN,
    analysis_toolchain_profile,
    build_analysis_command_spec,
    compare_produced_output_hashes,
    validate_analysis_snapshot_for_run,
)
from nexus_board.analysis.toolchain import (
    SNAPSHOT_REASON_BEFORE_RESTORE as SNAPSHOT_REASON_ANALYSIS_BEFORE_RESTORE,
)
from nexus_board.errors import (
    AnalysisPatchGenerationError,
    AnalysisPatchNotFoundError,
    AnalysisPatchValidationError,
    BoardError,
    CommandValidationError,
    FirmwarePatchGenerationError,
    FirmwarePatchNotFoundError,
    FirmwarePatchValidationError,
    RegistryError,
    WorkspaceScaffoldConflictError,
)
from nexus_board.firmware.patch import (
    FIRMWARE_PATCH_GENERATOR_ID,
    FIRMWARE_PATCH_GENERATOR_VERSION,
    assemble_firmware_generation_context,
    check_patch_apply_staleness,
    generate_firmware_patch_operations,
    read_snapshot_file_text,
    snapshot_manifest_index,
    validate_firmware_patch_proposal,
)
from nexus_board.firmware.scaffold import (
    DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID,
    get_firmware_scaffold_profile,
)
from nexus_board.firmware.toolchain import (
    FIRMWARE_COMPILE_OPERATION,
    FIRMWARE_TEST_OPERATION,
    SNAPSHOT_REASON_BEFORE_RESTORE,
    SNAPSHOT_REASON_MANUAL,
    SNAPSHOT_REASON_PATCH_BASE,
    build_firmware_command_spec,
    firmware_toolchain_profile,
    require_firmware_toolchain,
    snapshot_reason_for_operation,
    validate_firmware_snapshot_for_toolchain,
)
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.paths import normalize_workspace_path
from nexus_board.registries.artifact_types import ArtifactTypeRegistry
from nexus_board.services.execution_service import ExecutionService
from nexus_board.services.filesystem_service import (
    FilesystemWorkspaceService,
    is_filesystem_workspace,
)
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.workspace_service import WorkspaceService

FIRMWARE_ARTIFACT_TYPE = "firmware"
ANALYSIS_ARTIFACT_TYPE = "analysis"

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

    def create_firmware_patch_proposal(self, proposal: dict[str, Any]) -> None: ...

    def get_firmware_patch_proposal(self, proposal_id: str) -> dict[str, Any]: ...

    def update_firmware_patch_proposal(
        self, proposal_id: str, proposal: dict[str, Any]
    ) -> None: ...


class _FirmwarePatchGenerator(Protocol):
    def generate(
        self,
        *,
        context: dict[str, Any],
        base_snapshot: dict[str, Any],
    ) -> dict[str, Any]: ...


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
        firmware_patch_generator: _FirmwarePatchGenerator | None = None,
        analysis_patch_generator: Any | None = None,
    ) -> None:
        self.invalidation: Any | None = None
        self._kernel = kernel_store
        self._projects = project_store
        self._types = artifact_types
        self._workspaces = workspaces
        self._filesystem = filesystem
        self._executions = executions
        self._ledger = ledger
        self._analysis_patch_generator = analysis_patch_generator
        self._firmware_patch_generator = firmware_patch_generator

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
                actor=_actor_or_system(actor),
            )
            workspace = created["workspace"]
            draft = created["draft"]
        else:
            workspace = existing["workspace"]
            draft = existing["draft"]

        if self.invalidation is not None:
            self.invalidation.bind_workspace(project_id, artifact_type)

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

    def generate_firmware_scaffold(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        profile_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Materialize the deterministic Firmware scaffold when safe.

        Never silently overwrites existing scaffold target paths. Unrelated
        workspace files are preserved. Exact matching content is a no-op.
        """
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware scaffold generation is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        try:
            profile = get_firmware_scaffold_profile(
                profile_id or DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID
            )
        except KeyError as exc:
            raise CommandValidationError(str(exc)) from exc

        workspace_id = binding["workspaceId"]
        existing_by_path: dict[str, dict[str, Any]] = {}
        matching = 0
        conflicts: list[str] = []
        for spec in profile.files:
            record = self._kernel.get_workspace_file(workspace_id, spec.path)
            if record is None:
                continue
            existing_by_path[spec.path] = record
            if record.get("contentHash") == spec.content_hash:
                matching += 1
            else:
                conflicts.append(spec.path)

        if conflicts:
            raise WorkspaceScaffoldConflictError(
                "Firmware scaffold target path already exists: " + ", ".join(conflicts)
            )
        if matching == len(profile.files):
            return {
                "binding": _public_binding(binding),
                "status": "already-generated",
                "generationId": None,
                "generationKind": "scaffold",
                "profile": profile.as_public_dict(),
                "generatedFiles": [
                    {
                        "path": spec.path,
                        "contentHash": existing_by_path[spec.path]["contentHash"],
                        "sizeBytes": existing_by_path[spec.path]["sizeBytes"],
                        "origin": existing_by_path[spec.path].get("origin"),
                        "writePolicy": existing_by_path[spec.path].get("writePolicy"),
                        "generatedFrom": existing_by_path[spec.path].get("generatedFrom"),
                    }
                    for spec in profile.files
                ],
                "draft": self._kernel.get_draft(workspace_id),
                "workspace": self._kernel.get_workspace(workspace_id),
                "primaryPath": profile.files[-1].path if profile.files else None,
            }
        if matching > 0:
            # Partial scaffold (some targets match, others missing) — refuse.
            missing = [spec.path for spec in profile.files if spec.path not in existing_by_path]
            raise WorkspaceScaffoldConflictError(
                "Partial firmware scaffold already present; refusing unsafe generation. "
                f"Existing={sorted(existing_by_path)}; missing={missing}"
            )

        draft_version = expected_draft_version
        written: list[dict[str, Any]] = []
        last_workspace = binding["workspace"]
        last_draft = self._kernel.get_draft(workspace_id)
        for spec in profile.files:
            result = self._filesystem.write_file(
                workspace_id=workspace_id,
                path=spec.path,
                content=spec.content,
                actor=actor,
                expected_draft_version=draft_version,
                base_artifact_version=base_artifact_version,
                base_project_state_version=base_project_state_version,
                origin="GENERATED",
                write_policy="REGENERATION_MANAGED",
                generated_from=profile.generated_from,
                media_type=spec.media_type,
            )
            file_record = result["file"]
            if file_record.get("contentHash") != spec.content_hash:
                raise BoardError(
                    f"Scaffold write produced unexpected hash for {spec.path}",
                    code="WORKSPACE_SCAFFOLD_HASH_MISMATCH",
                )
            written.append(file_record)
            last_draft = result["draft"]
            last_workspace = result["workspace"]
            draft_version = int(last_draft["draftVersion"])

        generation_id = new_id("gen")
        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.scaffold-generated",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "artifactVersion": base_artifact_version,
                    "generationId": generation_id,
                    "generationKind": "scaffold",
                    "scaffoldProfileId": profile.profile_id,
                    "scaffoldProfileVersion": profile.profile_version,
                    "baseProjectStateVersion": base_project_state_version,
                    "generatedFiles": [
                        {"path": item["path"], "contentHash": item["contentHash"]}
                        for item in written
                    ],
                    "summary": (
                        f"Generated {profile.display_name} scaffold ({len(written)} files)"
                    ),
                },
                causation_id=causation_id,
                correlation_id=causation_id or generation_id,
                occurred_at=utc_now_iso(),
            )

        refreshed = self.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=False,
        )
        return {
            "binding": _public_binding(refreshed),
            "status": "generated",
            "generationId": generation_id,
            "generationKind": "scaffold",
            "profile": profile.as_public_dict(),
            "generatedFiles": [
                {
                    "path": item["path"],
                    "contentHash": item["contentHash"],
                    "sizeBytes": item["sizeBytes"],
                    "origin": item.get("origin"),
                    "writePolicy": item.get("writePolicy"),
                    "generatedFrom": item.get("generatedFrom"),
                }
                for item in written
            ],
            "draft": last_draft,
            "workspace": last_workspace,
            "event": event,
            "primaryPath": profile.files[-1].path if profile.files else None,
        }

    def propose_firmware_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        requested_change: str,
        allow_fixture: bool = False,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a validated patch proposal against an immutable base snapshot.

        Does not mutate workspace files. The generator never writes directly.
        """
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware patch generation is only available for artifact type firmware"
            )
        if not isinstance(requested_change, str) or not requested_change.strip():
            raise CommandValidationError("requestedChange is required")

        if not isinstance(allow_fixture, bool):
            raise CommandValidationError("allowFixture must be a boolean")
        if self._firmware_patch_generator is None and not allow_fixture:
            raise FirmwarePatchGenerationError(
                "Configure a model provider for firmware authoring.",
                code="MODEL_PROVIDER_UNAVAILABLE",
            )

        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        workspace_id = binding["workspaceId"]

        snapshot_result = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=SNAPSHOT_REASON_PATCH_BASE,
        )
        base_snapshot_id = snapshot_result["snapshotId"]
        base_snapshot = self._kernel.get_snapshot(base_snapshot_id)

        context = assemble_firmware_generation_context(
            project_store=self._projects,
            project_id=project_id,
            base_snapshot=base_snapshot,
            requested_change=requested_change.strip(),
            file_store=self._filesystem.file_store,
        )
        generator_id = FIRMWARE_PATCH_GENERATOR_ID
        generator_version = FIRMWARE_PATCH_GENERATOR_VERSION
        generator_metadata: dict[str, Any] | None = None
        if self._firmware_patch_generator is not None:
            generated = self._firmware_patch_generator.generate(
                context=context,
                base_snapshot=base_snapshot,
            )
            operations = generated.get("operations")
            if not isinstance(operations, list) or not operations:
                raise FirmwarePatchGenerationError("Patch generator returned no operations")
            maybe_id = generated.get("generatorId")
            if isinstance(maybe_id, str) and maybe_id.strip():
                generator_id = maybe_id.strip()
            maybe_version = generated.get("generatorVersion")
            if isinstance(maybe_version, str) and maybe_version.strip():
                generator_version = maybe_version.strip()
            metadata = generated.get("generatorMetadata")
            if isinstance(metadata, dict):
                generator_metadata = metadata
        else:
            generator_metadata = {"mode": "fixture"}
            operations = generate_firmware_patch_operations(
                requested_change=requested_change.strip(),
                base_snapshot=base_snapshot,
                file_store=self._filesystem.file_store,
                context=context,
            )

        now = utc_now_iso()
        proposal_id = new_id("fwpatch")
        proposal = {
            "schemaVersion": "1.0.0",
            "proposalId": proposal_id,
            "projectId": project_id,
            "artifactId": binding["artifactId"],
            "artifactType": artifact_type,
            "workspaceId": workspace_id,
            "baseSnapshotId": base_snapshot_id,
            "requestedChange": requested_change.strip(),
            "generatorId": generator_id,
            "generatorVersion": generator_version,
            "inputArtifactReferences": context["inputArtifactReferences"],
            "operations": operations,
            "status": "proposed",
            "requestedBy": actor,
            "requestedAt": now,
        }
        if generator_metadata:
            proposal["generatorMetadata"] = generator_metadata
        validate_firmware_patch_proposal(
            proposal,
            base_snapshot=base_snapshot,
            limits=self._filesystem.limits,
        )
        self._kernel.create_firmware_patch_proposal(proposal)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-proposed",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": base_snapshot_id,
                    "requestedChange": requested_change.strip(),
                    "generatorId": generator_id,
                    "generatorVersion": generator_version,
                    "generationKind": "patch",
                    "inputArtifactReferences": context["inputArtifactReferences"],
                    "patchOperations": [
                        {
                            "operationType": op["operationType"],
                            "path": op["path"],
                            **(
                                {"expectedBaseHash": op["expectedBaseHash"]}
                                if "expectedBaseHash" in op
                                else {}
                            ),
                            **({"contentHash": op["contentHash"]} if "contentHash" in op else {}),
                        }
                        for op in operations
                    ],
                    "summary": (
                        f"Proposed firmware patch ({len(operations)} file"
                        f"{'' if len(operations) == 1 else 's'})"
                    ),
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        return {
            "binding": _public_binding(binding),
            "status": "proposed",
            "proposal": proposal,
            "baseSnapshot": base_snapshot,
            "generationContext": context,
            "event": event,
        }

    def apply_firmware_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        proposal_id: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply a previously proposed patch through the Phase 14 filesystem boundary.

        Multi-file patches apply sequentially; partial application is possible if a
        later operation fails after earlier writes succeeded.
        """
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware patch apply is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        workspace_id = binding["workspaceId"]
        try:
            proposal = self._kernel.get_firmware_patch_proposal(proposal_id)
        except Exception as exc:  # noqa: BLE001
            from nexus_persistence.errors import FirmwarePatchNotFoundError as StoreNotFound

            if isinstance(exc, StoreNotFound):
                raise FirmwarePatchNotFoundError(str(exc)) from exc
            raise

        if proposal.get("status") != "proposed":
            raise FirmwarePatchValidationError(
                f"Patch proposal is not in proposed status: {proposal.get('status')}"
            )
        if proposal.get("projectId") != project_id:
            raise FirmwarePatchNotFoundError("Patch proposal not found for project")
        if proposal.get("workspaceId") != workspace_id:
            raise FirmwarePatchValidationError("Patch proposal workspace mismatch")

        base_snapshot = self._kernel.get_snapshot(proposal["baseSnapshotId"])
        validate_firmware_patch_proposal(
            proposal,
            base_snapshot=base_snapshot,
            limits=self._filesystem.limits,
        )

        def _current_file(path: str) -> dict[str, Any] | None:
            return self._kernel.get_workspace_file(workspace_id, path)

        check_patch_apply_staleness(proposal=proposal, get_current_file=_current_file)

        generated_from = f"{proposal['generatorId']}@{proposal['generatorVersion']}"
        draft_version = expected_draft_version
        applied_files: list[dict[str, Any]] = []
        last_draft = self._kernel.get_draft(workspace_id)
        last_workspace = binding["workspace"]

        for operation in proposal["operations"]:
            op_type = operation["operationType"]
            path = operation["path"]
            if op_type in {"create-file", "replace-file"}:
                content = operation["content"].encode("utf-8")
                result = self._filesystem.write_file(
                    workspace_id=workspace_id,
                    path=path,
                    content=content,
                    actor=actor,
                    expected_draft_version=draft_version,
                    base_artifact_version=base_artifact_version,
                    base_project_state_version=base_project_state_version,
                    origin="GENERATED",
                    write_policy="REGENERATION_MANAGED",
                    generated_from=generated_from,
                    media_type="text/plain",
                )
                file_record = result["file"]
                if file_record.get("contentHash") != operation["contentHash"]:
                    raise BoardError(
                        f"Patch apply produced unexpected hash for {path}",
                        code="FIRMWARE_PATCH_APPLY_HASH_MISMATCH",
                    )
                applied_files.append(file_record)
                last_draft = result["draft"]
                last_workspace = result["workspace"]
                draft_version = int(last_draft["draftVersion"])
            elif op_type == "delete-file":
                result = self._filesystem.delete_file(
                    workspace_id=workspace_id,
                    path=path,
                    actor=actor,
                    expected_draft_version=draft_version,
                    base_artifact_version=base_artifact_version,
                    base_project_state_version=base_project_state_version,
                )
                applied_files.append({"path": path, "deleted": True})
                last_draft = result["draft"]
                last_workspace = result["workspace"]
                draft_version = int(last_draft["draftVersion"])

        now = utc_now_iso()
        updated = dict(proposal)
        updated["status"] = "applied"
        updated["decidedAt"] = now
        updated["decidedBy"] = actor
        self._kernel.update_firmware_patch_proposal(proposal_id, updated)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-applied",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": proposal["baseSnapshotId"],
                    "requestedChange": proposal["requestedChange"],
                    "generatorId": proposal["generatorId"],
                    "generatorVersion": proposal["generatorVersion"],
                    "generationKind": "patch",
                    "inputArtifactReferences": proposal.get("inputArtifactReferences") or [],
                    "patchOperations": [
                        {
                            "operationType": op["operationType"],
                            "path": op["path"],
                            **(
                                {"expectedBaseHash": op["expectedBaseHash"]}
                                if "expectedBaseHash" in op
                                else {}
                            ),
                            **({"contentHash": op["contentHash"]} if "contentHash" in op else {}),
                        }
                        for op in proposal["operations"]
                    ],
                    "generatedFiles": [
                        {
                            "path": item["path"],
                            "contentHash": item.get("contentHash"),
                        }
                        for item in applied_files
                        if not item.get("deleted")
                    ],
                    "summary": f"Applied firmware patch ({len(proposal['operations'])} operations)",
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        refreshed = self.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=False,
        )
        return {
            "binding": _public_binding(refreshed),
            "status": "applied",
            "proposal": updated,
            "appliedFiles": applied_files,
            "draft": last_draft,
            "workspace": last_workspace,
            "event": event,
            "applySemantics": "sequential-non-atomic",
        }

    def discard_firmware_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        proposal_id: str,
        actor: dict[str, Any],
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Discard a proposed patch without mutating workspace files."""
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware patch discard is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        try:
            proposal = self._kernel.get_firmware_patch_proposal(proposal_id)
        except Exception as exc:  # noqa: BLE001
            from nexus_persistence.errors import FirmwarePatchNotFoundError as StoreNotFound

            if isinstance(exc, StoreNotFound):
                raise FirmwarePatchNotFoundError(str(exc)) from exc
            raise

        if proposal.get("projectId") != project_id:
            raise FirmwarePatchNotFoundError("Patch proposal not found for project")
        if proposal.get("workspaceId") != binding["workspaceId"]:
            raise FirmwarePatchValidationError("Patch proposal belongs to another workspace")
        if proposal.get("status") != "proposed":
            raise FirmwarePatchValidationError(
                f"Patch proposal is not in proposed status: {proposal.get('status')}"
            )

        now = utc_now_iso()
        updated = dict(proposal)
        updated["status"] = "discarded"
        updated["decidedAt"] = now
        updated["decidedBy"] = actor
        self._kernel.update_firmware_patch_proposal(proposal_id, updated)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-discarded",
                actor=actor,
                subject_type="workspace",
                subject_id=binding["workspaceId"],
                payload={
                    "workspaceId": binding["workspaceId"],
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": proposal["baseSnapshotId"],
                    "requestedChange": proposal["requestedChange"],
                    "generatorId": proposal["generatorId"],
                    "generatorVersion": proposal["generatorVersion"],
                    "generationKind": "patch",
                    "summary": "Discarded firmware patch proposal",
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        return {
            "binding": _public_binding(binding),
            "status": "discarded",
            "proposal": updated,
            "event": event,
        }

    def create_firmware_snapshot(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        reason: str | None = None,
    ) -> dict[str, Any]:
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Manual firmware snapshots are only available for artifact type firmware"
            )
        label = (reason or SNAPSHOT_REASON_MANUAL).strip()
        if not label:
            raise CommandValidationError("Snapshot reason must not be empty")
        return self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=label,
        )

    def restore_firmware_snapshot(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        """Restore a snapshot after creating a before-restore safety snapshot."""
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware snapshot restore is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="snapshots",
        )
        safety = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=SNAPSHOT_REASON_BEFORE_RESTORE,
        )
        result = self._workspaces.restore_snapshot(
            workspace_id=binding["workspaceId"],
            snapshot_id=snapshot_id,
            actor=actor,
        )
        return {
            "binding": _public_binding(binding),
            "beforeRestoreSnapshotId": safety["snapshotId"],
            **result,
        }

    def read_firmware_snapshot_file(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        path: str,
    ) -> dict[str, Any]:
        """Read-only preview of a file from an immutable filesystem snapshot."""
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Firmware snapshot preview is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="snapshots",
        )
        snapshot = self._kernel.get_snapshot(snapshot_id)
        if snapshot.get("workspaceId") != binding["workspaceId"]:
            raise CommandValidationError("Snapshot does not belong to firmware workspace")
        manifest = snapshot_manifest_index(snapshot)
        entry = manifest.get(path)
        if entry is None:
            raise BoardError(
                f"Snapshot file not found: {path}",
                code="WORKSPACE_FILE_NOT_FOUND",
            )
        content = read_snapshot_file_text(
            file_store=self._filesystem.file_store,
            entry=entry,
            path=path,
        )
        return {
            "binding": _public_binding(binding),
            "snapshotId": snapshot_id,
            "path": path,
            "encoding": "utf-8",
            "content": content,
            "sizeBytes": len(content.encode("utf-8")),
            "contentHash": entry.get("contentHash"),
        }

    def compile_firmware(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        require_real: bool = False,
        base_artifact_version: int | None = None,
        base_project_state_version: int | None = None,
        max_duration_ms: int | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(require_real, bool):
            raise CommandValidationError("requireReal must be a boolean")
        require_firmware_toolchain(require_real=require_real)
        return self._start_firmware_toolchain_execution(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            operation="compile",
            product_operation=FIRMWARE_COMPILE_OPERATION,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            max_duration_ms=max_duration_ms,
            causation_id=causation_id,
        )

    def test_firmware(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        base_artifact_version: int | None = None,
        base_project_state_version: int | None = None,
        max_duration_ms: int | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        return self._start_firmware_toolchain_execution(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            operation="test",
            product_operation=FIRMWARE_TEST_OPERATION,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            max_duration_ms=max_duration_ms,
            causation_id=causation_id,
        )

    def _start_firmware_toolchain_execution(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        operation: str,
        product_operation: str,
        base_artifact_version: int | None,
        base_project_state_version: int | None,
        max_duration_ms: int | None,
        causation_id: str | None,
    ) -> dict[str, Any]:
        if artifact_type != FIRMWARE_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                f"{product_operation} is only available for artifact type firmware"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="execution",
        )
        snapshot_result = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=snapshot_reason_for_operation(operation),
        )
        snapshot_id = snapshot_result["snapshotId"]
        base_snapshot = self._kernel.get_snapshot(snapshot_id)
        validate_firmware_snapshot_for_toolchain(
            base_snapshot,
            file_store=self._filesystem.file_store,
            operation=operation,
        )
        require_firmware_toolchain()
        command_spec = build_firmware_command_spec(operation)
        workspace = binding["workspace"]
        project = self._projects.get_project(project_id)
        exec_result = self._executions.execute(
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
            causation_id=causation_id or new_id("cmd"),
            max_duration_ms=max_duration_ms,
            options={
                "commandSpec": command_spec,
                "productOperation": product_operation,
                # ESP32 Arduino ELF (~6.3 MB) plus BIN, bounded by the execution API cap.
                **({"maxOutputBytes": 10_485_760} if operation == "compile" else {}),
            },
        )
        return {
            "binding": _public_binding(binding),
            "operation": product_operation,
            "toolchainProfile": firmware_toolchain_profile(),
            "executionSnapshotId": snapshot_id,
            "executionRun": exec_result["executionRun"],
            "executionJob": exec_result.get("executionJob"),
            "accepted": exec_result.get("accepted", True),
            "startedAt": utc_now_iso(),
        }

    def preview_analysis_output(
        self,
        *,
        project_id: str,
        output_id: str,
        max_bytes: int = 65_536,
    ) -> dict[str, Any]:
        """Bounded preview of an Analysis ProducedOutput (Phase 16G)."""
        output = self.get_output(project_id=project_id, output_id=output_id)
        name = str(output.get("name") or "")
        content = output.get("content") or {}
        kind = content.get("kind")
        raw: bytes
        if kind == "inline-structured":
            structured = content.get("structuredResult") or {}
            text = structured.get("text")
            if isinstance(text, str):
                raw = text.encode("utf-8")
            else:
                raise CommandValidationError("Inline output has no previewable text")
        elif kind == "storage-reference":
            if content.get("storageKind") != "file-store":
                raise CommandValidationError("Unsupported output storage kind")
            uri = content.get("uri")
            if not isinstance(uri, str) or not uri:
                raise CommandValidationError("Output storage uri missing")
            data = self._filesystem.file_store.get(uri)
            if not isinstance(data, (bytes, bytearray)):
                raise BoardError("Output blob missing", code="OUTPUT_NOT_FOUND")
            raw = bytes(data)
        else:
            raise CommandValidationError(f"Unsupported output content kind: {kind!r}")

        truncated = len(raw) > max_bytes
        preview_bytes = raw[:max_bytes]
        lower = name.lower()
        is_png = lower.endswith(".png") or preview_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        if is_png:
            import base64

            return {
                "schemaVersion": "1.0.0",
                "outputId": output_id,
                "name": name,
                "previewKind": "image-png",
                "mediaType": "image/png",
                "contentBase64": base64.b64encode(preview_bytes).decode("ascii"),
                "sizeBytes": len(raw),
                "truncated": truncated,
                "contentDigest": output.get("contentDigest"),
            }
        text = preview_bytes.decode("utf-8", errors="replace")
        if lower.endswith(".json"):
            preview_kind = "json"
        elif lower.endswith(".csv"):
            preview_kind = "csv"
        elif lower.endswith(".txt") or lower.endswith(".md"):
            preview_kind = "text"
        else:
            preview_kind = "unknown"
        return {
            "schemaVersion": "1.0.0",
            "outputId": output_id,
            "name": name,
            "previewKind": preview_kind,
            "mediaType": "text/plain",
            "text": text,
            "sizeBytes": len(raw),
            "truncated": truncated,
            "contentDigest": output.get("contentDigest"),
        }

    def generate_analysis_scaffold(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        profile_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Materialize the deterministic Analysis scaffold when safe."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis scaffold generation is only available for artifact type analysis"
            )

        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        try:
            profile = get_analysis_scaffold_profile(
                profile_id or DEFAULT_ANALYSIS_SCAFFOLD_PROFILE_ID
            )
        except KeyError as exc:
            raise CommandValidationError(str(exc)) from exc

        workspace_id = binding["workspaceId"]
        existing_by_path: dict[str, dict[str, Any]] = {}
        matching = 0
        conflicts: list[str] = []
        for spec in profile.files:
            record = self._kernel.get_workspace_file(workspace_id, spec.path)
            if record is None:
                continue
            existing_by_path[spec.path] = record
            if record.get("contentHash") == spec.content_hash:
                matching += 1
            else:
                conflicts.append(spec.path)

        if conflicts:
            raise WorkspaceScaffoldConflictError(
                "Analysis scaffold target path already exists: " + ", ".join(conflicts)
            )

        if matching == len(profile.files):
            return {
                "binding": _public_binding(binding),
                "status": "already-generated",
                "generationId": None,
                "generationKind": "scaffold",
                "profile": profile.as_public_dict(),
                "generatedFiles": [
                    {
                        "path": spec.path,
                        "contentHash": existing_by_path[spec.path]["contentHash"],
                        "sizeBytes": existing_by_path[spec.path]["sizeBytes"],
                        "origin": existing_by_path[spec.path].get("origin"),
                        "writePolicy": existing_by_path[spec.path].get("writePolicy"),
                        "generatedFrom": existing_by_path[spec.path].get("generatedFrom"),
                    }
                    for spec in profile.files
                ],
                "draft": self._kernel.get_draft(workspace_id),
                "workspace": self._kernel.get_workspace(workspace_id),
                "primaryPath": profile.files[-1].path if profile.files else None,
            }

        if matching > 0:
            # Partial scaffold (some targets match, others missing) — refuse.
            missing = [spec.path for spec in profile.files if spec.path not in existing_by_path]
            raise WorkspaceScaffoldConflictError(
                "Partial analysis scaffold already present; refusing unsafe generation. "
                f"Existing={sorted(existing_by_path)}; missing={missing}"
            )

        draft_version = expected_draft_version
        written: list[dict[str, Any]] = []
        last_workspace = binding["workspace"]
        last_draft = self._kernel.get_draft(workspace_id)
        for spec in profile.files:
            result = self._filesystem.write_file(
                workspace_id=workspace_id,
                path=spec.path,
                content=spec.content,
                actor=actor,
                expected_draft_version=draft_version,
                base_artifact_version=base_artifact_version,
                base_project_state_version=base_project_state_version,
                origin="GENERATED",
                write_policy="REGENERATION_MANAGED",
                generated_from=profile.generated_from,
                media_type=spec.media_type,
            )
            file_record = result["file"]
            if file_record.get("contentHash") != spec.content_hash:
                raise BoardError(
                    f"Scaffold write produced unexpected hash for {spec.path}",
                    code="WORKSPACE_SCAFFOLD_HASH_MISMATCH",
                )
            written.append(file_record)
            last_draft = result["draft"]
            last_workspace = result["workspace"]
            draft_version = int(last_draft["draftVersion"])

        generation_id = new_id("gen")
        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.scaffold-generated",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "artifactVersion": base_artifact_version,
                    "generationId": generation_id,
                    "generationKind": "scaffold",
                    "scaffoldProfileId": profile.profile_id,
                    "scaffoldProfileVersion": profile.profile_version,
                    "baseProjectStateVersion": base_project_state_version,
                    "generatedFiles": [
                        {"path": item["path"], "contentHash": item["contentHash"]}
                        for item in written
                    ],
                    "summary": f"Generated {profile.display_name} scaffold ({len(written)} files)",
                },
                causation_id=causation_id,
                correlation_id=causation_id or generation_id,
                occurred_at=utc_now_iso(),
            )

        refreshed = self.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=False,
        )
        return {
            "binding": _public_binding(refreshed),
            "status": "generated",
            "generationId": generation_id,
            "generationKind": "scaffold",
            "profile": profile.as_public_dict(),
            "generatedFiles": [
                {
                    "path": item["path"],
                    "contentHash": item["contentHash"],
                    "sizeBytes": item["sizeBytes"],
                    "origin": item.get("origin"),
                    "writePolicy": item.get("writePolicy"),
                    "generatedFrom": item.get("generatedFrom"),
                }
                for item in written
            ],
            "draft": last_draft,
            "workspace": last_workspace,
            "event": event,
            "primaryPath": profile.files[-1].path if profile.files else None,
        }

    def write_analysis_input_file(
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
        media_type: str | None = None,
        causation_id: str | None = None,
        generated_from: str | None = None,
    ) -> dict[str, Any]:
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis input upload is only available for artifact type analysis"
            )
        # Enforce the analysis data/ root.
        normalized = normalize_workspace_path(path)
        if not (normalized == "data" or normalized.startswith("data/")):
            raise CommandValidationError("Analysis inputs must be written under data/")

        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        workspace_id = binding["workspaceId"]
        result = self._filesystem.write_file(
            workspace_id=workspace_id,
            path=normalized,
            content=content,
            actor=actor,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            origin="USER",
            write_policy="USER_EDITABLE",
            generated_from=generated_from,
            media_type=media_type,
        )
        return {"binding": _public_binding(binding), **result}

    def import_produced_output_into_analysis_input(
        self,
        *,
        project_id: str,
        artifact_type: str,
        output_id: str,
        path: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "ProducedOutput import is only available for artifact type analysis"
            )

        normalized = normalize_workspace_path(path)
        if not (normalized == "data" or normalized.startswith("data/")):
            raise CommandValidationError("Analysis inputs must be written under data/")

        output = self._executions.get_output(output_id)
        if output.get("projectId") != project_id:
            raise BoardError("Produced output does not belong to project", code="OUTPUT_NOT_FOUND")

        output_content = output.get("content") or {}
        content_kind = output_content.get("kind")

        data_bytes: bytes
        if content_kind == "inline-structured":
            structured = output_content.get("structuredResult")
            if isinstance(structured, dict) and isinstance(structured.get("text"), str):
                data_bytes = structured["text"].encode("utf-8")
            elif isinstance(structured, dict) and isinstance(
                structured.get("value"), (str, int, float, bool, type(None))
            ):
                data_bytes = str(structured["value"]).encode("utf-8")
            else:
                data_bytes = str(structured).encode("utf-8")
        elif content_kind == "storage-reference":
            if output_content.get("storageKind") != "file-store":
                raise CommandValidationError("Unsupported output storageKind for import")
            uri = output_content.get("uri")
            if not isinstance(uri, str):
                raise CommandValidationError("Invalid produced output uri")
            data_bytes = self._filesystem.file_store.get(uri)
        else:
            raise CommandValidationError("Unsupported produced output content kind for import")

        media_type = output.get("mediaType")
        workspace_binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        _ = workspace_binding
        # Import provenance is represented via origin + generatedFrom.
        result = self._filesystem.write_file(
            workspace_id=workspace_binding["workspaceId"],
            path=normalized,
            content=data_bytes,
            actor=actor,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            origin="RUNTIME_OUTPUT",
            write_policy="USER_EDITABLE",
            generated_from=f"imported-output:{output_id}",
            media_type=str(media_type) if media_type else None,
        )

        return {"binding": _public_binding(workspace_binding), **result}

    def upsert_analysis_investigation(
        self,
        *,
        project_id: str,
        artifact_type: str,
        investigation: dict[str, Any],
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> dict[str, Any]:
        """Persist lightweight investigation metadata under nexus/investigation.json."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis investigation metadata is only available for artifact type analysis"
            )
        import json

        from nexus_board.analysis.semantics import (
            INVESTIGATION_METADATA_PATH,
            validate_investigation_dict,
        )

        validate_investigation_dict(investigation)
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        content = (json.dumps(investigation, sort_keys=True, indent=2) + "\n").encode("utf-8")
        result = self._filesystem.write_file(
            workspace_id=binding["workspaceId"],
            path=INVESTIGATION_METADATA_PATH,
            content=content,
            actor=actor,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
            origin="GENERATED",
            write_policy="USER_EDITABLE",
            generated_from="analysis-investigation.v1",
            media_type="application/json",
        )
        return {"binding": _public_binding(binding), "path": INVESTIGATION_METADATA_PATH, **result}

    def _get_analysis_patch_proposal(self, proposal_id: str) -> dict[str, Any]:
        # The predecessor patch store persists opaque payloads. Analysis IDs use
        # the anpatch_ namespace; validate type before sharing this durable store.
        try:
            proposal = self._kernel.get_firmware_patch_proposal(proposal_id)
        except StoreFirmwarePatchNotFoundError as exc:
            raise AnalysisPatchNotFoundError("Analysis patch proposal not found") from exc
        if proposal.get("artifactType") != ANALYSIS_ARTIFACT_TYPE:
            raise AnalysisPatchNotFoundError("Analysis patch proposal not found")
        return proposal

    def propose_analysis_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        requested_change: str,
        causation_id: str | None = None,
        require_model: bool = False,
    ) -> dict[str, Any]:
        """Generate a validated patch proposal against an immutable base snapshot (Phase 16C)."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis patch generation is only available for artifact type analysis"
            )
        if not isinstance(requested_change, str) or not requested_change.strip():
            raise CommandValidationError("requestedChange is required")

        if require_model and self._analysis_patch_generator is None:
            raise AnalysisPatchGenerationError(
                "Configure a model provider for analysis repair.", code="MODEL_PROVIDER_UNAVAILABLE"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        workspace_id = binding["workspaceId"]

        snapshot_result = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=SNAPSHOT_REASON_ANALYSIS_PATCH_BASE,
        )
        base_snapshot_id = snapshot_result["snapshotId"]
        base_snapshot = self._kernel.get_snapshot(base_snapshot_id)

        context = assemble_analysis_generation_context(
            project_store=self._projects,
            project_id=project_id,
            base_snapshot=base_snapshot,
            requested_change=requested_change.strip(),
            file_store=self._filesystem.file_store,
        )

        generator_id = ANALYSIS_PATCH_GENERATOR_ID
        generator_version = ANALYSIS_PATCH_GENERATOR_VERSION
        generator_metadata: dict[str, Any] | None = None

        if self._analysis_patch_generator is not None:
            generated = self._analysis_patch_generator.generate(
                context=context,
                base_snapshot=base_snapshot,
            )
            maybe_ops = generated.get("operations")
            operations = maybe_ops if isinstance(maybe_ops, list) else []
            if not operations:
                raise AnalysisPatchGenerationError(
                    "Analysis patch generator returned no operations"
                )
            maybe_id = generated.get("generatorId")
            if isinstance(maybe_id, str) and maybe_id.strip():
                generator_id = maybe_id.strip()
            maybe_version = generated.get("generatorVersion")
            if isinstance(maybe_version, str) and maybe_version.strip():
                generator_version = maybe_version.strip()
            maybe_metadata = generated.get("generatorMetadata")
            if isinstance(maybe_metadata, dict):
                generator_metadata = maybe_metadata
        else:
            operations = generate_analysis_patch_operations(
                requested_change=requested_change.strip(),
                base_snapshot=base_snapshot,
                file_store=self._filesystem.file_store,
                context=context,
            )

        now = utc_now_iso()
        proposal_id = new_id("anpatch")
        proposal = {
            "schemaVersion": "1.0.0",
            "proposalId": proposal_id,
            "projectId": project_id,
            "artifactId": binding["artifactId"],
            "artifactType": artifact_type,
            "workspaceId": workspace_id,
            "baseSnapshotId": base_snapshot_id,
            "requestedChange": requested_change.strip(),
            "generatorId": generator_id,
            "generatorVersion": generator_version,
            "inputArtifactReferences": [],
            "operations": operations,
            "status": "proposed",
            "requestedBy": actor,
            "requestedAt": now,
        }
        if generator_metadata:
            proposal["generatorMetadata"] = generator_metadata

        validate_analysis_patch_proposal(
            proposal,
            base_snapshot=base_snapshot,
            limits=self._filesystem.limits,
        )
        self._kernel.create_firmware_patch_proposal(proposal)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-proposed",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": base_snapshot_id,
                    "requestedChange": requested_change.strip(),
                    "generatorId": generator_id,
                    "generatorVersion": generator_version,
                    "generationKind": "patch",
                    "inputArtifactReferences": context.get("inputArtifactReferences") or [],
                    "patchOperations": [
                        {
                            "operationType": op["operationType"],
                            "path": op["path"],
                            **(
                                {"expectedBaseHash": op["expectedBaseHash"]}
                                if "expectedBaseHash" in op
                                else {}
                            ),
                            **({"contentHash": op["contentHash"]} if "contentHash" in op else {}),
                        }
                        for op in operations
                    ],
                    "summary": (
                        f"Proposed analysis patch ({len(operations)} file"
                        f"{'' if len(operations) == 1 else 's'})"
                    ),
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        return {
            "binding": _public_binding(binding),
            "status": "proposed",
            "proposal": proposal,
            "baseSnapshotId": base_snapshot_id,
            "generationContext": context,
            "event": event,
        }

    def apply_analysis_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        proposal_id: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply a proposed analysis patch through the filesystem boundary."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis patch apply is only available for artifact type analysis"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        workspace_id = binding["workspaceId"]

        proposal = self._get_analysis_patch_proposal(proposal_id)

        if proposal.get("status") != "proposed":
            raise AnalysisPatchValidationError(
                f"Patch proposal is not in proposed status: {proposal.get('status')}"
            )
        if proposal.get("projectId") != project_id:
            raise AnalysisPatchNotFoundError("Patch proposal not found for project")
        if proposal.get("workspaceId") != workspace_id:
            raise AnalysisPatchValidationError("Patch proposal workspace mismatch")

        base_snapshot = self._kernel.get_snapshot(proposal["baseSnapshotId"])
        validate_analysis_patch_proposal(
            proposal,
            base_snapshot=base_snapshot,
            limits=self._filesystem.limits,
        )

        def _current_file(path: str) -> dict[str, Any] | None:
            return self._kernel.get_workspace_file(workspace_id, path)

        check_analysis_patch_apply_staleness(
            proposal=proposal,
            get_current_file=_current_file,
            base_snapshot=base_snapshot,
        )

        generated_from = f"{proposal['generatorId']}@{proposal['generatorVersion']}"
        draft_version = expected_draft_version
        applied_files: list[dict[str, Any]] = []
        last_draft = self._kernel.get_draft(workspace_id)
        last_workspace = binding["workspace"]

        for operation in proposal["operations"]:
            op_type = operation["operationType"]
            path = operation["path"]

            if op_type in {"create-file", "replace-file"}:
                content = operation["content"].encode("utf-8")
                result = self._filesystem.write_file(
                    workspace_id=workspace_id,
                    path=path,
                    content=content,
                    actor=actor,
                    expected_draft_version=draft_version,
                    base_artifact_version=base_artifact_version,
                    base_project_state_version=base_project_state_version,
                    origin="GENERATED",
                    write_policy="REGENERATION_MANAGED",
                    generated_from=generated_from,
                    media_type="text/plain",
                )
                file_record = result["file"]
                if file_record.get("contentHash") != operation["contentHash"]:
                    raise BoardError(
                        f"Analysis patch apply produced unexpected hash for {path}",
                        code="ANALYSIS_PATCH_APPLY_HASH_MISMATCH",
                    )
                applied_files.append(file_record)
                last_draft = result["draft"]
                last_workspace = result["workspace"]
                draft_version = int(last_draft["draftVersion"])

            elif op_type == "delete-file":
                result = self._filesystem.delete_file(
                    workspace_id=workspace_id,
                    path=path,
                    actor=actor,
                    expected_draft_version=draft_version,
                    base_artifact_version=base_artifact_version,
                    base_project_state_version=base_project_state_version,
                )
                applied_files.append({"path": path, "deleted": True})
                last_draft = result["draft"]
                last_workspace = result["workspace"]
                draft_version = int(last_draft["draftVersion"])
            else:
                raise AnalysisPatchValidationError(f"Unsupported operation type: {op_type}")

        now = utc_now_iso()
        updated = dict(proposal)
        updated["status"] = "applied"
        updated["decidedAt"] = now
        updated["decidedBy"] = actor
        self._kernel.update_firmware_patch_proposal(proposal_id, updated)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-applied",
                actor=actor,
                subject_type="workspace",
                subject_id=workspace_id,
                payload={
                    "workspaceId": workspace_id,
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": proposal["baseSnapshotId"],
                    "requestedChange": proposal["requestedChange"],
                    "generatorId": proposal["generatorId"],
                    "generatorVersion": proposal["generatorVersion"],
                    "generationKind": "patch",
                    "inputArtifactReferences": proposal.get("inputArtifactReferences") or [],
                    "patchOperations": [
                        {
                            "operationType": op["operationType"],
                            "path": op["path"],
                            **(
                                {"expectedBaseHash": op["expectedBaseHash"]}
                                if "expectedBaseHash" in op
                                else {}
                            ),
                            **({"contentHash": op["contentHash"]} if "contentHash" in op else {}),
                        }
                        for op in proposal["operations"]
                    ],
                    "generatedFiles": [
                        {
                            "path": item["path"],
                            "contentHash": item.get("contentHash"),
                        }
                        for item in applied_files
                        if not item.get("deleted")
                    ],
                    "summary": f"Applied analysis patch ({len(proposal['operations'])} operations)",
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        refreshed = self.resolve_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            create_if_missing=False,
        )
        return {
            "binding": _public_binding(refreshed),
            "status": "applied",
            "proposal": updated,
            "appliedFiles": applied_files,
            "draft": last_draft,
            "workspace": last_workspace,
            "event": event,
            "applySemantics": "sequential-non-atomic",
        }

    def discard_analysis_patch(
        self,
        *,
        project_id: str,
        artifact_type: str,
        proposal_id: str,
        actor: dict[str, Any],
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Discard a proposed analysis patch without mutating workspace files (Phase 16C)."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis patch discard is only available for artifact type analysis"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="filesystem",
        )
        proposal = self._get_analysis_patch_proposal(proposal_id)

        if proposal.get("projectId") != project_id:
            raise AnalysisPatchNotFoundError("Patch proposal not found for project")
        if proposal.get("status") != "proposed":
            raise AnalysisPatchValidationError(
                f"Patch proposal is not in proposed status: {proposal.get('status')}"
            )

        now = utc_now_iso()
        updated = dict(proposal)
        updated["status"] = "discarded"
        updated["decidedAt"] = now
        updated["decidedBy"] = actor

        self._kernel.update_firmware_patch_proposal(proposal_id, updated)

        event = None
        if self._ledger is not None:
            event = self._ledger.append(
                project_id=project_id,
                event_type="workspace.patch-discarded",
                actor=actor,
                subject_type="workspace",
                subject_id=binding["workspaceId"],
                payload={
                    "workspaceId": binding["workspaceId"],
                    "artifactId": binding["artifactId"],
                    "artifactType": artifact_type,
                    "patchProposalId": proposal_id,
                    "baseSnapshotId": proposal["baseSnapshotId"],
                    "requestedChange": proposal["requestedChange"],
                    "generatorId": proposal["generatorId"],
                    "generatorVersion": proposal["generatorVersion"],
                    "generationKind": "patch",
                    "summary": "Discarded analysis patch proposal",
                },
                causation_id=causation_id,
                correlation_id=causation_id or proposal_id,
                occurred_at=now,
            )

        return {
            "binding": _public_binding(binding),
            "status": "discarded",
            "proposal": updated,
            "event": event,
        }

    def restore_analysis_snapshot(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        """Restore an analysis snapshot after creating a before-restore safety snapshot."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis snapshot restore is only available for artifact type analysis"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="snapshots",
        )
        safety = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=SNAPSHOT_REASON_ANALYSIS_BEFORE_RESTORE,
        )
        result = self._workspaces.restore_snapshot(
            workspace_id=binding["workspaceId"],
            snapshot_id=snapshot_id,
            actor=actor,
        )
        return {
            "binding": _public_binding(binding),
            "beforeRestoreSnapshotId": safety["snapshotId"],
            **result,
        }

    def read_analysis_snapshot_file(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        path: str,
    ) -> dict[str, Any]:
        """Read-only preview of a file from an immutable analysis filesystem snapshot."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "Analysis snapshot preview is only available for artifact type analysis"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="snapshots",
        )
        snapshot = self._kernel.get_snapshot(snapshot_id)
        if snapshot.get("workspaceId") != binding["workspaceId"]:
            raise CommandValidationError("Snapshot does not belong to analysis workspace")
        manifest = analysis_snapshot_manifest_index(snapshot)
        entry = manifest.get(path)
        if entry is None:
            raise BoardError(
                f"Snapshot file not found: {path}",
                code="WORKSPACE_FILE_NOT_FOUND",
            )
        content = read_analysis_snapshot_file_text(
            file_store=self._filesystem.file_store,
            entry=entry,
            path=path,
        )
        return {
            "binding": _public_binding(binding),
            "snapshotId": snapshot_id,
            "path": path,
            "encoding": "utf-8",
            "content": content,
            "sizeBytes": len(content.encode("utf-8")),
            "contentHash": entry.get("contentHash"),
        }

    def run_analysis(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        base_artifact_version: int | None = None,
        base_project_state_version: int | None = None,
        max_duration_ms: int | None = None,
        causation_id: str | None = None,
        require_real: bool = False,
    ) -> dict[str, Any]:
        """Run analysis.py against an immutable pre-run snapshot (Phase 16D)."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "analysis.run is only available for artifact type analysis"
            )
        if require_real and analysis_toolchain_profile()["executionMode"] == "fixture":
            raise BoardError(
                "Real analysis required; fixture mode selected",
                code="ANALYSIS_TOOLCHAIN_UNAVAILABLE",
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="execution",
        )
        snapshot_result = self.create_snapshot(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            reason=SNAPSHOT_REASON_BEFORE_RUN,
        )
        snapshot_id = snapshot_result["snapshotId"]
        base_snapshot = self._kernel.get_snapshot(snapshot_id)
        validate_analysis_snapshot_for_run(
            base_snapshot,
            file_store=self._filesystem.file_store,
        )
        command_spec = build_analysis_command_spec()
        workspace = binding["workspace"]
        project = self._projects.get_project(project_id)
        exec_result = self._executions.execute(
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
            causation_id=causation_id or new_id("cmd"),
            max_duration_ms=max_duration_ms,
            options={"commandSpec": command_spec, "productOperation": ANALYSIS_RUN_OPERATION},
        )
        return {
            "binding": _public_binding(binding),
            "operation": ANALYSIS_RUN_OPERATION,
            "toolchainProfile": analysis_toolchain_profile(),
            "executionSnapshotId": snapshot_id,
            "executionRun": exec_result["executionRun"],
            "executionJob": exec_result.get("executionJob"),
            "accepted": exec_result.get("accepted", True),
            "startedAt": utc_now_iso(),
        }

    def rerun_analysis(
        self,
        *,
        project_id: str,
        artifact_type: str,
        snapshot_id: str,
        actor: dict[str, Any],
        base_artifact_version: int | None = None,
        base_project_state_version: int | None = None,
        max_duration_ms: int | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Re-run analysis against a specific immutable snapshot."""
        if artifact_type != ANALYSIS_ARTIFACT_TYPE:
            raise WorkspaceRuntimeCapabilityError(
                "analysis.rerun is only available for artifact type analysis"
            )
        binding = self._require_binding(
            project_id=project_id,
            artifact_type=artifact_type,
            capability="execution",
        )
        workspace = binding["workspace"]
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise CommandValidationError("snapshotId is required for rerun")
        base_snapshot = self._kernel.get_snapshot(snapshot_id)
        if base_snapshot.get("workspaceId") != workspace["workspaceId"]:
            raise CommandValidationError("Snapshot does not belong to this analysis workspace")
        validate_analysis_snapshot_for_run(
            base_snapshot,
            file_store=self._filesystem.file_store,
        )
        command_spec = build_analysis_command_spec()
        project = self._projects.get_project(project_id)
        exec_result = self._executions.execute(
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
            causation_id=causation_id or new_id("cmd"),
            max_duration_ms=max_duration_ms,
            options={
                "commandSpec": command_spec,
                "productOperation": ANALYSIS_RUN_OPERATION,
                "rerun": True,
                "rerunSnapshotId": snapshot_id,
            },
        )
        return {
            "binding": _public_binding(binding),
            "operation": ANALYSIS_RUN_OPERATION,
            "rerun": True,
            "toolchainProfile": analysis_toolchain_profile(),
            "executionSnapshotId": snapshot_id,
            "executionRun": exec_result["executionRun"],
            "executionJob": exec_result.get("executionJob"),
            "accepted": exec_result.get("accepted", True),
            "startedAt": utc_now_iso(),
        }

    def compare_analysis_run_outputs(
        self,
        *,
        project_id: str,
        baseline_execution_run_id: str,
        rerun_execution_run_id: str,
    ) -> dict[str, Any]:
        """Compare ProducedOutput content hashes between baseline and rerun executions."""
        baseline = self.list_outputs_for_run(
            project_id=project_id,
            execution_run_id=baseline_execution_run_id,
        )["outputs"]
        rerun = self.list_outputs_for_run(
            project_id=project_id,
            execution_run_id=rerun_execution_run_id,
        )["outputs"]
        comparisons = compare_produced_output_hashes(baseline, rerun)
        return {
            "schemaVersion": "1.0.0",
            "baselineExecutionRunId": baseline_execution_run_id,
            "rerunExecutionRunId": rerun_execution_run_id,
            "comparisons": comparisons,
        }


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
