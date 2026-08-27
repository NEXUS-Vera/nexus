#!/usr/bin/env python3
"""Deterministic PlatformIO stub for offline ``make check`` (Phase 15E).

Simulates ``pio run`` / ``pio test`` without network or real toolchain installs.
Activated when ``NEXUS_FIRMWARE_USE_STUB`` is enabled (default in tests).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BUILD_ENV = "nexus"
BUILD_DIR = Path(f".pio/build/{BUILD_ENV}")
ELF_PATH = BUILD_DIR / "firmware.elf"
BIN_PATH = BUILD_DIR / "firmware.bin"
MAIN_CPP = Path("src/main.cpp")
PLATFORMIO_INI = Path("platformio.ini")
TEST_FILE = Path("test/test_nexus.cpp")


def _maybe_delay() -> None:
    raw = os.environ.get("NEXUS_FIRMWARE_STUB_DELAY_MS", "").strip()
    if not raw:
        return
    try:
        delay = int(raw)
    except ValueError:
        return
    if delay <= 0:
        return
    time.sleep(delay / 1000.0)


def _fail(msg: str, *, path: str | None = None, line: int = 1, col: int = 1) -> int:
    if path:
        print(f"{path}:{line}:{col}: error: {msg}", file=sys.stderr)
    else:
        print(f"error: {msg}", file=sys.stderr)
    return 1


def _cmd_run() -> int:
    _maybe_delay()
    if not PLATFORMIO_INI.is_file():
        return _fail("platformio.ini not found")
    if not MAIN_CPP.is_file():
        return _fail("src/main.cpp not found", path="src/main.cpp")
    source = MAIN_CPP.read_text(encoding="utf-8")
    if "NEXUS_COMPILE_ERROR" in source:
        return _fail("expected ';' before '}'", path="src/main.cpp", line=4, col=5)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ELF_PATH.write_bytes(b"\x7fELF\x01NEXUS_FIRMWARE_STUB")
    BIN_PATH.write_bytes(b"\x00NEXUS_BIN_STUB")
    print("Processing nexus (platform: espressif32; board: esp32dev; framework: arduino)")
    print("Building .pio/build/nexus/firmware.elf")
    print("Building .pio/build/nexus/firmware.bin")
    print("========================= [SUCCESS] Took 0.42 seconds =========================")
    return 0


def _cmd_test() -> int:
    _maybe_delay()
    if not TEST_FILE.is_file():
        return _fail(f"missing test file: {TEST_FILE}")
    content = TEST_FILE.read_text(encoding="utf-8")
    print("Testing env:nexus...")
    if "NEXUS_TEST_FAIL" in content:
        print("test/test_nexus.cpp:5: Failure", file=sys.stderr)
        print("========================= [FAILED] Took 0.12 seconds =========================", file=sys.stderr)
        return 1
    print("test/test_nexus.cpp .. PASSED")
    print("========================= [PASSED] Took 0.12 seconds =========================")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        print("usage: platformio_stub.py run|test [-e env]", file=sys.stderr)
        return 2
    sub = args[0]
    if sub == "run":
        return _cmd_run()
    if sub == "test":
        return _cmd_test()
    print(f"unsupported stub command: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
