"""Workspace lifecycle service."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.errors import (
    CommandValidationError,
    SnapshotImmutableError,
)
from nexus_board.governance.concurrency import (
    check_artifact_and_project_versions,
    check_draft_version,
)
from nexus_board.ids import content_digest, new_id, utc_now_iso
from nexus_board.registries.artifact_types import ArtifactTypeRegistry
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService


class _KernelStore(Protocol):
    def create_workspace(self, workspace: dict[str, Any], draft: dict[str, Any]) -> None: ...

    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...

    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def update_draft(self, draft: dict[str, Any]) -> None: ...

    def create_snapshot(self, snapshot: dict[str, Any]) -> None: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]: ...

    def update_snapshot(self, snapshot: dict[str, Any]) -> None: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...


class WorkspaceService:
    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        registry: ArtifactTypeRegistry,
        ledger: ProjectLedgerService,
        projection: ProjectBoardProjectionService,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._registry = registry
        self._ledger = ledger
        self._projection = projection

    def get_or_none(self, project_id: str, artifact_type: str) -> dict[str, Any] | None:
        workspace = self._kernel.get_workspace_by_project_artifact(project_id, artifact_type)
        if workspace is None:
            return None
        draft = self._kernel.get_draft(workspace["workspaceId"])
        return {"workspace": workspace, "draft": draft}

    def create_if_missing(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        initial_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.get_or_none(project_id, artifact_type)
        if existing is not None:
            return existing
        return self.create_workspace(
            project_id=project_id,
            artifact_type=artifact_type,
            actor=actor,
            initial_content=initial_content,
        )

    def create_workspace(
        self,
        *,
        project_id: str,
        artifact_type: str,
        actor: dict[str, Any],
        initial_content: dict[str, Any] | None = None,
        artifact_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        definition = self._registry.get(artifact_type)
        project = self._projects.get_project(project_id)
        try:
            artifact = self._projects.get_artifact(project_id, artifact_type)
        except Exception:  # noqa: BLE001
            if artifact_type != "component-plan":
                raise
            # component-plan may not exist yet; synthesize placeholder pointer
            artifact = {
                "artifactId": artifact_id or new_id("art"),
                "artifactVersion": 1,
                "artifactType": artifact_type,
                "content": initial_content
                or {
                    "selectionState": "draft",
                    "candidateCount": 0,
                    "constraintSummary": "No candidates retrieved; retrieval deferred.",
                    "unresolvedCompatibilityChecks": ["provider-retrieval-unavailable"],
                    "approvalStatus": "not-required",
                },
            }
        now = utc_now_iso()
        content = (
            initial_content if initial_content is not None else dict(artifact.get("content") or {})
        )
        workspace = {
            "schemaVersion": "1.0.0",
            "workspaceId": new_id("ws"),
            "projectId": project_id,
            "artifactId": artifact["artifactId"],
            "artifactType": artifact_type,
            "workspaceType": definition["workspaceType"],
            "status": "ready",
            "baseArtifactVersion": int(artifact["artifactVersion"]),
            "baseProjectStateVersion": int(project["currentStateVersion"]),
            "createdBy": actor,
            "createdAt": now,
            "updatedAt": now,
            "runtimeCapabilityRequirements": list(definition.get("requiredCapabilities") or []),
            "externalWorkspaceReferences": [],
        }
        draft = {
            "schemaVersion": "1.0.0",
            "workspaceId": workspace["workspaceId"],
            "draftVersion": 1,
            "baseArtifactVersion": int(artifact["artifactVersion"]),
            "baseProjectStateVersion": int(project["currentStateVersion"]),
            "content": content,
            "validationState": "unvalidated",
            "createdAt": now,
            "updatedAt": now,
            "updatedBy": actor,
        }
        self._kernel.create_workspace(workspace, draft)
        self._ledger.append(
            project_id=project_id,
            event_type="workspace.created",
            actor=actor,
            subject_type="workspace",
            subject_id=workspace["workspaceId"],
            payload={
                "workspaceId": workspace["workspaceId"],
                "artifactType": artifact_type,
            },
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=now,
        )
        self._projection.update_after_write(project_id)
        return {"workspace": workspace, "draft": draft}

    def update_draft(
        self,
        *,
        workspace_id: str,
        content: dict[str, Any],
        expected_draft_version: int,
        actor: dict[str, Any],
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> dict[str, Any]:
        workspace = self._kernel.get_workspace(workspace_id)
        draft = self._kernel.get_draft(workspace_id)
        project = self._projects.get_project(workspace["projectId"])
        check_artifact_and_project_versions(
            expected_artifact_version=base_artifact_version,
            actual_artifact_version=int(workspace["baseArtifactVersion"]),
            expected_project_state_version=base_project_state_version,
            actual_project_state_version=int(project["currentStateVersion"]),
        )
        check_draft_version(
            expected_draft_version=expected_draft_version,
            actual_draft_version=int(draft["draftVersion"]),
        )
        now = utc_now_iso()
        draft = dict(draft)
        draft["content"] = content
        draft["draftVersion"] = int(draft["draftVersion"]) + 1
        draft["validationState"] = "unvalidated"
        draft["updatedAt"] = now
        draft["updatedBy"] = actor
        # Draft edits must NOT bump accepted artifact version.
        self._kernel.update_draft(draft)
        workspace = dict(workspace)
        workspace["status"] = "dirty"
        workspace["updatedAt"] = now
        self._kernel.update_workspace(workspace)
        self._projection.update_after_write(workspace["projectId"])
        return {"workspace": workspace, "draft": draft}

    def create_snapshot(
        self,
        *,
        workspace_id: str,
        reason: str,
        actor: dict[str, Any],
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._kernel.get_workspace(workspace_id)
        draft = self._kernel.get_draft(workspace_id)
        existing = self._kernel.list_snapshots(workspace_id)
        now = utc_now_iso()
        structured = dict(draft["content"])
        snapshot = {
            "schemaVersion": "1.0.0",
            "snapshotId": new_id("snap"),
            "workspaceId": workspace_id,
            "projectId": workspace["projectId"],
            "artifactId": workspace["artifactId"],
            "snapshotVersion": len(existing) + 1,
            "baseArtifactVersion": int(draft["baseArtifactVersion"]),
            "baseProjectStateVersion": int(draft["baseProjectStateVersion"]),
            "content": {"kind": "structured", "structuredContent": structured},
            "contentDigest": content_digest(structured),
            "createdBy": actor,
            "createdAt": now,
            "reason": reason,
        }
        self._kernel.create_snapshot(snapshot)
        workspace = dict(workspace)
        workspace["currentSnapshotId"] = snapshot["snapshotId"]
        workspace["status"] = "ready"
        workspace["updatedAt"] = now
        self._kernel.update_workspace(workspace)
        self._ledger.append(
            project_id=workspace["projectId"],
            event_type="workspace.snapshot-created",
            actor=actor,
            subject_type="snapshot",
            subject_id=snapshot["snapshotId"],
            payload={
                "workspaceId": workspace_id,
                "snapshotId": snapshot["snapshotId"],
                "artifactType": workspace["artifactType"],
                "reason": reason,
            },
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=now,
        )
        self._projection.update_after_write(workspace["projectId"])
        return snapshot

    def restore_snapshot(
        self,
        *,
        workspace_id: str,
        snapshot_id: str,
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        workspace = self._kernel.get_workspace(workspace_id)
        snapshot = self._kernel.get_snapshot(snapshot_id)
        if snapshot["workspaceId"] != workspace_id:
            raise CommandValidationError("Snapshot does not belong to workspace.")
        content = snapshot["content"].get("structuredContent") or {}
        draft = self._kernel.get_draft(workspace_id)
        now = utc_now_iso()
        draft = dict(draft)
        draft["content"] = dict(content)
        draft["draftVersion"] = int(draft["draftVersion"]) + 1
        draft["validationState"] = "unvalidated"
        draft["updatedAt"] = now
        draft["updatedBy"] = actor
        self._kernel.update_draft(draft)
        workspace = dict(workspace)
        workspace["status"] = "dirty"
        workspace["updatedAt"] = now
        self._kernel.update_workspace(workspace)
        self._projection.update_after_write(workspace["projectId"])
        return {"workspace": workspace, "draft": draft, "snapshot": snapshot}

    def assert_snapshot_immutable(self, snapshot: dict[str, Any]) -> None:
        try:
            self._kernel.update_snapshot(snapshot)
        except SnapshotImmutableError:
            return
        raise SnapshotImmutableError("Snapshots must be immutable.")
