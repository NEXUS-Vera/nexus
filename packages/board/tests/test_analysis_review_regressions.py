"""N39 blocking regressions for analysis execution and VERIFY evidence."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from unittest.mock import Mock

import jsonschema
import pytest
from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator, _run_sync
from nexus_board.errors import AnalysisPatchGenerationError
from nexus_board.services.verification_service import VerificationError, VerificationService
from nexus_board.verification.assessment import evaluate_criterion
from nexus_board.verification.close import (
    annotate_risk_mitigation_verification,
    promote_analysis_evidence_into_test_plan,
)
from nexus_board.verification.coverage import compute_requirement_coverage
from nexus_board.verification.evidence import resolve_existence_evidence
from nexus_board.verification.fixture_risk_register import (
    build_golden_vibration_risk_register_content,
)
from nexus_model_gateway import ModelPolicy

ROOT = Path(__file__).resolve().parents[3]


def test_run_sync_times_out_without_hanging() -> None:
    release = threading.Event()

    async def stalled() -> None:
        await asyncio.to_thread(release.wait)

    try:
        with pytest.raises(AnalysisPatchGenerationError, match="timed out"):
            _run_sync(stalled(), timeout=0.02)
    finally:
        release.set()


def test_run_sync_propagates_cancelled_error_without_queue_deadlock() -> None:
    async def cancelled() -> None:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        _run_sync(cancelled(), timeout=0.2)


def test_python_analysis_dockerfile_declares_non_root_user() -> None:
    lines = (ROOT / "infra/docker/python-analysis/Dockerfile").read_text().splitlines()
    users = [line.split(maxsplit=1)[1] for line in lines if line.startswith("USER ")]
    assert users and users[-1] not in {"root", "0", "0:0"}


@pytest.mark.parametrize("status", ["failed", "timed-out", "cancelled", "running", "queued", None])
def test_promote_execution_evidence_rejects_non_completed_run(status: str | None) -> None:
    store = Mock()
    store.get_execution_run.return_value = {"projectId": "p1", "status": status}
    projects = Mock()
    service = VerificationService(
        kernel_store=store,
        project_store=projects,
        workspaces=Mock(),
        commands=Mock(),
        ledger=Mock(),
        projection=Mock(),
    )
    with pytest.raises(VerificationError, match="completed"):
        service.promote_execution_evidence(
            project_id="p1",
            execution_run_id="run1",
            actor={"actorType": "user"},
        )
    projects.get_artifact.assert_not_called()
    store.list_produced_outputs.assert_not_called()


@pytest.mark.parametrize("missing_status", [None, "blocked", "inconclusive", "ready", "failed"])
def test_risk_not_verified_when_required_test_missing_or_skipped(
    missing_status: str | None,
) -> None:
    risk = {
        "status": "mitigating",
        "verificationTestIds": ["T2", "T99"],
        "mitigationVerificationSufficient": True,
    }
    cases = [
        {"displayId": "T2", "assessment": "PASS", "evidenceReferences": [{"evidenceId": "e1"}]}
    ]
    if missing_status:
        cases.append({"displayId": "T99", "status": missing_status})
    result = annotate_risk_mitigation_verification({"risks": [risk]}, test_cases=cases)["risks"][0]
    assert result["status"] == "mitigating"
    assert result["mitigationVerificationStatus"] != "verified"


@pytest.mark.parametrize("method", ["simulation", "firmware-test", "manual", "inspection"])
@pytest.mark.parametrize("ctype", ["existence", "numeric-comparison", "range"])
def test_analysis_promotion_ignores_non_analysis_tests(method: str, ctype: str) -> None:
    case = {
        "testId": "t1",
        "verificationMethod": method,
        "status": "passed",
        "assessment": "PASS",
        "criterion": {
            "criterionType": ctype,
            "outputName": "wave.vcd",
            "metricId": "x",
            "expectedValue": 1,
        },
    }
    content = {"testCases": [case]}
    updated, changed = promote_analysis_evidence_into_test_plan(
        content,
        summary={},
        produced_output_names=[],
        execution_run_id="run1",
    )
    assert updated == content
    assert not changed


@pytest.mark.parametrize(
    "expected,actual,result",
    [
        ("", "GPIO21", "INCONCLUSIVE"),
        ("   ", "GPIO21", "INCONCLUSIVE"),
        ("GPIO1", "GPIO12", "FAIL"),
        (" gpio21 ", "GPIO21", "PASS"),
    ],
)
def test_structural_mapping_rejects_empty_expected_and_substring_mismatch(
    expected: str, actual: str, result: str
) -> None:
    assessment, _ = evaluate_criterion(
        {"criterionType": "structural-mapping", "expectedMapping": expected},
        actual=actual,
    )
    assert assessment == result


@pytest.mark.parametrize("assessment", [None, "PASS", "FAIL"])
def test_annotated_risk_register_validates_against_v1_schema(assessment: str | None) -> None:
    content = build_golden_vibration_risk_register_content()
    cases = (
        []
        if assessment is None
        else [
            {
                "displayId": "T2",
                "assessment": assessment,
                "evidenceReferences": [{"evidenceId": "e1"}],
            }
        ]
    )
    annotated = annotate_risk_mitigation_verification(content, test_cases=cases)
    schema = json.loads(
        (
            ROOT / "packages/contracts/schemas/artifacts/content/risk-register.v1.schema.json"
        ).read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(annotated)
    assert schema["$defs"]["riskItem"]["properties"]["mitigationVerificationStatus"]["enum"] == [
        "proposed",
        "evidence-present",
        "verified",
    ]


def test_coverage_deduplicates_display_and_uuid_links() -> None:
    rows = compute_requirement_coverage(
        requirements=[{"displayId": "R1", "requirementId": "req1"}],
        test_cases=[{"testId": "t1", "displayId": "T1", "linkedRequirementIds": ["R1", "req1"]}],
    )
    assert rows[0]["linkedTestIds"] == ["T1"]
    assert len(rows[0]["tests"]) == 1


def test_existence_uses_exact_names_and_deterministic_order() -> None:
    evidence = resolve_existence_evidence(
        produced_output_names=["outputs/z.txt", "outputs/summary.json.bak"],
        required_names=["outputs/summary.json"],
    )
    assert evidence.present is False
    reversed_evidence = resolve_existence_evidence(
        produced_output_names=["outputs/summary.json.bak", "outputs/z.txt"],
        required_names=["outputs/summary.json"],
    )
    assert evidence == reversed_evidence
    assert resolve_existence_evidence(
        produced_output_names=["outputs/summary.json"], required_names=["summary.json"]
    ).present
    assert not resolve_existence_evidence(
        produced_output_names=["outputs/summary.json.bak"], required_names=["summary.json"]
    ).present


def test_live_analysis_patch_generator_times_out() -> None:
    release = threading.Event()
    finished = threading.Event()
    errors: list[BaseException] = []

    async def stalled() -> None:
        await asyncio.to_thread(release.wait)

    gateway = Mock()
    gateway.generate_structured.side_effect = lambda **kwargs: stalled()
    generator = LiveAnalysisPatchGenerator(
        gateway=gateway,
        model_policy=ModelPolicy(provider="fake", model="test", timeout_seconds=0.01),
    )

    def generate() -> None:
        try:
            generator.generate(
                context={
                    "requestedChange": "change",
                    "baseSnapshotId": "snap1",
                    "snapshotFiles": [],
                    "fileContents": {},
                },
                base_snapshot={},
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    caller = threading.Thread(target=generate, daemon=True)
    caller.start()
    try:
        assert finished.wait(6), "Live analysis generation exceeded its bounded timeout"
        assert len(errors) == 1 and isinstance(errors[0], AnalysisPatchGenerationError)
    finally:
        release.set()
        caller.join(timeout=2)
