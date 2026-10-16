"""Deterministic golden Risk Register for esp32-imu-vibration-monitor."""

from __future__ import annotations

from typing import Any

from nexus_board.verification.risk_scoring import (
    compute_risk_priority,
    compute_risk_register_summary,
)


def build_golden_vibration_risk_register_content() -> dict[str, Any]:
    risks = [
        _risk(
            "risk_16GOLDENK1I2CPIN00000000001",
            "K1",
            "Incorrect I²C pin configuration",
            "SDA/SCL wired to non-canonical pins breaks MPU6050 communication.",
            "electrical",
            ["R1", "R2"],
            ["ESP32", "MPU6050"],
            "possible",
            "high",
            "Use canonical GPIO21 (SDA) / GPIO22 (SCL) mapping.",
            ["T2"],
            "mitigated",
        ),
        _risk(
            "risk_16GOLDENK2MPUINIT0000000001",
            "K2",
            "MPU6050 initialization failure",
            "Sensor may fail to ACK or leave firmware without a readiness marker.",
            "firmware",
            ["R4"],
            ["MPU6050"],
            "possible",
            "high",
            "Explicit startup failure path and NEXUS_MPU_READY marker.",
            ["T4"],
            "mitigating",
        ),
        _risk(
            "risk_16GOLDENK3TELEM000000000001",
            "K3",
            "Telemetry format mismatch",
            "Analysis or consumers may break if field names drift from golden schema.",
            "data-quality",
            ["R5", "R8"],
            ["ESP32"],
            "unlikely",
            "medium",
            "Stable telemetry schema: time_ms, accel_x_g, accel_y_g, accel_z_g.",
            ["T5"],
            "mitigating",
        ),
        _risk(
            "risk_16GOLDENK4SAMPLERATE0000001",
            "K4",
            "Sampling-rate drift",
            "Blocking work in the main loop can push the interval away from 50 Hz.",
            "performance",
            ["R6"],
            ["ESP32"],
            "possible",
            "high",
            "Monotonic 20 ms scheduling and interval validation via T6.",
            ["T6"],
            "open",
        ),
        _risk(
            "risk_16GOLDENK5NOISE000000000001",
            "K5",
            "Excessive accelerometer noise",
            "Stationary accel_x RMS may exceed the R7 0.10 g limit.",
            "performance",
            ["R7"],
            ["MPU6050"],
            "unlikely",
            "high",
            "Mounting/filtering plus deterministic Analysis verification (T7).",
            ["T7"],
            "mitigated",
        ),
        _risk(
            "risk_16GOLDENK6SIMDIVERGE0000001",
            "K6",
            "Simulator/hardware divergence",
            "Wokwi/surrogate results may not match physical MPU6050/ESP32 behavior.",
            "integration",
            ["R1", "R4", "R7"],
            ["ESP32", "MPU6050"],
            "possible",
            "medium",
            "Defer closure until physical hardware validation exists.",
            [],
            "monitoring",
            residual="No physical-hardware evidence in Phase 17; remains unresolved.",
        ),
    ]
    summary = compute_risk_register_summary(risks)
    return {
        "schemaVersion": "1.0.0",
        "riskRegisterId": "rreg_16GOLDENVIBRATIONMONITOR01",
        "title": "ESP32 IMU Vibration Monitor Risks",
        "summary": summary,
        "risks": risks,
        "provenance": {
            "generatedBy": "fixture",
            "notes": (
                "Phase 17 golden risks; K6 intentionally unresolved without hardware evidence."
            ),
        },
    }


def _risk(
    risk_id: str,
    display_id: str,
    title: str,
    description: str,
    category: str,
    reqs: list[str],
    components: list[str],
    likelihood: str,
    severity: str,
    mitigation: str,
    verification_tests: list[str],
    status: str,
    residual: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "riskId": risk_id,
        "displayId": display_id,
        "title": title,
        "description": description,
        "category": category,
        "linkedRequirementIds": reqs,
        "linkedComponentIds": components,
        "linkedArchitectureRefs": [],
        "linkedTestIds": verification_tests,
        "likelihood": likelihood,
        "severity": severity,
        "priorityScore": compute_risk_priority(severity=severity, likelihood=likelihood),
        "mitigation": mitigation,
        "verificationTestIds": verification_tests,
        "status": status,
        "evidenceReferences": [],
    }
    if residual:
        item["residualRisk"] = residual
    return item
