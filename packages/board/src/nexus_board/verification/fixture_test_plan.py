"""Deterministic golden Test Plan for esp32-imu-vibration-monitor (T1–T8)."""

from __future__ import annotations

from typing import Any

from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)


def build_golden_vibration_test_plan_content(
    *,
    requirements: list[dict[str, Any]] | None = None,
    apply_r7_pass: bool = False,
    analysis_metric: float | None = 0.015676464092948383,
    apply_structural_pass: bool = False,
) -> dict[str, Any]:
    """Build T1–T8 covering R1–R8 with typed criteria.

    By default TestCases start ``ready`` so Phase 17F product promotion can close
    evidence. Optional flags apply deterministic PASS for fixtures/demos.
    """

    cases = [
        _case(
            "test_16GOLDENT1I2CCOMM00000000001",
            "T1",
            "I²C communication",
            ["R1"],
            ["ESP32", "MPU6050"],
            "simulation",
            "MPU6050 initialization succeeds over I²C.",
            {
                "criterionType": "contains",
                "marker": "NEXUS_MPU_READY",
            },
            status="ready",
        ),
        _case(
            "test_16GOLDENT2PINMAP000000000001",
            "T2",
            "I²C pin mapping",
            ["R2"],
            ["ESP32", "MPU6050"],
            "inspection",
            "SDA → GPIO21 and SCL → GPIO22.",
            {
                "criterionType": "structural-mapping",
                "signal": "SDA",
                "expectedMapping": "GPIO21",
            },
            status="passed" if apply_structural_pass else "ready",
            assessment="PASS" if apply_structural_pass else None,
            actual="GPIO21" if apply_structural_pass else None,
            authority="deterministic-code" if apply_structural_pass else None,
            procedure=["Inspect Electrical Architecture / Wokwi pin mapping for SDA/SCL."],
        ),
        _case(
            "test_16GOLDENT3BAUD00000000000001",
            "T3",
            "Serial baud rate",
            ["R3"],
            ["ESP32"],
            "inspection",
            "Serial initializes at 115200 baud.",
            {
                "criterionType": "exact-match",
                "expectedValue": "115200",
            },
            status="ready",
        ),
        _case(
            "test_16GOLDENT4MPUINIT00000000001",
            "T4",
            "MPU6050 initialization",
            ["R4"],
            ["MPU6050"],
            "execution-output",
            "Firmware reports NEXUS_MPU_READY before streaming.",
            {
                "criterionType": "contains",
                "marker": "NEXUS_MPU_READY",
            },
            status="ready",
        ),
        _case(
            "test_16GOLDENT5TELEM0000000000001",
            "T5",
            "Telemetry schema",
            ["R5"],
            ["ESP32", "MPU6050"],
            "execution-output",
            "Telemetry includes time_ms, accel_x_g, accel_y_g, accel_z_g.",
            {
                "criterionType": "contains",
                "marker": "accel_x_g",
            },
            status="ready",
        ),
        _case(
            "test_16GOLDENT6SAMPLE000000000001",
            "T6",
            "Sampling frequency",
            ["R6"],
            ["ESP32"],
            "analysis",
            "Telemetry interval approximately 50 Hz (45–55 Hz).",
            {
                "criterionType": "range",
                "metricId": "sampling_hz",
                "minValue": 45,
                "maxValue": 55,
                "unit": "Hz",
            },
            status="ready",
        ),
        _case(
            "test_16GOLDENT7NOISE0000000000001",
            "T7",
            "Stationary accel_x RMS noise",
            ["R7"],
            ["MPU6050"],
            "analysis",
            "Demeaned accel_x RMS noise < 0.10 g.",
            {
                "criterionType": "numeric-comparison",
                "metricId": "accel_x_rms_noise_g",
                "operator": "<",
                "expectedValue": 0.10,
                "unit": "g",
            },
            status="passed" if apply_r7_pass else "ready",
            assessment="PASS" if apply_r7_pass else None,
            actual=(
                f"{analysis_metric:.4f} g"
                if apply_r7_pass and analysis_metric is not None
                else None
            ),
            authority="deterministic-code" if apply_r7_pass else None,
            evidence=(
                [
                    {
                        "schemaVersion": "1.0.0",
                        "evidenceId": "evi_16GOLDENT7ANALYSISOUT000001",
                        "sourceType": "test-result",
                        "sourceId": "exec_GOLDEN_ANALYSIS_R7",
                        "evidenceStrength": "direct",
                        "supportedClaim": "accel_x_rms_noise_g < 0.10 g",
                        "sourceLocator": "outputs/summary.json",
                    }
                ]
                if apply_r7_pass
                else []
            ),
            finding=(
                "Stationary accel_x RMS remained comfortably below the R7 limit."
                if apply_r7_pass
                else None
            ),
        ),
        _case(
            "test_16GOLDENT8OUTPUTS00000000001",
            "T8",
            "Analysis deliverables",
            ["R8"],
            [],
            "analysis",
            "summary.json, processed.csv, and accel_plot.png are produced.",
            {
                "criterionType": "existence",
                "outputName": "summary.json,processed.csv,accel_plot.png",
            },
            status="passed" if apply_r7_pass else "ready",
            assessment="PASS" if apply_r7_pass else None,
            actual="summary.json,processed.csv,accel_plot.png" if apply_r7_pass else None,
            authority="deterministic-code" if apply_r7_pass else None,
        ),
    ]

    reqs = requirements or [
        {"displayId": f"R{i}", "requirementId": f"req_R{i}"} for i in range(1, 9)
    ]
    coverage_rows = compute_requirement_coverage(requirements=reqs, test_cases=cases)
    summary = compute_test_plan_coverage_summary(coverage_rows)

    return {
        "schemaVersion": "1.0.0",
        "testPlanId": "tplan_16GOLDENVIBRATIONMONITOR01",
        "title": "ESP32 IMU Vibration Monitor Verification",
        "summary": "Deterministic fixture Test Plan covering R1–R8 (T1–T8).",
        "testCases": cases,
        "coverageSummary": summary,
        "provenance": {"generatedBy": "fixture", "notes": "Phase 17 golden T1–T8"},
    }


def _case(
    test_id: str,
    display_id: str,
    title: str,
    reqs: list[str],
    components: list[str],
    method: str,
    expected: str,
    criterion: dict[str, Any],
    *,
    status: str = "planned",
    assessment: str | None = None,
    actual: str | None = None,
    authority: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    finding: str | None = None,
    procedure: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "testId": test_id,
        "displayId": display_id,
        "title": title,
        "description": title,
        "linkedRequirementIds": reqs,
        "linkedComponentIds": components,
        "linkedArchitectureRefs": [],
        "verificationMethod": method,
        "preconditions": [],
        "inputs": [],
        "procedure": procedure or [f"Execute {display_id} using method {method}."],
        "expectedResult": expected,
        "criterion": criterion,
        "status": status,
        "evidenceReferences": evidence or [],
        "producedOutputIds": [],
    }
    if assessment:
        out["assessment"] = assessment
    if actual is not None:
        out["actualResult"] = actual
    if authority:
        out["assessmentAuthority"] = authority
    if finding:
        out["finding"] = finding
    return out
