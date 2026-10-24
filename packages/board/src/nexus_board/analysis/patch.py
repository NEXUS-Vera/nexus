"""Analysis patch proposal validation + deterministic generation (Phase 16C)."""

from __future__ import annotations

import json
from typing import Any

from nexus_persistence.errors import ArtifactNotFoundError
from nexus_persistence.file_store.hashing import blob_digest

from nexus_board.errors import (
    AnalysisPatchGenerationError,
    AnalysisPatchStaleError,
    AnalysisPatchValidationError,
)
from nexus_board.paths import WorkspacePathError, normalize_workspace_path
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits

ANALYSIS_PATCH_GENERATOR_ID = "analysis-patch-generator-v1"
ANALYSIS_PATCH_GENERATOR_VERSION = "1.0.0"

SNAPSHOT_REASON_PATCH_BASE = "analysis-patch-base"

MAX_PATCH_OPERATIONS = 32
MAX_CONTEXT_ARTIFACT_BYTES = 131_072
MAX_CONTEXT_FILES = 32
MAX_CONTEXT_FILE_BYTES = 32_768


CONTEXT_FILE_PATHS = (
    "analysis.py",
    "README.md",
)


def _text_hash(text: str) -> str:
    return blob_digest(text.encode("utf-8"))


def _decode_text(data: bytes, *, path: str) -> str:
    if b"\x00" in data:
        raise AnalysisPatchValidationError(f"Binary content rejected for path: {path}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AnalysisPatchValidationError(f"Non-UTF-8 content rejected for path: {path}") from exc


def snapshot_manifest_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    content = snapshot.get("content") or {}
    if content.get("kind") != "filesystem":
        raise AnalysisPatchValidationError("Base snapshot must be a filesystem snapshot")
    manifest = content.get("filesystemManifest") or {}
    entries = manifest.get("entries") or []
    return {str(entry["path"]): entry for entry in entries}


def read_snapshot_file_bytes(*, file_store: Any, entry: dict[str, Any]) -> bytes:
    content_hash = str(entry["contentHash"])
    data = file_store.get(content_hash)
    if not isinstance(data, (bytes, bytearray)):
        raise AnalysisPatchValidationError(f"Missing or invalid file-store blob for {content_hash}")
    return bytes(data)


def read_snapshot_file_text(*, file_store: Any, entry: dict[str, Any], path: str) -> str:
    return _decode_text(read_snapshot_file_bytes(file_store=file_store, entry=entry), path=path)


def assemble_analysis_generation_context(
    *,
    project_store: Any,
    project_id: str,
    base_snapshot: dict[str, Any],
    requested_change: str,
    file_store: Any,
) -> dict[str, Any]:
    """Structured generation context for an analysis patch proposal."""
    artifacts = {}
    refs = []
    context_bytes = 0
    for kind in (
        "requirement-set",
        "component-plan",
        "electrical-architecture",
        "execution-plan",
        "test-plan",
    ):
        try:
            artifact = project_store.get_artifact(project_id, kind)
        except ArtifactNotFoundError:
            continue
        context_bytes += len(json.dumps(artifact["content"], ensure_ascii=False).encode("utf-8"))
        if context_bytes > MAX_CONTEXT_ARTIFACT_BYTES:
            raise AnalysisPatchGenerationError("Analysis artifact context exceeds byte limit")
        artifacts[kind] = artifact["content"]
        refs.append(
            {
                "artifactType": kind,
                "artifactId": artifact["artifactId"],
                "artifactVersion": artifact["artifactVersion"],
            }
        )

    manifest = snapshot_manifest_index(base_snapshot)
    snapshot_files = [
        {
            "path": path,
            "contentHash": entry["contentHash"],
            "sizeBytes": int(entry.get("sizeBytes", 0)),
            **({"generatedFrom": entry["generatedFrom"]} if entry.get("generatedFrom") else {}),
        }
        for path, entry in sorted(manifest.items())
    ]

    file_contents: dict[str, str] = {}
    for path in CONTEXT_FILE_PATHS:
        entry = manifest.get(path)
        if not entry:
            continue
        size = int(entry.get("sizeBytes", 0))
        if size > MAX_CONTEXT_FILE_BYTES:
            continue
        try:
            file_contents[path] = read_snapshot_file_text(
                file_store=file_store, entry=entry, path=path
            )
        except AnalysisPatchValidationError:
            continue

    return {
        "schemaVersion": "1.0.0",
        "requestedChange": requested_change,
        "inputArtifactReferences": refs,
        "artifacts": artifacts,
        "baseSnapshotId": base_snapshot["snapshotId"],
        "snapshotFiles": snapshot_files[:MAX_CONTEXT_FILES],
        "fileContents": file_contents,
    }


def generate_analysis_patch_operations(
    *,
    requested_change: str,
    base_snapshot: dict[str, Any],
    file_store: Any,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic patch generator for Analysis (fixture mode)."""
    _ = file_store
    _ = context
    manifest = snapshot_manifest_index(base_snapshot)

    requested_marker = requested_change.strip().replace("\n", " ")
    ops: list[dict[str, Any]] = []

    # Replace README with a stable change marker.
    readme_entry = manifest.get("README.md")
    if readme_entry:
        try:
            # Best-effort; if unreadable (binary), skip README patch.
            base_bytes = file_store.get(str(readme_entry["contentHash"]))
            base_readme = _decode_text(base_bytes, path="README.md")
        except Exception:
            base_readme = ""
        new_readme = (
            base_readme.rstrip() + "\n\n# Requested change\n" + requested_marker + "\n"
        ).lstrip()
        ops.append(
            {
                "operationType": "replace-file",
                "path": "README.md",
                "expectedBaseHash": readme_entry["contentHash"],
                "content": new_readme,
                "contentHash": _text_hash(new_readme),
            }
        )

    # Replace analysis.py similarly.
    analysis_entry = manifest.get("analysis.py")
    if analysis_entry:
        try:
            base_bytes = file_store.get(str(analysis_entry["contentHash"]))
            base_analysis = _decode_text(base_bytes, path="analysis.py")
        except Exception:
            base_analysis = ""
        new_analysis = (
            base_analysis.rstrip() + f"\n\n# Requested change: {requested_marker}\n"
        ).lstrip()
        ops.append(
            {
                "operationType": "replace-file",
                "path": "analysis.py",
                "expectedBaseHash": analysis_entry["contentHash"],
                "content": new_analysis,
                "contentHash": _text_hash(new_analysis),
            }
        )

    if not ops:
        raise AnalysisPatchGenerationError(
            "Deterministic analysis patch generator could not find "
            "README.md or analysis.py in base snapshot"
        )
    if len(ops) > MAX_PATCH_OPERATIONS:
        raise AnalysisPatchGenerationError("Generated too many operations")

    return ops


def validate_analysis_patch_proposal(
    proposal: dict[str, Any],
    *,
    base_snapshot: dict[str, Any],
    limits: WorkspaceFilesystemLimits,
) -> None:
    """Deterministic validation of patch operations against an immutable base snapshot."""
    if proposal.get("artifactType") != "analysis":
        raise AnalysisPatchValidationError("artifactType must be analysis")
    operations = proposal.get("operations")
    if not isinstance(operations, list) or not operations:
        raise AnalysisPatchValidationError("operations must be non-empty array")
    if len(operations) > MAX_PATCH_OPERATIONS:
        raise AnalysisPatchValidationError("Too many patch operations")

    manifest = snapshot_manifest_index(base_snapshot)
    targets: set[str] = set()
    for item in operations:
        if not isinstance(item, dict):
            raise AnalysisPatchValidationError("operation must be an object")
        op_type = str(item.get("operationType", "")).strip()
        try:
            path = normalize_workspace_path(str(item.get("path", "")))
        except WorkspacePathError as exc:
            raise AnalysisPatchValidationError(str(exc)) from exc
        if path in targets:
            raise AnalysisPatchValidationError(f"Duplicate operation target: {path}")
        targets.add(path)

        if len(path) > 1024:
            raise AnalysisPatchValidationError("Patch path too long")

        if op_type == "create-file":
            content = item.get("content")
            if not isinstance(content, str):
                raise AnalysisPatchValidationError(f"create-file requires text content ({path})")
            if "\x00" in content:
                raise AnalysisPatchValidationError(f"Binary content rejected ({path})")
            content_hash = item.get("contentHash")
            if not isinstance(content_hash, str) or content_hash != _text_hash(content):
                raise AnalysisPatchValidationError(f"Invalid contentHash for create-file ({path})")
            if manifest.get(path) is not None:
                raise AnalysisPatchValidationError(
                    f"create-file target already present in base snapshot: {path}"
                )
            continue

        if op_type == "replace-file":
            content = item.get("content")
            expected = item.get("expectedBaseHash")
            content_hash = item.get("contentHash")
            if not isinstance(content, str) or "\x00" in content:
                raise AnalysisPatchValidationError(f"replace-file requires utf-8 text ({path})")
            if not isinstance(expected, str):
                raise AnalysisPatchValidationError(
                    f"replace-file expectedBaseHash required ({path})"
                )
            if not isinstance(content_hash, str) or content_hash != _text_hash(content):
                raise AnalysisPatchValidationError(f"Invalid contentHash for replace-file ({path})")

            entry = manifest.get(path)
            if entry is None:
                raise AnalysisPatchValidationError(
                    f"replace-file target missing from base snapshot: {path}"
                )
            if str(entry.get("contentHash")) != expected:
                raise AnalysisPatchValidationError(f"Expected base hash mismatch ({path})")
            # File size bound for text content.
            if len(content.encode("utf-8")) > limits.max_file_bytes:
                raise AnalysisPatchValidationError(f"Patch content exceeds max_file_bytes ({path})")
            continue

        if op_type == "delete-file":
            expected = item.get("expectedBaseHash")
            if not isinstance(expected, str):
                raise AnalysisPatchValidationError(
                    f"delete-file expectedBaseHash required ({path})"
                )
            entry = manifest.get(path)
            if entry is None:
                raise AnalysisPatchValidationError(
                    f"delete-file target missing from base snapshot: {path}"
                )
            if str(entry.get("contentHash")) != expected:
                raise AnalysisPatchValidationError(f"Expected base hash mismatch ({path})")
            continue

        raise AnalysisPatchValidationError(f"Unsupported operation type: {op_type!r}")


def check_patch_apply_staleness(
    *,
    proposal: dict[str, Any],
    get_current_file: Any,
    base_snapshot: dict[str, Any],
) -> None:
    """Reject apply when workspace diverged from proposal base hashes."""
    operations = proposal.get("operations") or []
    manifest = snapshot_manifest_index(base_snapshot)
    _ = manifest

    for op in operations:
        if not isinstance(op, dict):
            continue
        op_type = str(op.get("operationType", "")).strip()
        try:
            path = normalize_workspace_path(str(op.get("path", "")))
        except WorkspacePathError as exc:
            raise AnalysisPatchValidationError(str(exc)) from exc
        manifest.get(path)
        if op_type == "replace-file":
            expected = op.get("expectedBaseHash")
            if not isinstance(expected, str):
                raise AnalysisPatchValidationError("replace-file expectedBaseHash missing")
            current = get_current_file(path)
            if not current:
                raise AnalysisPatchStaleError(f"replace-file target missing in workspace: {path}")
            if str(current.get("contentHash")) != expected:
                raise AnalysisPatchStaleError(f"replace-file stale content for: {path}")
        elif op_type == "delete-file":
            expected = op.get("expectedBaseHash")
            if not isinstance(expected, str):
                raise AnalysisPatchValidationError("delete-file expectedBaseHash missing")
            current = get_current_file(path)
            if not current:
                raise AnalysisPatchStaleError(f"delete-file target already missing: {path}")
            if str(current.get("contentHash")) != expected:
                raise AnalysisPatchStaleError(f"delete-file stale content for: {path}")
        elif op_type == "create-file":
            # create-file fails if already exists.
            current = get_current_file(path)
            if current is not None:
                raise AnalysisPatchStaleError(f"create-file target already exists: {path}")
        else:
            raise AnalysisPatchValidationError(f"Unsupported operation type: {op_type!r}")


def materialize_model_patch_operations(
    *,
    generated: dict[str, Any],
    base_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Materialize model DTO operations into validated analysis patch operations."""
    raw_ops = generated.get("operations")
    if not isinstance(raw_ops, list) or not raw_ops:
        raise AnalysisPatchGenerationError("Model returned no patch operations")
    if len(raw_ops) > MAX_PATCH_OPERATIONS:
        raise AnalysisPatchGenerationError(
            f"Model returned too many operations ({len(raw_ops)} > {MAX_PATCH_OPERATIONS})"
        )
    manifest = snapshot_manifest_index(base_snapshot)
    ops: list[dict[str, Any]] = []
    for item in raw_ops:
        if not isinstance(item, dict):
            raise AnalysisPatchGenerationError("Model operation must be an object")
        op_type = str(item.get("operationType", "")).strip()
        path = normalize_workspace_path(str(item.get("path", "")))
        if op_type == "create-file":
            content = item.get("content")
            if not isinstance(content, str):
                raise AnalysisPatchGenerationError(f"create-file requires text content ({path})")
            ops.append(
                {
                    "operationType": "create-file",
                    "path": path,
                    "content": content,
                    "contentHash": _text_hash(content),
                }
            )
            continue
        if op_type == "replace-file":
            content = item.get("content")
            if not isinstance(content, str):
                raise AnalysisPatchGenerationError(f"replace-file requires text content ({path})")
            entry = manifest.get(path)
            if entry is None:
                raise AnalysisPatchGenerationError(
                    f"replace-file target missing from base snapshot: {path}"
                )
            ops.append(
                {
                    "operationType": "replace-file",
                    "path": path,
                    "expectedBaseHash": entry["contentHash"],
                    "content": content,
                    "contentHash": _text_hash(content),
                }
            )
            continue
        if op_type == "delete-file":
            entry = manifest.get(path)
            if entry is None:
                raise AnalysisPatchGenerationError(
                    f"delete-file target missing from base snapshot: {path}"
                )
            ops.append(
                {
                    "operationType": "delete-file",
                    "path": path,
                    "expectedBaseHash": entry["contentHash"],
                }
            )
            continue
        raise AnalysisPatchGenerationError(f"Unsupported model operation type: {op_type!r}")
    return ops
