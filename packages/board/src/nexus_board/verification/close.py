"""Promote execution/structural evidence into Test Plan content (Phase 17F).

Pure transforms only — no storage mutation. Application wiring lives in
VerificationService.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nexus_board.verification.apply import apply_evidence_to_test_case
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_board.verification.evidence import (
    ResolvedEvidence,
    resolve_analysis_metric_evidence,
    resolve_existence_evidence,
    resolve_marker_evidence,
    resolve_structural_mapping_evidence,
)


def stable_evidence_id(*, source_id: str, test_id: str, key: str) -> str:
    digest = hashlib.sha256(f"{source_id}|{test_id}|{key}".encode()).hexdigest()[:24]
    return f"evi_{digest}"


def evidence_ref(
    *,
    source_id: str,
    test_id: str,
    key: str,
    claim: str,
    locator: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": stable_evidence_id(source_id=source_id, test_id=test_id, key=key),
        "sourceType": "test-result",
        "sourceId": source_id,
        "evidenceStrength": "direct",
        "supportedClaim": claim,
        "sourceLocator": locator,
    }


def content_fingerprint(content: dict[str, Any]) -> str:
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def case_already_has_evidence(case: dict[str, Any], evidence_id: str) -> bool:
    for ref in case.get("evidenceReferences") or []:
        if isinstance(ref, dict) and ref.get("evidenceId") == evidence_id:
            return True
    return False


def apply_resolved_evidence(
    case: dict[str, Any],
    evidence: ResolvedEvidence,
    *,
    source_id: str,
    key: str,
    claim: str,
    locator: str,
    force_apply: bool = False,
) -> dict[str, Any]:
    """Apply evidence when present, or when force_apply for missing→INCONCLUSIVE/FAIL."""

    if not force_apply and evidence.present is False and evidence.actual is None:
        # For existence criteria, present=False is a definitive FAIL — force apply.
        raw_criterion = case.get("criterion")
        criterion: dict[str, Any] = raw_criterion if isinstance(raw_criterion, dict) else {}
        if criterion.get("criterionType") != "existence":
            return dict(case)

    ref = evidence_ref(
        source_id=source_id,
        test_id=str(case.get("testId") or case.get("displayId") or "test"),
        key=key,
        claim=claim,
        locator=locator,
    )
    if case_already_has_evidence(case, ref["evidenceId"]):
        # Idempotent: keep existing assessment when the same source evidence is reprocessed.
        return dict(case)
    return apply_evidence_to_test_case(case, evidence, evidence_reference=ref)


def promote_analysis_evidence_into_test_plan(
    test_plan_content: dict[str, Any],
    *,
    summary: dict[str, Any] | None,
    produced_output_names: list[str] | None = None,
    execution_run_id: str,
    output_id: str | None = None,
    requirements: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    expected_project_id: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Match Analysis metrics/outputs to eligible TestCases and assess.

    Returns (updated_content, changed).
    Rejects cross-project evidence when expected_project_id is set.
    """

    if (
        expected_project_id is not None
        and project_id is not None
        and expected_project_id != project_id
    ):
        raise ValueError("EVIDENCE_PROJECT_MISMATCH")

    updated = dict(test_plan_content)
    cases: list[dict[str, Any]] = []
    for case in list(test_plan_content.get("testCases") or []):
        if not isinstance(case, dict):
            continue
        criterion = case.get("criterion") if isinstance(case.get("criterion"), dict) else None
        if criterion is None:
            cases.append(dict(case))
            continue
        # Explicit non-analysis methods must retain their own evidence.
        method = str(case.get("verificationMethod") or "")
        ctype = criterion.get("criterionType")
        analysis_eligible = method in {"analysis", ""} and ctype in {
            "numeric-comparison",
            "range",
            "existence",
        }
        if not analysis_eligible:
            cases.append(dict(case))
            continue

        next_case = dict(case)
        str(case.get("testId") or case.get("displayId") or "test")
        if ctype in {"numeric-comparison", "range"} and criterion.get("metricId"):
            metric_id = str(criterion["metricId"])
            evidence = resolve_analysis_metric_evidence(
                summary=summary,
                metric_id=metric_id,
                execution_run_id=execution_run_id,
                output_id=output_id,
            )
            next_case = apply_resolved_evidence(
                next_case,
                evidence,
                source_id=execution_run_id,
                key=f"metric:{metric_id}",
                claim=f"{metric_id} assessed",
                locator="outputs/summary.json",
                force_apply=True,
            )
        elif ctype == "existence":
            names = [
                part.strip()
                for part in str(criterion.get("outputName") or "").split(",")
                if part.strip()
            ]
            evidence = resolve_existence_evidence(
                produced_output_names=list(produced_output_names or []),
                required_names=names,
                execution_run_id=execution_run_id,
            )
            next_case = apply_resolved_evidence(
                next_case,
                evidence,
                source_id=execution_run_id,
                key=f"existence:{','.join(names)}",
                claim="required ProducedOutputs present",
                locator=",".join(names) or "outputs/",
                force_apply=True,
            )
        cases.append(next_case)

    updated["testCases"] = cases
    if requirements is not None:
        rows = compute_requirement_coverage(requirements=requirements, test_cases=cases)
        updated["coverageSummary"] = compute_test_plan_coverage_summary(rows)
    changed = content_fingerprint(updated) != content_fingerprint(test_plan_content)
    return updated, changed


def promote_marker_evidence_into_test_plan(
    test_plan_content: dict[str, Any],
    *,
    log_text: str | None,
    execution_run_id: str,
    requirements: list[dict[str, Any]] | None = None,
    eligible_methods: frozenset[str] | None = None,
    run_occurred: bool = True,
) -> tuple[dict[str, Any], bool]:
    """Apply contains/exact marker criteria from firmware/simulation logs."""

    methods = eligible_methods or frozenset({"execution-output", "simulation", "firmware-test"})
    updated = dict(test_plan_content)
    cases: list[dict[str, Any]] = []
    for case in list(test_plan_content.get("testCases") or []):
        if not isinstance(case, dict):
            continue
        criterion = case.get("criterion") if isinstance(case.get("criterion"), dict) else None
        method = str(case.get("verificationMethod") or "")
        if criterion is None or method not in methods:
            cases.append(dict(case))
            continue
        ctype = criterion.get("criterionType")
        if ctype not in {"contains", "exact-match"}:
            cases.append(dict(case))
            continue
        marker = str(criterion.get("marker") or criterion.get("expectedValue") or "")
        if not run_occurred or log_text is None:
            # No eligible run → BLOCKED/INCONCLUSIVE, not FAIL.
            next_case = dict(case)
            next_case["assessment"] = "INCONCLUSIVE"
            next_case["assessmentAuthority"] = "deterministic-code"
            next_case["status"] = "blocked" if not run_occurred else "inconclusive"
            next_case["actualResult"] = "No eligible runtime evidence."
            cases.append(next_case)
            continue
        evidence = resolve_marker_evidence(
            log_text=log_text,
            marker=marker,
            execution_run_id=execution_run_id,
        )
        # Marker absent after a real run → FAIL (present=False with empty actual).
        if not evidence.present:
            evidence = ResolvedEvidence(
                source=evidence.source,
                actual=log_text,
                present=True,  # we have a log; marker missing → FAIL via contains
                detail=evidence.detail,
                execution_run_id=execution_run_id,
                evidence_status="tested",
            )
        next_case = apply_resolved_evidence(
            case,
            evidence,
            source_id=execution_run_id,
            key=f"marker:{marker}",
            claim=f"marker {marker}",
            locator="execution-log",
            force_apply=True,
        )
        cases.append(next_case)

    updated["testCases"] = cases
    if requirements is not None:
        rows = compute_requirement_coverage(requirements=requirements, test_cases=cases)
        updated["coverageSummary"] = compute_test_plan_coverage_summary(rows)
    changed = content_fingerprint(updated) != content_fingerprint(test_plan_content)
    return updated, changed


def promote_structural_evidence_into_test_plan(
    test_plan_content: dict[str, Any],
    *,
    signal_map: dict[str, str],
    source_id: str,
    requirements: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Apply structural-mapping criteria from Electrical/Wokwi translation maps."""

    updated = dict(test_plan_content)
    cases: list[dict[str, Any]] = []
    for case in list(test_plan_content.get("testCases") or []):
        if not isinstance(case, dict):
            continue
        criterion = case.get("criterion") if isinstance(case.get("criterion"), dict) else None
        if criterion is None or criterion.get("criterionType") != "structural-mapping":
            cases.append(dict(case))
            continue
        signal = str(criterion.get("signal") or "")
        expected = str(criterion.get("expectedMapping") or "")
        observed = signal_map.get(signal)
        evidence = resolve_structural_mapping_evidence(
            signal=signal,
            observed_mapping=observed,
            expected_mapping=expected,
        )
        next_case = apply_resolved_evidence(
            case,
            evidence,
            source_id=source_id,
            key=f"structural:{signal}",
            claim=f"{signal} → {expected}",
            locator="electrical-architecture/wokwi-translation",
            force_apply=True,
        )
        cases.append(next_case)

    updated["testCases"] = cases
    if requirements is not None:
        rows = compute_requirement_coverage(requirements=requirements, test_cases=cases)
        updated["coverageSummary"] = compute_test_plan_coverage_summary(rows)
    changed = content_fingerprint(updated) != content_fingerprint(test_plan_content)
    return updated, changed


def annotate_risk_mitigation_verification(
    risk_register_content: dict[str, Any],
    *,
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Annotate risks with mitigation verification evidence without auto-closing.

    Only auto-transitions to ``mitigated`` when the risk explicitly declares
    ``mitigationVerificationSufficient: true`` and all verificationTestIds PASS.
    K6-style risks without verification tests remain unchanged.
    """

    by_display = {
        str(c.get("displayId")): c for c in test_cases if isinstance(c, dict) and c.get("displayId")
    }
    updated = dict(risk_register_content)
    risks: list[dict[str, Any]] = []
    for risk in list(risk_register_content.get("risks") or []):
        if not isinstance(risk, dict):
            continue
        next_risk = dict(risk)
        vids = [str(v) for v in (risk.get("verificationTestIds") or [])]
        if not vids:
            next_risk["mitigationVerificationStatus"] = "proposed"
            risks.append(next_risk)
            continue
        linked = [by_display[v] for v in vids if v in by_display]
        if not linked:
            next_risk["mitigationVerificationStatus"] = "proposed"
            risks.append(next_risk)
            continue
        all_pass = len(linked) == len(vids) and all(
            c.get("assessment") == "PASS" or c.get("status") == "passed" for c in linked
        )
        any_evidence = any(c.get("evidenceReferences") for c in linked)
        if all_pass and any_evidence:
            next_risk["mitigationVerificationStatus"] = "verified"
            next_risk["mitigationVerifiedByTests"] = vids
            if risk.get("mitigationVerificationSufficient") is True and risk.get("status") not in {
                "accepted",
                "monitoring",
            }:
                next_risk["status"] = "mitigated"
        elif any_evidence:
            next_risk["mitigationVerificationStatus"] = "evidence-present"
            next_risk["mitigationVerifiedByTests"] = vids
        else:
            next_risk["mitigationVerificationStatus"] = "proposed"
        risks.append(next_risk)
    updated["risks"] = risks
    return updated


# Back-compat alias used by Phase 17C helpers/tests.
def apply_analysis_summary_to_test_plan(
    test_plan_content: dict[str, Any],
    *,
    summary: dict[str, Any] | None,
    produced_output_names: list[str] | None = None,
    execution_run_id: str | None = None,
    output_id: str | None = None,
    requirements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    updated, _ = promote_analysis_evidence_into_test_plan(
        test_plan_content,
        summary=summary,
        produced_output_names=produced_output_names,
        execution_run_id=execution_run_id or "exec_unknown",
        output_id=output_id,
        requirements=requirements,
    )
    return updated
