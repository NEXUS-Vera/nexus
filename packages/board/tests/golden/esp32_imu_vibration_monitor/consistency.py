"""Golden ESP32 IMU Vibration Monitor consistency validator (Phase 16I).

Test-harness only — does not special-case production runtime services.
"""

from __future__ import annotations

from typing import Any

GOLDEN_PROMPT = (
    "Build an ESP32-based vibration monitor using an MPU6050. "
    "It should stream acceleration telemetry and analyze stationary sensor noise "
    "to verify that accel_x RMS noise stays below 0.10 g."
)

TELEMETRY_FIELDS: tuple[str, ...] = ("time_ms", "accel_x_g", "accel_y_g", "accel_z_g")
ANALYSIS_OUTPUTS: tuple[str, ...] = (
    "outputs/summary.json",
    "outputs/processed.csv",
    "outputs/accel_plot.png",
)

EXPECTED: dict[str, Any] = {
    "sda_gpio": 21,
    "scl_gpio": 22,
    "uart_baud": 115200,
    "telemetry_fields": TELEMETRY_FIELDS,
    "r7_threshold_g": 0.10,
    "rms_definition": "demeaned",
    "analysis_outputs": ANALYSIS_OUTPUTS,
    "mcu_part": "FX-MCU-32",
    "imu_part": "FX-IMU-200",
}


def _req_map(artifacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    for art in artifacts:
        if art.get("artifactType") == "requirement-set":
            return {
                str(r.get("displayId")): r
                for r in (art.get("content") or {}).get("requirements") or []
                if isinstance(r, dict)
            }
    return {}


def _component_parts(artifacts: list[dict[str, Any]]) -> set[str]:
    parts: set[str] = set()
    for art in artifacts:
        if art.get("artifactType") != "component-plan":
            continue
        for cand in (art.get("content") or {}).get("candidates") or []:
            pn = cand.get("partNumber")
            if isinstance(pn, str):
                parts.add(pn)
    return parts


def validate_golden_consistency(
    *,
    artifacts: list[dict[str, Any]],
    firmware_source: str,
    analysis_source: str,
    analysis_summary: dict[str, Any] | None = None,
    wokwi_support: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Return a list of inconsistency findings (empty means consistent)."""
    findings: list[dict[str, str]] = []
    reqs = _req_map(artifacts)
    for display in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
        if display not in reqs:
            findings.append({"code": "MISSING_REQUIREMENT", "message": f"Missing {display}"})

    parts = _component_parts(artifacts)
    if EXPECTED["mcu_part"] not in parts:
        findings.append({"code": "WRONG_MCU", "message": f"Expected {EXPECTED['mcu_part']}"})
    if EXPECTED["imu_part"] not in parts:
        findings.append({"code": "WRONG_IMU", "message": f"Expected {EXPECTED['imu_part']}"})

    if "GPIO21" not in firmware_source and "PIN_SDA = 21" not in firmware_source:
        findings.append({"code": "FIRMWARE_SDA_MISMATCH", "message": "Firmware missing GPIO21/SDA=21"})
    if "GPIO22" not in firmware_source and "PIN_SCL = 22" not in firmware_source:
        findings.append({"code": "FIRMWARE_SCL_MISMATCH", "message": "Firmware missing GPIO22/SCL=22"})
    if "115200" not in firmware_source:
        findings.append({"code": "FIRMWARE_BAUD_MISMATCH", "message": "Firmware missing 115200 baud"})
    for field in TELEMETRY_FIELDS:
        # Firmware emits TEL,time,ax,ay,az — names documented in comments / Analysis schema.
        if field == "time_ms" and "TEL," not in firmware_source:
            findings.append({"code": "FIRMWARE_TELEM_MISSING", "message": "Missing TEL telemetry frame"})

    if "stationary_imu.csv" not in analysis_source:
        findings.append({"code": "ANALYSIS_DATASET_MISMATCH", "message": "Analysis must read stationary_imu.csv"})
    if "0.10" not in analysis_source and "THRESHOLD_G = 0.10" not in analysis_source:
        findings.append({"code": "ANALYSIS_THRESHOLD_MISMATCH", "message": "Analysis threshold must be 0.10 g"})
    if "demeaned" not in analysis_source:
        findings.append({"code": "ANALYSIS_RMS_DEFINITION", "message": "RMS definition must be demeaned"})

    if analysis_summary is not None:
        if analysis_summary.get("assessment") not in {"PASS", "FAIL", "INCONCLUSIVE"}:
            findings.append({"code": "SUMMARY_ASSESSMENT_MISSING", "message": "summary.json missing assessment"})
        if analysis_summary.get("authority") != "deterministic-code":
            findings.append({"code": "SUMMARY_AUTHORITY", "message": "assessment authority must be deterministic-code"})
        thr = analysis_summary.get("threshold_g")
        if thr is not None and float(thr) != EXPECTED["r7_threshold_g"]:
            findings.append({"code": "SUMMARY_THRESHOLD", "message": "summary threshold != R7 0.10 g"})
        if analysis_summary.get("assessment") != "PASS":
            findings.append(
                {
                    "code": "R7_NOT_PASS",
                    "message": f"Expected R7 PASS, got {analysis_summary.get('assessment')}",
                }
            )

    if wokwi_support is not None:
        status = str(wokwi_support.get("status") or wokwi_support.get("supportStatus") or "")
        if status.lower() in {"unsupported", "failed"}:
            findings.append({"code": "WOKWI_UNSUPPORTED", "message": f"Wokwi support={status}"})
        part_types = set(wokwi_support.get("partTypes") or [])
        if part_types and "wokwi-esp32-devkit-v1" not in part_types:
            findings.append({"code": "WOKWI_MCU_MISSING", "message": "Missing ESP32 Wokwi part"})
        if part_types and "wokwi-mpu6050" not in part_types:
            findings.append({"code": "WOKWI_IMU_MISSING", "message": "Missing MPU6050 Wokwi part"})

    return findings
