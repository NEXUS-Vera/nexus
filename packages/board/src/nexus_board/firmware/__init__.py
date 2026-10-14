"""Firmware application helpers (Phase 15)."""

from __future__ import annotations

from nexus_board.firmware.scaffold import (
    DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID,
    PLATFORMIO_ARDUINO_ESP32_PROFILE,
    PLATFORMIO_ARDUINO_ESP32_V1,
    FirmwareScaffoldProfile,
    get_firmware_scaffold_profile,
    materialize_firmware_scaffold_files,
)

__all__ = [
    "DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID",
    "PLATFORMIO_ARDUINO_ESP32_PROFILE",
    "PLATFORMIO_ARDUINO_ESP32_V1",
    "FirmwareScaffoldProfile",
    "get_firmware_scaffold_profile",
    "materialize_firmware_scaffold_files",
]
