"""Phase 15B deterministic firmware scaffold tests."""

from __future__ import annotations

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import WorkspaceScaffoldConflictError
from nexus_board.firmware.scaffold import (
    MAIN_CPP_BYTES,
    MAIN_CPP_PATH,
    PLATFORMIO_ARDUINO_ESP32_PROFILE,
    PLATFORMIO_ARDUINO_ESP32_V1,
    PLATFORMIO_INI_BYTES,
    PLATFORMIO_INI_PATH,
    get_firmware_scaffold_profile,
    materialize_firmware_scaffold_files,
)
from nexus_board.services.workspace_runtime import WorkspaceRuntimeCapabilityError
from nexus_persistence.file_store.hashing import blob_digest


def test_scaffold_profile_is_stable_and_deterministic() -> None:
    profile = get_firmware_scaffold_profile()
    assert profile.profile_id == PLATFORMIO_ARDUINO_ESP32_V1
    assert profile.profile_version == "1.0.0"
    assert profile.target_paths() == (PLATFORMIO_INI_PATH, MAIN_CPP_PATH)
    assert PLATFORMIO_INI_BYTES == (
        b"[env:nexus]\n"
        b"platform = espressif32\n"
        b"board = esp32dev\n"
        b"framework = arduino\n"
        b"monitor_speed = 115200\n"
    )
    assert MAIN_CPP_BYTES == (
        b"#include <Arduino.h>\n"
        b"\n"
        b"void setup() {\n"
        b"    Serial.begin(115200);\n"
        b"}\n"
        b"\n"
        b"void loop() {\n"
        b"}\n"
    )
    first = materialize_firmware_scaffold_files()
    second = materialize_firmware_scaffold_files()
    assert [item["path"] for item in first] == [item["path"] for item in second]
    assert [item["content"] for item in first] == [item["content"] for item in second]
    assert [item["contentHash"] for item in first] == [item["contentHash"] for item in second]
    assert first[0]["contentHash"] == blob_digest(PLATFORMIO_INI_BYTES)
    assert first[1]["contentHash"] == blob_digest(MAIN_CPP_BYTES)
    assert PLATFORMIO_ARDUINO_ESP32_PROFILE.generated_from == (
        f"{PLATFORMIO_ARDUINO_ESP32_V1}@1.0.0"
    )


def test_generate_scaffold_on_blank_firmware_workspace() -> None:
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    result = kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    assert result["status"] == "generated"
    assert result["generationId"].startswith("gen_")
    assert result["profile"]["profileId"] == PLATFORMIO_ARDUINO_ESP32_V1
    paths = {item["path"] for item in result["generatedFiles"]}
    assert paths == {PLATFORMIO_INI_PATH, MAIN_CPP_PATH}
    for item in result["generatedFiles"]:
        assert item["origin"] == "GENERATED"
        assert item["writePolicy"] == "REGENERATION_MANAGED"
        assert item["generatedFrom"] == f"{PLATFORMIO_ARDUINO_ESP32_V1}@1.0.0"

    listed = kernel.workspace_runtime.list_files(
        project_id=project_id, artifact_type="firmware"
    )
    assert {f["path"] for f in listed["files"]} == paths

    read_main = kernel.workspace_runtime.read_file(
        project_id=project_id, artifact_type="firmware", path=MAIN_CPP_PATH
    )
    assert read_main["content"] == MAIN_CPP_BYTES

    events, _ = kernel_store.list_project_events(project_id, limit=50)
    scaffold_events = [e for e in events if e["eventType"] == "workspace.scaffold-generated"]
    assert len(scaffold_events) == 1
    payload = scaffold_events[0]["payload"]
    assert payload["scaffoldProfileId"] == PLATFORMIO_ARDUINO_ESP32_V1
    assert payload["scaffoldProfileVersion"] == "1.0.0"
    assert payload["generationKind"] == "scaffold"
    assert payload["artifactId"] == binding["artifactId"]
    assert {f["path"] for f in payload["generatedFiles"]} == paths
    assert scaffold_events[0]["actor"]["actorId"] == user["actorId"]


def test_scaffold_preserves_unrelated_files_and_blocks_conflicts() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    binding = kernel.workspace_runtime.resolve_binding(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    acquire_edit_lease(
        kernel,
        project_id=project_id,
        artifact_id=binding["artifactId"],
        workspace_id=binding["workspaceId"],
        requested_by=user,
    )
    written = kernel.workspace_runtime.write_file(
        project_id=project_id,
        artifact_type="firmware",
        path="notes.txt",
        content=b"keep me\n",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    draft_version = int(written["draft"]["draftVersion"])
    generated = kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=draft_version,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert generated["status"] == "generated"
    listed = kernel.workspace_runtime.list_files(
        project_id=project_id, artifact_type="firmware"
    )
    assert {f["path"] for f in listed["files"]} == {
        "notes.txt",
        PLATFORMIO_INI_PATH,
        MAIN_CPP_PATH,
    }

    # Exact repeat → already-generated no-op.
    again = kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=int(generated["draft"]["draftVersion"]),
        base_artifact_version=1,
        base_project_state_version=1,
    )
    assert again["status"] == "already-generated"

    # Conflicting main.cpp content blocks generation.
    kernel2, _ps2, _ks2, project_id2 = build_test_kernel(auto_start_scheduler=False)
    user2 = actor("user")
    binding2 = kernel2.workspace_runtime.resolve_binding(
        project_id=project_id2, artifact_type="firmware", actor=user2
    )
    acquire_edit_lease(
        kernel2,
        project_id=project_id2,
        artifact_id=binding2["artifactId"],
        workspace_id=binding2["workspaceId"],
        requested_by=user2,
    )
    kernel2.workspace_runtime.write_file(
        project_id=project_id2,
        artifact_type="firmware",
        path=MAIN_CPP_PATH,
        content=b"// user file\n",
        actor=user2,
        expected_draft_version=1,
        base_artifact_version=1,
        base_project_state_version=1,
    )
    with pytest.raises(WorkspaceScaffoldConflictError):
        kernel2.workspace_runtime.generate_firmware_scaffold(
            project_id=project_id2,
            artifact_type="firmware",
            actor=user2,
            expected_draft_version=2,
            base_artifact_version=1,
            base_project_state_version=1,
        )


def test_scaffold_denied_for_non_firmware_artifact() -> None:
    kernel, _ps, _ks, project_id = build_test_kernel(auto_start_scheduler=False)
    user = actor("user")
    with pytest.raises(WorkspaceRuntimeCapabilityError):
        kernel.workspace_runtime.generate_firmware_scaffold(
            project_id=project_id,
            artifact_type="code-scratch",
            actor=user,
            expected_draft_version=1,
            base_artifact_version=1,
            base_project_state_version=1,
        )
