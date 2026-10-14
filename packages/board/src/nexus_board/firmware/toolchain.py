"""PlatformIO firmware compile/test toolchain mapping (Phase 15E).

Maps product operations ``firmware.compile`` and ``firmware.test`` to approved
ExecutionCommandSpec values. Never exposes arbitrary shell commands to callers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus_board.errors import (
    CommandValidationError,
    FirmwareTestNotConfiguredError,
    FirmwareToolchainValidationError,
)
from nexus_board.execution.command_spec import validate_command_spec
from nexus_board.firmware.patch import read_snapshot_file_text, snapshot_manifest_index
from nexus_board.firmware.scaffold import (
    MAIN_CPP_PATH,
    PLATFORMIO_ARDUINO_ESP32_V1,
    PLATFORMIO_ARDUINO_ESP32_V1_VERSION,
    PLATFORMIO_INI_PATH,
)

FIRMWARE_COMPILE_OPERATION = "firmware.compile"
FIRMWARE_TEST_OPERATION = "firmware.test"

# Snapshot reason conventions (Phase 15D/E).
SNAPSHOT_REASON_MANUAL = "manual"
SNAPSHOT_REASON_BEFORE_COMPILE = "before-compile"
SNAPSHOT_REASON_BEFORE_TEST = "before-test"
SNAPSHOT_REASON_BEFORE_RESTORE = "before-restore"
SNAPSHOT_REASON_PATCH_BASE = "firmware-patch-base"

BUILD_ENV = "nexus"
BUILD_ELF_PATH = f".pio/build/{BUILD_ENV}/firmware.elf"
BUILD_BIN_PATH = f".pio/build/{BUILD_ENV}/firmware.bin"

TEST_DIR = "test"
TEST_MAIN_PATH = f"{TEST_DIR}/test_nexus.cpp"

_STUB_SCRIPT = Path(__file__).resolve().parent / "platformio_stub.py"


def firmware_toolchain_profile() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "executionMode": "fixture" if _use_platformio_stub() else "platformio",
        "profileId": PLATFORMIO_ARDUINO_ESP32_V1,
        "profileVersion": PLATFORMIO_ARDUINO_ESP32_V1_VERSION,
        "platformioEnv": BUILD_ENV,
        "platform": "espressif32",
        "board": "esp32dev",
        "framework": "arduino",
        "declaredCompileOutputs": [
            {"path": BUILD_ELF_PATH, "kind": "artifact", "logicalName": "firmware.elf"},
            {"path": BUILD_BIN_PATH, "kind": "artifact", "logicalName": "firmware.bin"},
        ],
    }


def _use_platformio_stub() -> bool:
    raw = os.environ.get("NEXUS_FIRMWARE_USE_STUB", "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _pio_executable_and_args(operation: str) -> tuple[str, list[str]]:
    """Return approved executable/args for compile or test."""
    if operation == "compile":
        subcmd = "run"
        extra = ["-e", BUILD_ENV]
    elif operation == "test":
        subcmd = "test"
        extra = ["-e", BUILD_ENV]
    else:
        raise CommandValidationError(f"Unsupported firmware operation: {operation}")

    if _use_platformio_stub():
        return "python3", [str(_STUB_SCRIPT), subcmd, *extra]
    return "pio", [subcmd, *extra]


def build_firmware_command_spec(operation: str) -> dict[str, Any]:
    """Build a validated ExecutionCommandSpec for compile or test."""
    if operation not in {"compile", "test"}:
        raise CommandValidationError(f"Unsupported firmware operation: {operation}")
    executable, arguments = _pio_executable_and_args(operation)
    declared = [
        {"path": BUILD_ELF_PATH, "kind": "artifact"},
        {"path": BUILD_BIN_PATH, "kind": "artifact"},
    ]
    if operation == "test":
        declared = []
    env_entries: list[dict[str, str]] = [
        {"name": "PLATFORMIO_CORE_DIR", "value": "/opt/platformio"},
        {"name": "NEXUS_FIRMWARE_PROFILE", "value": PLATFORMIO_ARDUINO_ESP32_V1},
    ]
    spec = {
        "schemaVersion": "1.0.0",
        "executable": executable,
        "arguments": arguments,
        "workingDirectory": "",
        "environment": env_entries,
        "declaredOutputs": declared,
    }
    stub_delay = os.environ.get("NEXUS_FIRMWARE_STUB_DELAY_MS", "").strip()
    if stub_delay and _use_platformio_stub():
        env_entries.append({"name": "NEXUS_FIRMWARE_STUB_DELAY_MS", "value": stub_delay})
    return validate_command_spec(spec)


def validate_firmware_snapshot_for_toolchain(
    snapshot: dict[str, Any],
    *,
    file_store: Any,
    operation: str,
) -> None:
    """Application-side validation before starting compile/test."""
    manifest = snapshot_manifest_index(snapshot)
    if PLATFORMIO_INI_PATH not in manifest:
        raise FirmwareToolchainValidationError(
            f"Snapshot missing required file: {PLATFORMIO_INI_PATH}"
        )
    has_src = any(path.startswith("src/") for path in manifest)
    if not has_src:
        raise FirmwareToolchainValidationError("Snapshot missing required source under src/")
    if MAIN_CPP_PATH not in manifest:
        raise FirmwareToolchainValidationError(f"Snapshot missing required file: {MAIN_CPP_PATH}")
    if operation == "test" and TEST_MAIN_PATH not in manifest:
        raise FirmwareTestNotConfiguredError(
            f"Snapshot missing firmware test file: {TEST_MAIN_PATH}"
        )
    # Reject obvious binary-only main if we can read it.
    try:
        entry = manifest[MAIN_CPP_PATH]
        text = read_snapshot_file_text(
            file_store=file_store,
            entry=entry,
            path=MAIN_CPP_PATH,
        )
        if "NEXUS_COMPILE_ERROR" in text and operation == "compile":
            # Allow compile to proceed — toolchain should fail with compiler logs.
            pass
    except Exception:  # noqa: BLE001
        raise FirmwareToolchainValidationError(
            f"Cannot read snapshot source file: {MAIN_CPP_PATH}"
        ) from None


def snapshot_reason_for_operation(operation: str) -> str:
    if operation == "compile":
        return SNAPSHOT_REASON_BEFORE_COMPILE
    if operation == "test":
        return SNAPSHOT_REASON_BEFORE_TEST
    raise CommandValidationError(f"Unknown operation for snapshot reason: {operation}")
