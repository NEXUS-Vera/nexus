"""Deterministic Firmware scaffold profiles (Phase 15B).

Application-owned templates only — no PlatformIO execution, no MCU selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexus_persistence.file_store.hashing import blob_digest

# Explicit versioned profile id — not inferred from Components/Electrical.
PLATFORMIO_ARDUINO_ESP32_V1 = "platformio-arduino-esp32-v1"
PLATFORMIO_ARDUINO_ESP32_V1_VERSION = "1.0.0"

PLATFORMIO_INI_BYTES = (
    b"[env:nexus]\n"
    b"platform = espressif32\n"
    b"board = esp32dev\n"
    b"framework = arduino\n"
    b"monitor_speed = 115200\n"
)

MAIN_CPP_BYTES = (
    b"#include <Arduino.h>\n"
    b"\n"
    b"void setup() {\n"
    b"    Serial.begin(115200);\n"
    b"}\n"
    b"\n"
    b"void loop() {\n"
    b"}\n"
)

PLATFORMIO_INI_PATH = "platformio.ini"
MAIN_CPP_PATH = "src/main.cpp"


@dataclass(frozen=True)
class ScaffoldFileSpec:
    path: str
    content: bytes
    media_type: str

    @property
    def content_hash(self) -> str:
        return blob_digest(self.content)


@dataclass(frozen=True)
class FirmwareScaffoldProfile:
    profile_id: str
    profile_version: str
    display_name: str
    toolchain: str
    language: str
    framework: str
    platform: str
    board: str
    monitor_speed: int
    files: tuple[ScaffoldFileSpec, ...]

    @property
    def generated_from(self) -> str:
        return f"{self.profile_id}@{self.profile_version}"

    def target_paths(self) -> tuple[str, ...]:
        return tuple(spec.path for spec in self.files)

    def file_by_path(self) -> dict[str, ScaffoldFileSpec]:
        return {spec.path: spec for spec in self.files}

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "profileId": self.profile_id,
            "profileVersion": self.profile_version,
            "displayName": self.display_name,
            "toolchain": self.toolchain,
            "language": self.language,
            "framework": self.framework,
            "platform": self.platform,
            "board": self.board,
            "monitorSpeed": self.monitor_speed,
            "targetPaths": list(self.target_paths()),
            "generatedFrom": self.generated_from,
        }


PLATFORMIO_ARDUINO_ESP32_PROFILE = FirmwareScaffoldProfile(
    profile_id=PLATFORMIO_ARDUINO_ESP32_V1,
    profile_version=PLATFORMIO_ARDUINO_ESP32_V1_VERSION,
    display_name="PlatformIO · ESP32 · Arduino",
    toolchain="platformio",
    language="cpp",
    framework="arduino",
    platform="espressif32",
    board="esp32dev",
    monitor_speed=115200,
    files=(
        ScaffoldFileSpec(
            path=PLATFORMIO_INI_PATH,
            content=PLATFORMIO_INI_BYTES,
            media_type="text/plain",
        ),
        ScaffoldFileSpec(
            path=MAIN_CPP_PATH,
            content=MAIN_CPP_BYTES,
            media_type="text/x-c++src",
        ),
    ),
)

_PROFILES: dict[str, FirmwareScaffoldProfile] = {
    PLATFORMIO_ARDUINO_ESP32_V1: PLATFORMIO_ARDUINO_ESP32_PROFILE,
}

DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID = PLATFORMIO_ARDUINO_ESP32_V1


def get_firmware_scaffold_profile(
    profile_id: str | None = None,
) -> FirmwareScaffoldProfile:
    key = profile_id or DEFAULT_FIRMWARE_SCAFFOLD_PROFILE_ID
    profile = _PROFILES.get(key)
    if profile is None:
        raise KeyError(f"Unknown firmware scaffold profile: {key}")
    return profile


def materialize_firmware_scaffold_files(
    profile_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic path/content/hash records for the profile."""
    profile = get_firmware_scaffold_profile(profile_id)
    return [
        {
            "path": spec.path,
            "content": spec.content,
            "contentHash": spec.content_hash,
            "mediaType": spec.media_type,
            "sizeBytes": len(spec.content),
        }
        for spec in profile.files
    ]
