"""Phase 17 verification assessment, coverage, evidence, and golden fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from nexus_board.verification.apply import apply_evidence_to_test_case
from nexus_board.verification.assessment import evaluate_criterion, status_from_assessment
from nexus_board.verification.close import apply_analysis_summary_to_test_plan
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_board.verification.evidence import (
    resolve_analysis_metric_evidence,
    resolve_existence_evidence,
    resolve_marker_evidence,
    resolve_structural_mapping_evidence,
)
from nexus_board.verification.fixture_risk_register import (
    build_golden_vibration_risk_register_content,
)
from nexus_board.verification.fixture_test_plan import (
    build_golden_vibration_test_plan_content,
)
from nexus_board.verification.live_validate import (
    VerifyDraftValidationError,
    validate_risk_register_draft,
    validate_test_plan_draft,
)
from nexus_board.verification.risk_scoring import compute_risk_priority

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "valid"
    / "esp32-imu-vibration-monitor"
)


def test_numeric_pass_fail_inconclusive() -> None:
    crit = {
        "criterionType": "numeric-comparison",
        "metricId": "accel_x_rms_noise_g",
        "operator": "<",
        "expectedValue": 0.1,
        "unit": "g",
    }
    assert evaluate_criterion(crit, actual=0.0157)[0] == "PASS"
    assert evaluate_criterion(crit, actual=0.2)[0] == "FAIL"
    assert evaluate_criterion(crit, actual=None)[0] == "INCONCLUSIVE"


def test_marker_existence_and_structural() -> None:
    assert (
        evaluate_criterion(
            {"criterionType": "contains", "marker": "NEXUS_MPU_READY"}, actual="x NEXUS_MPU_READY y"
        )[0]
        == "PASS"
    )
    assert (
        evaluate_criterion(
            {"criterionType": "existence", "outputName": "summary.json"},
            present=True,
        )[0]
        == "PASS"
    )
    assert (
        evaluate_criterion(
            {
                "criterionType": "structural-mapping",
                "signal": "SDA",
                "expectedMapping": "GPIO21",
            },
            actual="GPIO21",
        )[0]
        == "PASS"
    )


def test_range_sampling() -> None:
    crit = {"criterionType": "range", "minValue": 45, "maxValue": 55, "unit": "Hz"}
    assert evaluate_criterion(crit, actual=50)[0] == "PASS"
    assert evaluate_criterion(crit, actual=40)[0] == "FAIL"


def test_analysis_metric_evidence_to_test_pass() -> None:
    evidence = resolve_analysis_metric_evidence(
        summary={"accel_x_rms_noise_g": 0.0157, "assessment": "PASS"},
        metric_id="accel_x_rms_noise_g",
        execution_run_id="exec_1",
        output_id="out_1",
    )
    case = {
        "testId": "test_AAAAAAAAAAAAAAAA",
        "displayId": "T7",
        "title": "Noise",
        "linkedRequirementIds": ["R7"],
        "verificationMethod": "analysis",
        "expectedResult": "< 0.10 g",
        "criterion": {
            "criterionType": "numeric-comparison",
            "metricId": "accel_x_rms_noise_g",
            "operator": "<",
            "expectedValue": 0.1,
            "unit": "g",
        },
        "status": "ready",
        "evidenceReferences": [],
        "producedOutputIds": [],
    }
    updated = apply_evidence_to_test_case(
        case,
        evidence,
        evidence_reference={
            "schemaVersion": "1.0.0",
            "evidenceId": "evi_AAAAAAAAAAAAAAAA",
            "sourceType": "test-result",
            "sourceId": "exec_1",
            "evidenceStrength": "direct",
        },
    )
    assert updated["assessment"] == "PASS"
    assert updated["status"] == "passed"
    assert updated["assessmentAuthority"] == "deterministic-code"
    assert status_from_assessment("PASS") == "passed"


def test_missing_metric_inconclusive() -> None:
    evidence = resolve_analysis_metric_evidence(summary={}, metric_id="accel_x_rms_noise_g")
    assert evidence.present is False
    assessment, _ = evaluate_criterion(
        {
            "criterionType": "numeric-comparison",
            "metricId": "accel_x_rms_noise_g",
            "operator": "<",
            "expectedValue": 0.1,
        },
        actual=evidence.actual,
        present=evidence.present,
    )
    assert assessment == "INCONCLUSIVE"


def test_marker_and_existence_resolvers() -> None:
    assert resolve_marker_evidence(log_text="NEXUS_MPU_READY ok", marker="NEXUS_MPU_READY").present
    assert resolve_existence_evidence(
        produced_output_names=["outputs/summary.json", "outputs/accel_plot.png"],
        required_names=["summary.json", "accel_plot.png"],
    ).present
    assert (
        resolve_structural_mapping_evidence(
            signal="SDA",
            observed_mapping="GPIO21",
            expected_mapping="GPIO21",
        ).actual
        == "GPIO21"
    )


def test_golden_t1_t8_covers_r1_r8_and_r7_verified() -> None:
    req_art = json.loads(
        (FIXTURE_DIR / "requirement-set-artifact.json").read_text(encoding="utf-8")
    )
    requirements = req_art["content"]["requirements"]
    content = build_golden_vibration_test_plan_content(
        requirements=requirements, apply_r7_pass=True
    )
    assert len(content["testCases"]) == 8
    assert content["coverageSummary"]["coveredRequirements"] == 8
    assert content["coverageSummary"]["uncoveredRequirements"] == 0
    rows = compute_requirement_coverage(requirements=requirements, test_cases=content["testCases"])
    r7 = next(r for r in rows if r["displayId"] == "R7")
    assert r7["verificationState"] == "VERIFIED"
    t7 = next(c for c in content["testCases"] if c["displayId"] == "T7")
    assert t7["assessment"] == "PASS"
    assert t7["assessmentAuthority"] == "deterministic-code"
    assert t7["evidenceReferences"]


def test_golden_risk_register_keeps_unresolved_hardware_risk() -> None:
    content = build_golden_vibration_risk_register_content()
    assert len(content["risks"]) >= 6
    k6 = next(r for r in content["risks"] if r["displayId"] == "K6")
    assert k6["status"] == "monitoring"
    assert k6["category"] == "integration"
    assert not k6["verificationTestIds"]
    k5 = next(r for r in content["risks"] if r["displayId"] == "K5")
    assert k5["verificationTestIds"] == ["T7"]
    assert compute_risk_priority(severity="high", likelihood="possible") == 9


def test_live_draft_rejects_unknown_requirement() -> None:
    draft = build_golden_vibration_test_plan_content(apply_r7_pass=False)
    try:
        validate_test_plan_draft(draft, known_requirement_ids={"R1"})
        raise AssertionError("expected validation failure")
    except VerifyDraftValidationError as exc:
        assert exc.code == "UNKNOWN_REQUIREMENT_REF"


def test_live_risk_draft_rejects_unknown_test_ref() -> None:
    draft = build_golden_vibration_risk_register_content()
    try:
        validate_risk_register_draft(
            draft,
            known_requirement_ids={"R1", "R2", "R4", "R5", "R6", "R7", "R8"},
            known_test_ids={"T2"},
        )
        raise AssertionError("expected validation failure")
    except VerifyDraftValidationError as exc:
        assert exc.code == "UNKNOWN_TEST_REF"


def test_fixture_artifacts_on_disk_are_schema_shaped() -> None:
    tp = json.loads((FIXTURE_DIR / "test-plan-artifact.json").read_text(encoding="utf-8"))
    rr = json.loads((FIXTURE_DIR / "risk-register-artifact.json").read_text(encoding="utf-8"))
    assert tp["artifactType"] == "test-plan"
    assert rr["artifactType"] == "risk-register"
    assert tp["content"]["coverageSummary"]["coveredRequirements"] == 8
    assert tp["content"]["coverageSummary"]["uncoveredRequirements"] == 0
    # Phase 17F: golden fixture starts ready; product promotion closes R7.
    assert all(c["status"] == "ready" for c in tp["content"]["testCases"])
    summary = compute_test_plan_coverage_summary(
        compute_requirement_coverage(
            requirements=json.loads(
                (FIXTURE_DIR / "requirement-set-artifact.json").read_text(encoding="utf-8")
            )["content"]["requirements"],
            test_cases=tp["content"]["testCases"],
        )
    )
    assert summary["uncoveredRequirements"] == 0
    assert summary["verifiedRequirements"] == 0


def test_apply_analysis_summary_closes_r7_without_llm() -> None:
    requirements = json.loads(
        (FIXTURE_DIR / "requirement-set-artifact.json").read_text(encoding="utf-8")
    )["content"]["requirements"]
    draft = build_golden_vibration_test_plan_content(requirements=requirements, apply_r7_pass=False)
    t7 = next(c for c in draft["testCases"] if c["displayId"] == "T7")
    assert t7["status"] != "passed"
    closed = apply_analysis_summary_to_test_plan(
        draft,
        summary={"accel_x_rms_noise_g": 0.0157, "assessment": "PASS"},
        produced_output_names=[
            "outputs/summary.json",
            "outputs/processed.csv",
            "outputs/accel_plot.png",
        ],
        execution_run_id="exec_GOLDEN_ANALYSIS_R7",
        requirements=requirements,
    )
    t7b = next(c for c in closed["testCases"] if c["displayId"] == "T7")
    assert t7b["assessment"] == "PASS"
    assert t7b["assessmentAuthority"] == "deterministic-code"
    assert closed["coverageSummary"]["verifiedRequirements"] >= 1
    rows = compute_requirement_coverage(requirements=requirements, test_cases=closed["testCases"])
    r7 = next(r for r in rows if r["displayId"] == "R7")
    assert r7["verificationState"] == "VERIFIED"
