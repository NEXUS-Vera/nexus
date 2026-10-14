"""Filesystem workspace operations on the existing workspace kernel."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_persistence.file_store.hashing import opaque_content_reference
from nexus_persistence.file_store.protocol import FileStore

from nexus_board.errors import (
    CommandValidationError,
    WorkspaceFileNotFoundError,
    WorkspaceNotFilesystemError,
    WorkspaceQuotaExceededError,
    WorkspaceWritePolicyError,
)
from nexus_board.governance.concurrency import (
    check_artifact_and_project_versions,
    check_draft_version,
)
from nexus_board.ids import content_digest, utc_now_iso
from nexus_board.paths import normalize_workspace_path
from nexus_board.services.draft_lease import assert_actor_holds_lease
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits

FILESYSTEM_WORKSPACE_TYPES = frozenset({"code-workspace"})
ORIGINS = frozenset({"USER", "GENERATED", "SYSTEM", "RUNTIME_OUTPUT"})
WRITE_POLICIES = frozenset({"USER_EDITABLE", "REGENERATION_MANAGED", "READ_ONLY", "EPHEMERAL"})


class _KernelStore(Protocol):
    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...

    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def update_draft(self, draft: dict[str, Any]) -> None: ...

    def upsert_workspace_file(self, file_record: dict[str, Any]) -> None: ...

    def get_workspace_file(self, workspace_id: str, path: str) -> dict[str, Any] | None: ...

    def list_workspace_files(self, workspace_id: str) -> list[dict[str, Any]]: ...

    def delete_workspace_file(self, workspace_id: str, path: str) -> None: ...

    def replace_workspace_files(self, workspace_id: str, files: list[dict[str, Any]]) -> None: ...

    def list_referenced_content_hashes(self) -> set[str]: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...


class _Projection(Protocol):
    def update_after_write(self, project_id: str) -> Any: ...


def is_filesystem_workspace(workspace: dict[str, Any]) -> bool:
    return workspace.get("workspaceType") in FILESYSTEM_WORKSPACE_TYPES


def filesystem_draft_content() -> dict[str, Any]:
    return {"kind": "filesystem", "schemaVersion": "1.0.0"}


def build_filesystem_manifest(files: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for record in sorted(files, key=lambda item: item["path"]):
        entry: dict[str, Any] = {
            "path": record["path"],
            "contentHash": record["contentHash"],
            "contentReference": record["contentReference"],
            "sizeBytes": int(record["sizeBytes"]),
            "origin": record["origin"],
            "writePolicy": record["writePolicy"],
            "modifiedByUser": bool(record.get("modifiedByUser", False)),
        }
        if record.get("generatedFrom"):
            entry["generatedFrom"] = record["generatedFrom"]
        if record.get("mediaType"):
            entry["mediaType"] = record["mediaType"]
        entries.append(entry)
    manifest_body = {"entries": entries}
    return {
        "manifestDigest": content_digest(manifest_body),
        "entries": entries,
    }


class FilesystemWorkspaceService:
    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        file_store: FileStore,
        projection: _Projection,
        *,
        limits: WorkspaceFilesystemLimits | None = None,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._files = file_store
        self._projection = projection
        self._limits = limits or WorkspaceFilesystemLimits()

    @property
    def limits(self) -> WorkspaceFilesystemLimits:
        return self._limits

    @property
    def file_store(self) -> FileStore:
        return self._files

    def list_files(self, workspace_id: str) -> list[dict[str, Any]]:
        workspace = self._require_filesystem(workspace_id)
        _ = workspace
        return self._kernel.list_workspace_files(workspace_id)

    def read_file(self, workspace_id: str, path: str) -> dict[str, Any]:
        self._require_filesystem(workspace_id)
        normalized = normalize_workspace_path(path)
        record = self._kernel.get_workspace_file(workspace_id, normalized)
        if record is None:
            raise WorkspaceFileNotFoundError(f"Workspace file not found: {normalized}")
        content = self._files.get(record["contentHash"])
        return {"file": record, "content": content}

    def write_file(
        self,
        *,
        workspace_id: str,
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
        workspace = self._require_filesystem(workspace_id)
        draft = self._kernel.get_draft(workspace_id)
        assert_actor_holds_lease(draft, actor=actor)
        self._check_versions(
            workspace=workspace,
            draft=draft,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
        )
        normalized = normalize_workspace_path(path)
        if len(content) > self._limits.max_file_bytes:
            raise WorkspaceQuotaExceededError(
                f"File exceeds max_file_bytes ({self._limits.max_file_bytes})"
            )

        existing = self._kernel.get_workspace_file(workspace_id, normalized)
        if existing is not None:
            self._assert_mutable(existing, allow_user_edit=True)
            # Preserve origin (e.g. GENERATED); mark that the user edited it.
            next_origin = existing["origin"]
            next_policy = existing["writePolicy"]
            next_modified = True
            next_generated_from = existing.get("generatedFrom")
            next_media = media_type or existing.get("mediaType")
        else:
            next_origin = origin or "USER"
            next_policy = write_policy or "USER_EDITABLE"
            if next_origin not in ORIGINS:
                raise CommandValidationError(f"Invalid origin: {next_origin}")
            if next_policy not in WRITE_POLICIES:
                raise CommandValidationError(f"Invalid writePolicy: {next_policy}")
            next_modified = False
            next_generated_from = generated_from
            next_media = media_type
            files = self._kernel.list_workspace_files(workspace_id)
            if len(files) >= self._limits.max_file_count:
                raise WorkspaceQuotaExceededError(
                    f"Workspace exceeds max_file_count ({self._limits.max_file_count})"
                )

        current_total = sum(
            int(item["sizeBytes"])
            for item in self._kernel.list_workspace_files(workspace_id)
            if existing is None or item["path"] != normalized
        )
        if current_total + len(content) > self._limits.max_workspace_bytes:
            raise WorkspaceQuotaExceededError(
                f"Workspace exceeds max_workspace_bytes ({self._limits.max_workspace_bytes})"
            )

        # Blob first, then metadata — orphan blobs are GC-reclaimable.
        content_hash = self._files.put(content)
        now = utc_now_iso()
        record: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "workspaceId": workspace_id,
            "path": normalized,
            "contentHash": content_hash,
            "contentReference": opaque_content_reference(content_hash),
            "sizeBytes": len(content),
            "origin": next_origin,
            "writePolicy": next_policy,
            "modifiedByUser": next_modified,
            "createdAt": existing["createdAt"] if existing is not None else now,
            "updatedAt": now,
            "updatedBy": actor,
        }
        if next_generated_from:
            record["generatedFrom"] = next_generated_from
        if next_media:
            record["mediaType"] = next_media

        self._kernel.upsert_workspace_file(record)
        return self._bump_draft(workspace=workspace, draft=draft, actor=actor, now=now, file=record)

    def rename_file(
        self,
        *,
        workspace_id: str,
        from_path: str,
        to_path: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> dict[str, Any]:
        workspace = self._require_filesystem(workspace_id)
        draft = self._kernel.get_draft(workspace_id)
        assert_actor_holds_lease(draft, actor=actor)
        self._check_versions(
            workspace=workspace,
            draft=draft,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
        )
        source = normalize_workspace_path(from_path)
        destination = normalize_workspace_path(to_path)
        if source == destination:
            raise CommandValidationError("Rename source and destination must differ")
        existing = self._kernel.get_workspace_file(workspace_id, source)
        if existing is None:
            raise WorkspaceFileNotFoundError(f"Workspace file not found: {source}")
        self._assert_mutable(existing, allow_user_edit=True)
        if self._kernel.get_workspace_file(workspace_id, destination) is not None:
            raise CommandValidationError(f"Destination path already exists: {destination}")

        now = utc_now_iso()
        renamed = dict(existing)
        renamed["path"] = destination
        renamed["updatedAt"] = now
        renamed["updatedBy"] = actor
        if renamed["origin"] in {"GENERATED", "SYSTEM", "RUNTIME_OUTPUT"}:
            renamed["modifiedByUser"] = True
        self._kernel.upsert_workspace_file(renamed)
        self._kernel.delete_workspace_file(workspace_id, source)
        return self._bump_draft(
            workspace=workspace, draft=draft, actor=actor, now=now, file=renamed
        )

    def delete_file(
        self,
        *,
        workspace_id: str,
        path: str,
        actor: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> dict[str, Any]:
        workspace = self._require_filesystem(workspace_id)
        draft = self._kernel.get_draft(workspace_id)
        assert_actor_holds_lease(draft, actor=actor)
        self._check_versions(
            workspace=workspace,
            draft=draft,
            expected_draft_version=expected_draft_version,
            base_artifact_version=base_artifact_version,
            base_project_state_version=base_project_state_version,
        )
        normalized = normalize_workspace_path(path)
        existing = self._kernel.get_workspace_file(workspace_id, normalized)
        if existing is None:
            raise WorkspaceFileNotFoundError(f"Workspace file not found: {normalized}")
        self._assert_mutable(existing, allow_user_edit=True)
        # Do not delete the content-addressed blob; snapshots may still reference it.
        self._kernel.delete_workspace_file(workspace_id, normalized)
        now = utc_now_iso()
        return self._bump_draft(workspace=workspace, draft=draft, actor=actor, now=now, file=None)

    def capture_filesystem_snapshot_content(self, workspace_id: str) -> tuple[dict[str, Any], str]:
        files = self._kernel.list_workspace_files(workspace_id)
        for record in files:
            if not self._files.exists(record["contentHash"]):
                raise CommandValidationError(f"Missing blob for workspace file: {record['path']}")
        manifest = build_filesystem_manifest(files)
        return (
            {
                "kind": "filesystem",
                "filesystemManifest": manifest,
            },
            manifest["manifestDigest"],
        )

    def restore_filesystem_manifest(
        self,
        *,
        workspace_id: str,
        manifest: dict[str, Any],
        actor: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Replace mutable file index with snapshot manifest (lease already asserted)."""
        self._require_filesystem(workspace_id)
        entries = list(manifest.get("entries") or [])
        if len(entries) > self._limits.max_file_count:
            raise WorkspaceQuotaExceededError(
                f"Snapshot exceeds max_file_count ({self._limits.max_file_count})"
            )
        seen_paths: set[str] = set()
        for entry in entries:
            path = normalize_workspace_path(entry["path"])
            if path in seen_paths:
                raise CommandValidationError(f"Duplicate path in manifest: {path}")
            seen_paths.add(path)
            size = int(entry["sizeBytes"])
            if size < 0 or size > self._limits.max_file_bytes:
                raise WorkspaceQuotaExceededError(f"Snapshot file exceeds max_file_bytes: {path}")
        if sum(int(entry["sizeBytes"]) for entry in entries) > self._limits.max_workspace_bytes:
            raise WorkspaceQuotaExceededError("Snapshot exceeds max_workspace_bytes")
        now = utc_now_iso()
        restored: list[dict[str, Any]] = []
        for entry in entries:
            path = normalize_workspace_path(entry["path"])
            content_hash = entry["contentHash"]
            if not self._files.exists(content_hash):
                raise CommandValidationError(f"Snapshot blob missing for path: {path}")
            record: dict[str, Any] = {
                "schemaVersion": "1.0.0",
                "workspaceId": workspace_id,
                "path": path,
                "contentHash": content_hash,
                "contentReference": entry.get("contentReference")
                or opaque_content_reference(content_hash),
                "sizeBytes": int(entry["sizeBytes"]),
                "origin": entry["origin"],
                "writePolicy": entry["writePolicy"],
                "modifiedByUser": bool(entry.get("modifiedByUser", False)),
                "createdAt": now,
                "updatedAt": now,
                "updatedBy": actor,
            }
            if entry.get("generatedFrom"):
                record["generatedFrom"] = entry["generatedFrom"]
            if entry.get("mediaType"):
                record["mediaType"] = entry["mediaType"]
            restored.append(record)
        self._kernel.replace_workspace_files(workspace_id, restored)
        return restored

    def unreferenced_content_hashes(self) -> set[str]:
        """Return store hashes not referenced by mutable files or snapshots."""
        referenced = self._kernel.list_referenced_content_hashes()
        listing = getattr(self._files, "list_content_hashes", None)
        if listing is None:
            return set()
        return set(listing()) - referenced

    def _require_filesystem(self, workspace_id: str) -> dict[str, Any]:
        workspace = self._kernel.get_workspace(workspace_id)
        if not is_filesystem_workspace(workspace):
            raise WorkspaceNotFilesystemError("Workspace does not support filesystem operations")
        return workspace

    def _check_versions(
        self,
        *,
        workspace: dict[str, Any],
        draft: dict[str, Any],
        expected_draft_version: int,
        base_artifact_version: int,
        base_project_state_version: int,
    ) -> None:
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

    @staticmethod
    def _assert_mutable(record: dict[str, Any], *, allow_user_edit: bool) -> None:
        policy = record.get("writePolicy")
        if policy == "READ_ONLY":
            raise WorkspaceWritePolicyError("File is READ_ONLY and cannot be mutated")
        if policy not in WRITE_POLICIES:
            raise WorkspaceWritePolicyError("File has an unknown write policy")
        if not allow_user_edit:
            raise WorkspaceWritePolicyError("Mutation is not permitted")

    def _bump_draft(
        self,
        *,
        workspace: dict[str, Any],
        draft: dict[str, Any],
        actor: dict[str, Any],
        now: str,
        file: dict[str, Any] | None,
    ) -> dict[str, Any]:
        draft = dict(draft)
        draft["draftVersion"] = int(draft["draftVersion"]) + 1
        draft["validationState"] = "unvalidated"
        draft["updatedAt"] = now
        draft["updatedBy"] = actor
        if (
            not isinstance(draft.get("content"), dict)
            or draft["content"].get("kind") != "filesystem"
        ):
            draft["content"] = filesystem_draft_content()
        self._kernel.update_draft(draft)
        workspace = dict(workspace)
        workspace["status"] = "dirty"
        workspace["updatedAt"] = now
        self._kernel.update_workspace(workspace)
        self._projection.update_after_write(workspace["projectId"])
        result: dict[str, Any] = {"workspace": workspace, "draft": draft}
        if file is not None:
            result["file"] = file
        return result
