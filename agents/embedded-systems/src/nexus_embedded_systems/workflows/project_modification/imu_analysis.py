#!/usr/bin/env python3
"""ESP32 IMU analysis, reused from the Phase 16I golden analysis.

RMS noise definition: demeaned accel_x (about sample mean).
R7 criterion: accel_x_rms_noise_g < 0.10
Assessment is deterministic code — never LLM prose.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

DATA = Path("data/stationary_imu.csv")
OUT = Path("outputs")
THRESHOLD_G = 0.10
REQUIRED = ("time_s", "accel_x_g", "accel_y_g", "accel_z_g")


def main() -> None:
    data_path = Path("data/serial.log") if Path("data/serial.log").is_file() else DATA
    if not data_path.is_file():
        raise SystemExit(f"missing input: {DATA}")
    import hashlib

    raw = data_path.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    if data_path.name == "serial.log":
        frames = [line.removeprefix("TEL,") for line in lines if line.startswith("TEL,")]
        if not frames or any("NEXUS_MPU_" in line and "FAIL" in line for line in lines):
            raise SystemExit("missing or failed telemetry")
        lines = [",".join(REQUIRED), *frames]
    rows = list(csv.DictReader(lines))
    if not rows:
        raise SystemExit("empty dataset")
    for col in REQUIRED:
        if col not in rows[0]:
            raise SystemExit(f"missing column: {col}")

    xs = [float(r["accel_x_g"]) for r in rows]
    ys = [float(r["accel_y_g"]) for r in rows]
    zs = [float(r["accel_z_g"]) for r in rows]
    ts = [float(r["time_s"]) for r in rows]
    if not all(math.isfinite(value) for value in xs + ys + zs + ts):
        raise SystemExit("nonfinite telemetry")
    mean_x = sum(xs) / len(xs)
    rms = math.sqrt(sum((v - mean_x) ** 2 for v in xs) / len(xs))
    sampling_hz = (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) >= 2 and ts[-1] > ts[0] else 0.0
    assessment = "PASS" if rms < THRESHOLD_G else "FAIL"

    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "inputPath": str(data_path),
        "inputSha256": hashlib.sha256(raw).hexdigest(),
        "status": "ok",
        "requirementId": "R7",
        "metricId": "accel_x_rms_noise_g",
        "accel_x_rms_noise_g": rms,
        "threshold_g": THRESHOLD_G,
        "operator": "<",
        "assessment": assessment,
        "authority": "deterministic-code",
        "rmsNoiseDefinition": "demeaned",
        "sampleCount": len(xs),
        "sampling_hz": sampling_hz,
        "mean_accel_x_g": mean_x,
        "mean_accel_y_g": sum(ys) / len(ys),
        "mean_accel_z_g": sum(zs) / len(zs),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "results.json").write_text(
        json.dumps({"status": "ok", "assessment": assessment}, indent=2) + "\n", encoding="utf-8"
    )

    with (OUT / "processed.csv").open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=["time_s", "accel_x_g", "accel_x_demeaned_g"])
        w.writeheader()
        for t, x in zip(ts, xs, strict=True):
            w.writerow(
                {
                    "time_s": f"{t:.4f}",
                    "accel_x_g": f"{x:.6f}",
                    "accel_x_demeaned_g": f"{(x - mean_x):.6f}",
                }
            )

    # Prefer matplotlib when available; else write a tiny deterministic PNG.
    plot_path = OUT / "accel_plot.png"
    try:
        import matplotlib  # pyright: ignore[reportMissingImports] — optional plotting dependency

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # pyright: ignore[reportMissingImports]

        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(ts, xs, label="accel_x_g")
        ax.set_xlabel("time_s")
        ax.set_ylabel("accel_x_g")
        ax.set_title("Stationary IMU accel_x")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_path)
        plt.close(fig)
    except Exception:
        import struct
        import zlib

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        width = height = 16
        raw = b"".join(
            b"\x00" + bytes([min(255, int(abs(xs[i % len(xs)]) * 2000))] * width)
            for i in range(height)
        )
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
        plot_path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )

    (OUT / "note.txt").write_text(
        f"R7 assessment={assessment} rms={rms:.6f}g threshold={THRESHOLD_G}g\n", encoding="utf-8"
    )
    print(f"NEXUS_ANALYSIS_R7 assessment={assessment} rms={rms:.6f}")


if __name__ == "__main__":
    main()
