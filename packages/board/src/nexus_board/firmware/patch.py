"""Firmware patch proposal validation and deterministic generation (Phase 15C)."""

from __future__ import annotations

import json
from typing import Any, Protocol

from nexus_persistence.errors import ArtifactNotFoundError, ArtifactVersionNotFoundError
from nexus_persistence.file_store.hashing import blob_digest

from nexus_board.errors import (
    FirmwarePatchGenerationError,
    FirmwarePatchStaleError,
    FirmwarePatchValidationError,
)
from nexus_board.firmware.scaffold import (
    MAIN_CPP_PATH,
    PLATFORMIO_INI_BYTES,
    PLATFORMIO_INI_PATH,
)
from nexus_board.paths import WorkspacePathError, normalize_workspace_path
from nexus_board.services.filesystem_limits import WorkspaceFilesystemLimits

FIRMWARE_PATCH_GENERATOR_ID = "firmware-patch-generator-v1"
FIRMWARE_PATCH_GENERATOR_VERSION = "1.0.0"
MAX_PATCH_OPERATIONS = 32
MAX_CONTEXT_FILES = 32
MAX_CONTEXT_FILE_BYTES = 32_768
MAX_CONTEXT_ARTIFACT_BYTES = 131_072
MAX_CONTEXT_SNAPSHOT_FILES = 256
MAX_REQUEST_BYTES = 8_192

CONTEXT_ARTIFACT_TYPES = (
    "project-brief",
    "requirement-set",
    "component-plan",
    "functional-architecture",
    "electrical-architecture",
    "physical-architecture",
    "test-plan",
)


class _FileStore(Protocol):
    def get(self, content_hash: str) -> bytes: ...


class _ProjectStore(Protocol):
    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...


def _text_hash(text: str) -> str:
    return blob_digest(text.encode("utf-8"))


def _decode_text(data: bytes, *, path: str) -> str:
    if b"\x00" in data:
        raise FirmwarePatchValidationError(f"Binary content rejected for path: {path}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FirmwarePatchValidationError(f"Non-UTF-8 content rejected for path: {path}") from exc


def snapshot_manifest_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    content = snapshot.get("content") or {}
    if content.get("kind") != "filesystem":
        raise FirmwarePatchValidationError("Base snapshot must be a filesystem snapshot")
    manifest = content.get("filesystemManifest") or {}
    entries = manifest.get("entries") or []
    return {str(entry["path"]): entry for entry in entries}


def read_snapshot_file_bytes(
    *,
    file_store: _FileStore,
    entry: dict[str, Any],
) -> bytes:
    return file_store.get(str(entry["contentHash"]))


def read_snapshot_file_text(
    *,
    file_store: _FileStore,
    entry: dict[str, Any],
    path: str,
) -> str:
    return _decode_text(read_snapshot_file_bytes(file_store=file_store, entry=entry), path=path)


def assemble_firmware_generation_context(
    *,
    project_store: _ProjectStore,
    project_id: str,
    base_snapshot: dict[str, Any],
    requested_change: str,
    file_store: _FileStore,
) -> dict[str, Any]:
    """Structured generation context for the firmware patch generator."""
    if len(requested_change.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise FirmwarePatchGenerationError("Firmware request exceeds byte limit")
    input_refs: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    try:
        approved_plan = project_store.get_artifact(project_id, "execution-plan")
    except ArtifactNotFoundError:
        approved_plan = None
    if approved_plan is not None and approved_plan.get("approvalStatus") != "user-approved":
        raise FirmwarePatchGenerationError("Firmware context requires a user-approved plan")
    selected = []
    if approved_plan is not None:
        selected.append(approved_plan)
        # Resolve the reviewed versions, never silently substitute current domain content.
        sources = approved_plan["content"]["plan"]["sourceArtifacts"]
        if len(sources) > 32:
            raise FirmwarePatchGenerationError("Approved plan has too many source artifacts")
        for source in sources:
            for kind in (
                *CONTEXT_ARTIFACT_TYPES,
                "next-action",
                "risk-register",
                "firmware",
                "analysis",
            ):
                try:
                    candidate = project_store.get_artifact(
                        project_id, kind, version=source["artifactVersion"]
                    )
                except (ArtifactNotFoundError, ArtifactVersionNotFoundError):
                    continue
                if candidate["artifactId"] == source["artifactId"]:
                    if kind in CONTEXT_ARTIFACT_TYPES:
                        selected.append(candidate)
                    break
            else:
                raise FirmwarePatchGenerationError(
                    f"Approved plan source artifact is unavailable: {source}"
                )
    else:
        for kind in CONTEXT_ARTIFACT_TYPES:
            try:
                selected.append(project_store.get_artifact(project_id, kind))
            except ArtifactNotFoundError:
                continue
    context_bytes = 0
    for artifact in selected:
        artifact_type = artifact["artifactType"]
        context_bytes += len(
            json.dumps(artifact.get("content"), ensure_ascii=False).encode("utf-8")
        )
        if context_bytes > MAX_CONTEXT_ARTIFACT_BYTES:
            raise FirmwarePatchGenerationError("Firmware artifact context exceeds byte limit")
        input_refs.append(
            {
                "artifactType": artifact_type,
                "artifactVersion": int(artifact["artifactVersion"]),
                "artifactId": artifact["artifactId"],
            }
        )
        artifacts[artifact_type] = artifact.get("content")

    # Reviewed plan sources remain explicit; current revisions are also supplied to
    # authoring/repair so a historical approval cannot hide newer project context.
    current_artifacts = {}
    for kind in CONTEXT_ARTIFACT_TYPES:
        try:
            current = project_store.get_artifact(project_id, kind)
        except ArtifactNotFoundError:
            continue
        ref = {
            "artifactType": kind,
            "artifactId": current["artifactId"],
            "artifactVersion": current["artifactVersion"],
        }
        current_artifacts[kind] = current["content"]
        context_bytes += len(json.dumps(current["content"], ensure_ascii=False).encode("utf-8"))
        if context_bytes > MAX_CONTEXT_ARTIFACT_BYTES:
            raise FirmwarePatchGenerationError("Firmware artifact context exceeds byte limit")
        if ref not in input_refs:
            input_refs.append(ref)

    manifest = snapshot_manifest_index(base_snapshot)
    if len(manifest) > MAX_CONTEXT_SNAPSHOT_FILES:
        raise FirmwarePatchGenerationError("Firmware snapshot exceeds context file limit")
    snapshot_files: list[dict[str, Any]] = []
    for path in sorted(manifest):
        entry = manifest[path]
        snapshot_files.append(
            {
                "path": path,
                "contentHash": entry["contentHash"],
                "sizeBytes": int(entry.get("sizeBytes", 0)),
            }
        )

    file_contents: dict[str, str] = {}
    context_paths = [
        path
        for path in sorted(manifest)
        if path == PLATFORMIO_INI_PATH
        or path.startswith("src/")
        or path.startswith("include/")
        or path.startswith("lib/")
        or path.startswith("test/")
    ]
    for path in context_paths[:MAX_CONTEXT_FILES]:
        entry = manifest[path]
        size = int(entry.get("sizeBytes", 0))
        if size > MAX_CONTEXT_FILE_BYTES:
            continue
        try:
            file_contents[path] = read_snapshot_file_text(
                file_store=file_store,
                entry=entry,
                path=path,
            )
        except FirmwarePatchValidationError:
            # Context may include binary/non-UTF8 files; skip them.
            continue

    return {
        "schemaVersion": "1.0.0",
        "requestedChange": requested_change,
        "inputArtifactReferences": input_refs,
        "artifacts": artifacts,
        "currentArtifacts": current_artifacts,
        "baseSnapshotId": base_snapshot["snapshotId"],
        "snapshotFiles": snapshot_files,
        "fileContents": file_contents,
    }


def _platformio_ini_with_baud(base_text: str, baud: int) -> str:
    lines = base_text.splitlines()
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith("monitor_speed"):
            out.append(f"monitor_speed = {baud}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"monitor_speed = {baud}")
    text = "\n".join(out)
    if base_text.endswith("\n"):
        text += "\n"
    return text


def _main_cpp_with_baud(base_text: str, baud: int) -> str:
    return base_text.replace("Serial.begin(115200)", f"Serial.begin({baud})")


_MPU6050_MAIN_CPP = (
    "#include <Arduino.h>\n"
    "#include <Wire.h>\n"
    "\n"
    "static const uint8_t MPU6050_ADDR = 0x68;\n"
    "\n"
    "void setup() {\n"
    "    Serial.begin(115200);\n"
    "    Wire.begin();\n"
    "    Wire.beginTransmission(MPU6050_ADDR);\n"
    "    Wire.write(0x6B);\n"
    "    Wire.write(0x00);\n"
    "    Wire.endTransmission(true);\n"
    "}\n"
    "\n"
    "void loop() {\n"
    "}\n"
)

_ACCEL_HELPER_MAIN_CPP = (
    "#include <Arduino.h>\n"
    "#include <Wire.h>\n"
    "\n"
    "static const uint8_t MPU6050_ADDR = 0x68;\n"
    "\n"
    "struct AccelSample {\n"
    "    int16_t x;\n"
    "    int16_t y;\n"
    "    int16_t z;\n"
    "};\n"
    "\n"
    "bool readAcceleration(AccelSample &sample) {\n"
    "    Wire.beginTransmission(MPU6050_ADDR);\n"
    "    Wire.write(0x3B);\n"
    "    if (Wire.endTransmission(false) != 0) {\n"
    "        return false;\n"
    "    }\n"
    "    if (Wire.requestFrom(MPU6050_ADDR, 6) != 6) {\n"
    "        return false;\n"
    "    }\n"
    "    sample.x = (Wire.read() << 8) | Wire.read();\n"
    "    sample.y = (Wire.read() << 8) | Wire.read();\n"
    "    sample.z = (Wire.read() << 8) | Wire.read();\n"
    "    return true;\n"
    "}\n"
    "\n"
    "void setup() {\n"
    "    Serial.begin(115200);\n"
    "    Wire.begin();\n"
    "    Wire.beginTransmission(MPU6050_ADDR);\n"
    "    Wire.write(0x6B);\n"
    "    Wire.write(0x00);\n"
    "    Wire.endTransmission(true);\n"
    "}\n"
    "\n"
    "void loop() {\n"
    "    AccelSample sample{};\n"
    "    if (readAcceleration(sample)) {\n"
    '        Serial.printf("accel x=%d y=%d z=%d\\n", sample.x, sample.y, sample.z);\n'
    "    }\n"
    "    delay(500);\n"
    "}\n"
)


def generate_firmware_patch_operations(
    *,
    requested_change: str,
    base_snapshot: dict[str, Any],
    file_store: _FileStore,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic patch generator for tests and environments without a live model."""
    _ = context
    manifest = snapshot_manifest_index(base_snapshot)
    lower = requested_change.lower()
    operations: list[dict[str, Any]] = []

    if "9600" in lower and PLATFORMIO_INI_PATH in manifest:
        entry = manifest[PLATFORMIO_INI_PATH]
        base_text = read_snapshot_file_text(
            file_store=file_store,
            entry=entry,
            path=PLATFORMIO_INI_PATH,
        )
        replacement = _platformio_ini_with_baud(base_text, 9600)
        operations.append(
            {
                "operationType": "replace-file",
                "path": PLATFORMIO_INI_PATH,
                "expectedBaseHash": entry["contentHash"],
                "content": replacement,
                "contentHash": _text_hash(replacement),
            }
        )
        if MAIN_CPP_PATH in manifest:
            main_entry = manifest[MAIN_CPP_PATH]
            main_base = read_snapshot_file_text(
                file_store=file_store,
                entry=main_entry,
                path=MAIN_CPP_PATH,
            )
            main_replacement = _main_cpp_with_baud(main_base, 9600)
            if main_replacement != main_base:
                operations.append(
                    {
                        "operationType": "replace-file",
                        "path": MAIN_CPP_PATH,
                        "expectedBaseHash": main_entry["contentHash"],
                        "content": main_replacement,
                        "contentHash": _text_hash(main_replacement),
                    }
                )
    elif any(token in lower for token in ("mpu6050", "i2c")) and "acceleration" not in lower:
        if MAIN_CPP_PATH not in manifest:
            raise FirmwarePatchValidationError(
                "Cannot initialize MPU6050: src/main.cpp is missing from base snapshot"
            )
        main_entry = manifest[MAIN_CPP_PATH]
        operations.append(
            {
                "operationType": "replace-file",
                "path": MAIN_CPP_PATH,
                "expectedBaseHash": main_entry["contentHash"],
                "content": _MPU6050_MAIN_CPP,
                "contentHash": _text_hash(_MPU6050_MAIN_CPP),
            }
        )
    elif "acceleration" in lower and "helper" in lower:
        if MAIN_CPP_PATH not in manifest:
            raise FirmwarePatchValidationError(
                "Cannot add acceleration helper: src/main.cpp is missing from base snapshot"
            )
        main_entry = manifest[MAIN_CPP_PATH]
        operations.append(
            {
                "operationType": "replace-file",
                "path": MAIN_CPP_PATH,
                "expectedBaseHash": main_entry["contentHash"],
                "content": _ACCEL_HELPER_MAIN_CPP,
                "contentHash": _text_hash(_ACCEL_HELPER_MAIN_CPP),
            }
        )
    else:
        note_path = "generated/request-note.txt"
        if note_path in manifest:
            raise FirmwarePatchValidationError(f"Default patch target already exists: {note_path}")
        note_content = f"# Requested firmware change\n\n{requested_change.strip()}\n"
        operations.append(
            {
                "operationType": "create-file",
                "path": note_path,
                "content": note_content,
                "contentHash": _text_hash(note_content),
            }
        )

    if not operations:
        raise FirmwarePatchValidationError("Patch generator produced no operations")
    return operations


def materialize_model_patch_operations(
    *,
    generated: dict[str, Any],
    base_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Materialize model DTO operations into validated patch operations."""
    raw_ops = generated.get("operations")
    if not isinstance(raw_ops, list) or not raw_ops:
        raise FirmwarePatchGenerationError("Model returned no patch operations")
    if len(raw_ops) > MAX_PATCH_OPERATIONS:
        raise FirmwarePatchGenerationError(
            f"Model returned too many operations ({len(raw_ops)} > {MAX_PATCH_OPERATIONS})"
        )
    manifest = snapshot_manifest_index(base_snapshot)
    ops: list[dict[str, Any]] = []
    for item in raw_ops:
        if not isinstance(item, dict):
            raise FirmwarePatchGenerationError("Model operation must be an object")
        op_type = str(item.get("operationType", "")).strip()
        path = normalize_workspace_path(str(item.get("path", "")))
        if op_type == "create-file":
            content = item.get("content")
            if not isinstance(content, str):
                raise FirmwarePatchGenerationError(f"create-file requires text content ({path})")
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
                raise FirmwarePatchGenerationError(f"replace-file requires text content ({path})")
            entry = manifest.get(path)
            if entry is None:
                raise FirmwarePatchGenerationError(
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
                raise FirmwarePatchGenerationError(
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
        raise FirmwarePatchGenerationError(f"Unsupported model operation type: {op_type!r}")
    return ops


def validate_firmware_patch_proposal(
    proposal: dict[str, Any],
    *,
    base_snapshot: dict[str, Any],
    limits: WorkspaceFilesystemLimits | None = None,
) -> None:
    """Deterministic semantic validation against an immutable base snapshot."""
    limits = limits or WorkspaceFilesystemLimits()
    if proposal.get("artifactType") != "firmware":
        raise FirmwarePatchValidationError("Patch proposals must target artifact type firmware")
    if proposal.get("baseSnapshotId") != base_snapshot.get("snapshotId"):
        raise FirmwarePatchValidationError("Proposal baseSnapshotId does not match base snapshot")
    if base_snapshot.get("workspaceId") != proposal.get("workspaceId"):
        raise FirmwarePatchValidationError("Base snapshot belongs to a different workspace")
    if base_snapshot.get("projectId") != proposal.get("projectId"):
        raise FirmwarePatchValidationError("Base snapshot belongs to a different project")

    operations = proposal.get("operations") or []
    if not operations:
        raise FirmwarePatchValidationError("Patch proposal must include at least one operation")
    if len(operations) > MAX_PATCH_OPERATIONS:
        raise FirmwarePatchValidationError(
            f"Patch proposal exceeds max operations ({MAX_PATCH_OPERATIONS})"
        )

    manifest = snapshot_manifest_index(base_snapshot)
    seen_paths: set[str] = set()
    total_text_bytes = 0
    for operation in operations:
        op_type = operation.get("operationType")
        if op_type not in {"create-file", "replace-file", "delete-file"}:
            raise FirmwarePatchValidationError(f"Unsupported operation type: {op_type!r}")
        try:
            path = normalize_workspace_path(str(operation.get("path", "")))
        except WorkspacePathError as exc:
            raise FirmwarePatchValidationError(str(exc)) from exc
        if path in seen_paths:
            raise FirmwarePatchValidationError(f"Duplicate patch operation for path: {path}")
        seen_paths.add(path)

        if op_type == "create-file":
            if path in manifest:
                raise FirmwarePatchValidationError(
                    f"create-file target already exists in base snapshot: {path}"
                )
            content = operation.get("content")
            if not isinstance(content, str):
                raise FirmwarePatchValidationError(f"create-file missing text content: {path}")
            if b"\x00" in content.encode("utf-8"):
                raise FirmwarePatchValidationError(f"Binary content rejected for path: {path}")
            content_hash = operation.get("contentHash")
            if content_hash != _text_hash(content):
                raise FirmwarePatchValidationError(
                    f"create-file contentHash mismatch for path: {path}"
                )
            total_text_bytes += len(content.encode("utf-8"))
            if len(content.encode("utf-8")) > limits.max_file_bytes:
                raise FirmwarePatchValidationError(f"create-file content exceeds limit: {path}")

        elif op_type == "replace-file":
            entry = manifest.get(path)
            if entry is None:
                raise FirmwarePatchValidationError(
                    f"replace-file target missing from base snapshot: {path}"
                )
            expected = operation.get("expectedBaseHash")
            if expected != entry["contentHash"]:
                raise FirmwarePatchValidationError(
                    f"replace-file expectedBaseHash mismatch for path: {path}"
                )
            content = operation.get("content")
            if not isinstance(content, str):
                raise FirmwarePatchValidationError(f"replace-file missing text content: {path}")
            if b"\x00" in content.encode("utf-8"):
                raise FirmwarePatchValidationError(f"Binary content rejected for path: {path}")
            content_hash = operation.get("contentHash")
            if content_hash != _text_hash(content):
                raise FirmwarePatchValidationError(
                    f"replace-file contentHash mismatch for path: {path}"
                )
            total_text_bytes += len(content.encode("utf-8"))
            if len(content.encode("utf-8")) > limits.max_file_bytes:
                raise FirmwarePatchValidationError(f"replace-file content exceeds limit: {path}")

        elif op_type == "delete-file":
            entry = manifest.get(path)
            if entry is None:
                raise FirmwarePatchValidationError(
                    f"delete-file target missing from base snapshot: {path}"
                )
            expected = operation.get("expectedBaseHash")
            if expected != entry["contentHash"]:
                raise FirmwarePatchValidationError(
                    f"delete-file expectedBaseHash mismatch for path: {path}"
                )

    if total_text_bytes > limits.max_workspace_bytes:
        raise FirmwarePatchValidationError("Patch proposal total text bytes exceed workspace limit")


def check_patch_apply_staleness(
    *,
    proposal: dict[str, Any],
    get_current_file: Any,
) -> None:
    """Reject apply when current workspace bytes diverge from proposal base hashes."""
    for operation in proposal.get("operations") or []:
        op_type = operation.get("operationType")
        path = normalize_workspace_path(str(operation["path"]))
        current = get_current_file(path)
        if op_type == "create-file":
            if current is not None:
                raise FirmwarePatchStaleError(
                    f"create-file target now exists; proposal is stale for path: {path}"
                )
            continue
        expected = operation.get("expectedBaseHash")
        if current is None:
            raise FirmwarePatchStaleError(
                f"Patch target missing from workspace; proposal is stale for path: {path}"
            )
        if current.get("contentHash") != expected:
            raise FirmwarePatchStaleError(
                f"Workspace content changed since proposal base; stale path: {path}"
            )


def default_platformio_ini_text() -> str:
    return PLATFORMIO_INI_BYTES.decode("utf-8")


__all__ = [
    "FIRMWARE_PATCH_GENERATOR_ID",
    "FIRMWARE_PATCH_GENERATOR_VERSION",
    "MAX_PATCH_OPERATIONS",
    "CONTEXT_ARTIFACT_TYPES",
    "assemble_firmware_generation_context",
    "check_patch_apply_staleness",
    "generate_firmware_patch_operations",
    "materialize_model_patch_operations",
    "read_snapshot_file_text",
    "snapshot_manifest_index",
    "validate_firmware_patch_proposal",
]
