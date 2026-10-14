"""Materialize immutable filesystem snapshots into ephemeral execution trees."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Protocol

from nexus_persistence.file_store.hashing import blob_digest, opaque_content_reference
from nexus_persistence.file_store.protocol import FileStore

from nexus_board.errors import BoardError
from nexus_board.paths import normalize_workspace_path


class SnapshotMaterializationError(BoardError):
    code = "SNAPSHOT_MATERIALIZATION_FAILED"


class _KernelStore(Protocol):
    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...


def materialize_filesystem_snapshot(
    *,
    kernel_store: _KernelStore,
    file_store: FileStore,
    snapshot_id: str,
    workspace_bytes_limit: int,
    parent_dir: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Materialize snapshot files into a new ephemeral directory.

    Returns ``(root_path, manifest)``. Caller must delete ``root_path``.
    """
    # Lazy import avoids circular import through nexus_board.services.__init__.
    from nexus_board.services.filesystem_service import build_filesystem_manifest

    snapshot = kernel_store.get_snapshot(snapshot_id)
    content = snapshot.get("content") or {}
    if content.get("kind") != "filesystem":
        raise SnapshotMaterializationError("Execution requires a filesystem WorkspaceSnapshot")
    manifest = content.get("filesystemManifest")
    if not isinstance(manifest, dict):
        raise SnapshotMaterializationError("Filesystem snapshot missing filesystemManifest")
    entries = manifest.get("entries") or []
    if not isinstance(entries, list):
        raise SnapshotMaterializationError("filesystemManifest.entries must be an array")

    # Recompute digest from entries to detect corruption / drift.
    normalized_records: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        record: dict[str, Any] = {
            "path": entry["path"],
            "contentHash": entry["contentHash"],
            "contentReference": entry.get("contentReference")
            or opaque_content_reference(str(entry["contentHash"])),
            "sizeBytes": int(entry["sizeBytes"]),
            "origin": entry.get("origin") or "USER",
            "writePolicy": entry.get("writePolicy") or "USER_EDITABLE",
            "modifiedByUser": bool(entry.get("modifiedByUser", False)),
        }
        if entry.get("generatedFrom"):
            record["generatedFrom"] = entry["generatedFrom"]
        if entry.get("mediaType"):
            record["mediaType"] = entry["mediaType"]
        normalized_records.append(record)
    recomputed = build_filesystem_manifest(normalized_records)
    expected = manifest.get("manifestDigest")
    if expected != recomputed["manifestDigest"]:
        raise SnapshotMaterializationError("Workspace manifest digest mismatch")

    total_bytes = 0
    root = Path(tempfile.mkdtemp(prefix="nexus-exec-", dir=parent_dir)).resolve()
    try:
        for entry in entries:
            if not isinstance(entry, dict):
                raise SnapshotMaterializationError("Invalid manifest entry")
            path = normalize_workspace_path(str(entry["path"]))
            content_hash = str(entry["contentHash"])
            size_bytes = int(entry["sizeBytes"])
            total_bytes += size_bytes
            if total_bytes > workspace_bytes_limit:
                raise SnapshotMaterializationError("Materialized workspace exceeds workspaceBytes")
            data = file_store.get(content_hash)
            if blob_digest(data) != content_hash:
                raise SnapshotMaterializationError(f"Blob hash mismatch for snapshot path {path}")
            if len(data) != size_bytes:
                raise SnapshotMaterializationError(f"Blob size mismatch for snapshot path {path}")
            raw_target = root / path
            if raw_target.is_symlink() or any(
                p.is_symlink() for p in raw_target.parents if p != root and root in p.parents
            ):
                raise SnapshotMaterializationError("Refusing to write through symlink")
            target = raw_target.resolve()
            if not str(target).startswith(str(root) + os.sep) and target != root:
                raise SnapshotMaterializationError("Materialized path escaped execution root")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Refuse to write through existing symlinks.
            if target.exists() and target.is_symlink():
                raise SnapshotMaterializationError("Refusing to write through symlink")
            target.write_bytes(data)
            # Ensure no symlink was created by the write path.
            if target.is_symlink():
                raise SnapshotMaterializationError("Symlink created during materialization")
        return root, recomputed
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def cleanup_materialization(root: Path | None) -> None:
    if root is None:
        return
    shutil.rmtree(root, ignore_errors=True)
