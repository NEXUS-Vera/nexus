"""Phase 15E firmware compile/test execution tests."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
from helpers import acquire_edit_lease, actor, build_test_kernel
from nexus_board.errors import FirmwareTestNotConfiguredError, FirmwareToolchainValidationError
from nexus_board.firmware.scaffold import MAIN_CPP_PATH
from nexus_board.firmware.toolchain import (
    BUILD_BIN_PATH,
    BUILD_ELF_PATH,
    FIRMWARE_COMPILE_OPERATION,
    FIRMWARE_TEST_OPERATION,
    SNAPSHOT_REASON_BEFORE_COMPILE,
    SNAPSHOT_REASON_BEFORE_TEST,
    build_firmware_command_spec,
)


def _wait_run(kernel: Any, run_id: str, *, timeout: float = 8.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run: dict[str, Any] = kernel.executions.get_run(run_id)
        if run["status"] not in {"queued", "starting", "running"}:
            return run
        time.sleep(0.05)
    final: dict[str, Any] = kernel.executions.get_run(run_id)
    return final


def _setup_scaffolded_firmware(
    kernel: Any, project_id: str, user: dict[str, Any]
) -> dict[str, Any]:
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
    kernel.workspace_runtime.generate_firmware_scaffold(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
        expected_draft_version=1,
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
    )
    return dict(binding)


def test_compile_command_spec_is_approved_and_fixed() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    spec = build_firmware_command_spec("compile")
    assert spec["executable"] == "python3"
    assert "run" in spec["arguments"]
    paths = {item["path"] for item in spec["declaredOutputs"]}
    assert BUILD_ELF_PATH in paths
    assert BUILD_BIN_PATH in paths


def test_compile_creates_snapshot_and_succeeds_with_stub() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)

    started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    assert started["toolchainProfile"]["executionMode"] == "fixture"
    assert started["operation"] == FIRMWARE_COMPILE_OPERATION
    snap_id = started["executionSnapshotId"]
    run_id = started["executionRun"]["executionRunId"]
    snapshots = kernel_store.list_snapshots(binding["workspaceId"])
    assert any(
        s["snapshotId"] == snap_id and s["reason"] == SNAPSHOT_REASON_BEFORE_COMPILE
        for s in snapshots
    )

    run = _wait_run(kernel, run_id)
    assert run["status"] == "completed"
    assert run["inputSnapshotId"] == snap_id

    logs = kernel.executions.list_logs(run_id, after_sequence=0, limit=200)
    text = "".join(chunk["content"] for chunk in logs["chunks"])
    assert "SUCCESS" in text

    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=run_id
    )["outputs"]
    output_names = {item.get("name") for item in outputs}
    assert any("firmware.elf" in str(name) for name in output_names)


def test_compile_failure_surfaces_compiler_logs() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)
    draft = kernel_store.get_draft(binding["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path=MAIN_CPP_PATH,
        content=b"#include <Arduino.h>\n// NEXUS_COMPILE_ERROR\nvoid setup() {}\nvoid loop() {}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    run = _wait_run(kernel, started["executionRun"]["executionRunId"])
    assert run["status"] == "failed"
    logs = kernel.executions.list_logs(run["executionRunId"], after_sequence=0, limit=200)
    text = "".join(chunk["content"] for chunk in logs["chunks"])
    assert "error:" in text


def test_test_requires_test_file() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel, _ps, _kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user)
    with pytest.raises(FirmwareTestNotConfiguredError):
        kernel.workspace_runtime.test_firmware(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
        )


def test_test_passes_with_fixture_file() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
    kernel, _ps, kernel_store, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    binding = _setup_scaffolded_firmware(kernel, project_id, user)
    draft = kernel_store.get_draft(binding["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path="test/test_nexus.cpp",
        content=b"// passing test\nvoid test_ok() {}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )

    started = kernel.workspace_runtime.test_firmware(
        project_id=project_id,
        artifact_type="firmware",
        actor=user,
    )
    assert started["operation"] == FIRMWARE_TEST_OPERATION
    run = _wait_run(kernel, started["executionRun"]["executionRunId"])
    assert run["status"] == "completed"
    snapshots = kernel_store.list_snapshots(binding["workspaceId"])
    assert any(s["reason"] == SNAPSHOT_REASON_BEFORE_TEST for s in snapshots)


def test_missing_platformio_ini_rejected_before_execution() -> None:
    os.environ["NEXUS_FIRMWARE_USE_STUB"] = "1"
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
    draft = kernel_store.get_draft(binding["workspaceId"])
    kernel.filesystem.write_file(
        workspace_id=binding["workspaceId"],
        path=MAIN_CPP_PATH,
        content=b"int main(){return 0;}\n",
        actor=user,
        expected_draft_version=int(draft["draftVersion"]),
        base_artifact_version=int(binding["baseArtifactVersion"]),
        base_project_state_version=int(binding["baseProjectStateVersion"]),
        origin="USER",
        write_policy="USER_EDITABLE",
    )
    with pytest.raises(FirmwareToolchainValidationError):
        kernel.workspace_runtime.compile_firmware(
            project_id=project_id,
            artifact_type="firmware",
            actor=user,
        )


def test_real_pio_path_and_core_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    import shutil

    from nexus_board.execution.command_spec import environment_entries_to_mapping
    from nexus_board.execution.env import build_sandbox_environment

    pio = tmp_path / "pio"
    pio.write_text("#!/bin/sh\nexit 0\n")
    pio.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    monkeypatch.setenv("PLATFORMIO_CORE_DIR", str(tmp_path / "core"))
    spec = build_firmware_command_spec("compile")
    env = build_sandbox_environment(environment_entries_to_mapping(spec["environment"]))
    assert shutil.which(spec["executable"], path=env["PATH"]) == str(pio)
    assert env["PLATFORMIO_CORE_DIR"] == str(tmp_path / "core")
    monkeypatch.delenv("PLATFORMIO_CORE_DIR")
    default_spec = build_firmware_command_spec("compile")
    from pathlib import Path

    default_env = environment_entries_to_mapping(default_spec["environment"])
    assert default_env["PLATFORMIO_CORE_DIR"] == str(Path("~/.platformio").expanduser().resolve())
    pio.unlink()
    with pytest.raises(FirmwareToolchainValidationError, match="pio is not installed"):
        build_firmware_command_spec("compile")
    monkeypatch.delenv("NEXUS_FIRMWARE_USE_STUB")
    with pytest.raises(FirmwareToolchainValidationError):
        build_firmware_command_spec("compile")


@pytest.mark.parametrize(
    "elf_bytes, expected_status", [(6_300_000, "completed"), (11_000_000, "failed")]
)
def test_compile_stores_real_sized_elf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, elf_bytes: int, expected_status: str
) -> None:
    pio = tmp_path / "pio"
    pio.write_text(
        "#!/usr/bin/python3\nfrom pathlib import Path\n"
        f"p=Path({BUILD_ELF_PATH!r}); p.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_bytes(b'\\x7fELF' + bytes({elf_bytes}))\n"
        f"Path({BUILD_BIN_PATH!r}).write_bytes(bytes(1_000_000))\n"
    )
    pio.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    kernel, *_rest, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user)
    started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    run_id = started["executionRun"]["executionRunId"]
    assert _wait_run(kernel, run_id)["status"] == expected_status
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=run_id
    )["outputs"]
    assert len(outputs) == (2 if expected_status == "completed" else 0)


@pytest.mark.parametrize("flag", ["-Woverflow", "-Wdiv-by-zero", "-Wunused-variable"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_compiler_warning_classifies_build_before_output_promotion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, flag: str, stream: str
) -> None:
    pio = tmp_path / "pio"
    pio.write_text(
        "#!/usr/bin/python3\nimport sys\nfrom pathlib import Path\n"
        f"print('src/main.cpp: warning: arithmetic diagnostic [{flag}]', file=sys.{stream})\n"
        f"p=Path({BUILD_ELF_PATH!r}); p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_bytes(b'ELF')\n"
        f"Path({BUILD_BIN_PATH!r}).write_bytes(b'BIN')\n"
    )
    pio.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("NEXUS_FIRMWARE_USE_STUB", "0")
    kernel, *_rest, project_id = build_test_kernel(auto_start_scheduler=True)
    user = actor("user")
    _setup_scaffolded_firmware(kernel, project_id, user)
    started = kernel.workspace_runtime.compile_firmware(
        project_id=project_id, artifact_type="firmware", actor=user
    )
    run_id = started["executionRun"]["executionRunId"]
    run = _wait_run(kernel, run_id)
    unsafe = flag != "-Wunused-variable"
    assert run["status"] == ("failed" if unsafe else "completed")
    outputs = kernel.workspace_runtime.list_outputs_for_run(
        project_id=project_id, execution_run_id=run_id
    )["outputs"]
    assert len(outputs) == (0 if unsafe else 2)
    if unsafe:
        assert run["error"]["code"] == "FIRMWARE_UNSAFE_COMPILER_WARNING"
        assert flag in run["error"]["message"]
    logs = kernel.executions.list_logs(run_id, after_sequence=0, limit=200)
    assert flag in "".join(chunk["content"] for chunk in logs["chunks"])
