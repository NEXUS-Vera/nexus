"""Apply resolved evidence to a TestCase deterministically (Phase 17C)."""

from __future__ import annotations

from typing import Any

from nexus_board.verification.assessment import evaluate_criterion, status_from_assessment
from nexus_board.verification.evidence import ResolvedEvidence


def apply_evidence_to_test_case(
    test_case: dict[str, Any],
    evidence: ResolvedEvidence,
    *,
    evidence_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copy of test_case with deterministic assessment filled in.

    Does not invent PASS from missing evidence.
    """

    updated = dict(test_case)
    criterion = updated.get("criterion") if isinstance(updated.get("criterion"), dict) else None
    assessment, detail = evaluate_criterion(
        criterion,
        actual=evidence.actual,
        present=evidence.present,
    )
    updated["assessment"] = assessment
    updated["assessmentAuthority"] = "deterministic-code"
    updated["status"] = status_from_assessment(assessment)
    updated["actualResult"] = (
        detail
        if evidence.actual is None
        else f"{evidence.actual}" + (f" ({detail})" if detail else "")
    )
    if evidence.execution_run_id:
        updated["executionRunId"] = evidence.execution_run_id
    if evidence.output_id:
        outputs = list(updated.get("producedOutputIds") or [])
        if evidence.output_id not in outputs:
            outputs.append(evidence.output_id)
        updated["producedOutputIds"] = outputs
    if evidence_reference:
        refs = list(updated.get("evidenceReferences") or [])
        refs.append(evidence_reference)
        updated["evidenceReferences"] = refs
    return updated
