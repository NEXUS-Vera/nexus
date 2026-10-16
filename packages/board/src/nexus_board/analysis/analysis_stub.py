#!/usr/bin/env python3
"""Deterministic Analysis Python stub for offline ``make check`` (Phase 16D/G).

Simulates ``python3 analysis.py`` without requiring a real Python analysis
environment. Activated when ``NEXUS_ANALYSIS_USE_STUB`` is enabled (default in tests).

Writes the approved Analysis output manifest:
  outputs/results.json, summary.json, processed.csv, accel_plot.png, note.txt
"""

from __future__ import annotations

import csv
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path

ANALYSIS_PY = Path("analysis.py")
OUTPUTS_DIR = Path("outputs")
RESULTS_JSON = OUTPUTS_DIR / "results.json"
SUMMARY_JSON = OUTPUTS_DIR / "summary.json"
PROCESSED_CSV = OUTPUTS_DIR / "processed.csv"
PLOT_PNG = OUTPUTS_DIR / "accel_plot.png"
NOTE_TXT = OUTPUTS_DIR / "note.txt"
SENSOR_CSV = Path("data/sensor.csv")


def _maybe_delay() -> None:
    raw = os.environ.get("NEXUS_ANALYSIS_STUB_DELAY_MS", "").strip()
    if not raw:
        return
    try:
        delay = int(raw)
    except ValueError:
        return
    if delay <= 0:
        return
    time.sleep(delay / 1000.0)


def _minimal_png(width: int = 8, height: int = 8) -> bytes:
    """Return a tiny deterministic valid PNG (solid gray)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + (b"\x80" * width) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _read_sensor_rows() -> list[dict[str, str]]:
    if not SENSOR_CSV.is_file():
        return []
    with SENSOR_CSV.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    _maybe_delay()
    if not ANALYSIS_PY.is_file():
        print(f"error: {ANALYSIS_PY} not found", file=sys.stderr)
        return 1

    source = ANALYSIS_PY.read_text(encoding="utf-8")
    if "NEXUS_RUN_ERROR" in source:
        print("Traceback (most recent call last):", file=sys.stderr)
        print('  File "analysis.py", line 1, in <module>', file=sys.stderr)
        print("RuntimeError: analysis.py contains NEXUS_RUN_ERROR marker", file=sys.stderr)
        return 1

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = _read_sensor_rows()
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row.get("accel_x", "0") or "0"))
        except ValueError:
            continue
    mean = sum(values) / len(values) if values else 0.0
    summary = {
        "status": "ok",
        "stub": True,
        "count": len(values),
        "mean_accel_x": mean,
        "min_accel_x": min(values) if values else None,
        "max_accel_x": max(values) if values else None,
    }
    RESULTS_JSON.write_text(
        json.dumps({"status": "ok", "stub": True}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_JSON.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with PROCESSED_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "accel_x", "accel_x_sq"])
        writer.writeheader()
        for row in rows:
            try:
                ax = float(row.get("accel_x", "0") or "0")
            except ValueError:
                ax = 0.0
            writer.writerow(
                {
                    "time_s": row.get("time_s", ""),
                    "accel_x": row.get("accel_x", ""),
                    "accel_x_sq": f"{ax * ax:.6f}",
                }
            )
    PLOT_PNG.write_bytes(_minimal_png())
    NOTE_TXT.write_text("Nexus analysis stub completed.\n", encoding="utf-8")
    print("Nexus analysis stub: wrote outputs/{results,summary,processed,accel_plot,note}")
    print("========================= [SUCCESS] =========================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
