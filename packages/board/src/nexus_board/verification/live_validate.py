"""Live LLM Test Plan / Risk Register draft validation boundary (Phase 17B/D).

Generation uses the Nexus model gateway when configured. Drafts are validated
deterministically; broken entity references are rejected (not silently dropped).
"""

from __future__ import annotations

from typing import Any

from nexus_board.verification.assessment import (
    CRITERION_TYPES,
    TEST_STATUSES,
    VERIFICATION_METHODS,
)
from nexus_board.verification.risk_scoring import RISK_CATEGORIES, RISK_STATUSES


class VerifyDraftValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_test_plan_draft(
    draft: dict[str, Any],
    *,
    known_requirement_ids: set[str],
    known_component_ids: set[str] | None = None,
) -> None:
    if draft.get("schemaVersion") != "1.0.0":
        raise VerifyDraftValidationError("INVALID_SCHEMA_VERSION", "schemaVersion must be 1.0.0")
    cases = draft.get("testCases")
    if not isinstance(cases, list) or not cases:
        raise VerifyDraftValidationError("MISSING_TEST_CASES", "testCases must be a non-empty array")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise VerifyDraftValidationError("INVALID_TEST_CASE", "testCase must be an object")
        method = case.get("verificationMethod")
        if method not in VERIFICATION_METHODS:
            raise VerifyDraftValidationError(
                "INVALID_VERIFICATION_METHOD",
                f"Unsupported verificationMethod: {method!r}",
            )
        status = case.get("status", "planned")
        if status not in TEST_STATUSES:
            raise VerifyDraftValidationError("INVALID_TEST_STATUS", f"Unsupported status: {status!r}")
        criterion = case.get("criterion")
        if criterion is not None:
            if not isinstance(criterion, dict) or criterion.get("criterionType") not in CRITERION_TYPES:
                raise VerifyDraftValidationError("INVALID_CRITERION", "criterionType is invalid")
        for rid in case.get("linkedRequirementIds") or []:
            if rid not in known_requirement_ids:
                raise VerifyDraftValidationError(
                    "UNKNOWN_REQUIREMENT_REF",
                    f"TestCase references unknown requirement {rid!r}",
                )
        for cid in case.get("linkedComponentIds") or []:
            if known_component_ids is not None and cid not in known_component_ids:
                raise VerifyDraftValidationError(
                    "UNKNOWN_COMPONENT_REF",
                    f"TestCase references unknown component {cid!r}",
                )
        tid = case.get("testId") or case.get("displayId")
        if isinstance(tid, str):
            if tid in seen:
                raise VerifyDraftValidationError("DUPLICATE_TEST_ID", f"Duplicate test id {tid}")
            seen.add(tid)


def validate_risk_register_draft(
    draft: dict[str, Any],
    *,
    known_requirement_ids: set[str],
    known_test_ids: set[str] | None = None,
) -> None:
    if draft.get("schemaVersion") != "1.0.0":
        raise VerifyDraftValidationError("INVALID_SCHEMA_VERSION", "schemaVersion must be 1.0.0")
    risks = draft.get("risks")
    if not isinstance(risks, list) or not risks:
        raise VerifyDraftValidationError("MISSING_RISKS", "risks must be a non-empty array")
    for risk in risks:
        if not isinstance(risk, dict):
            raise VerifyDraftValidationError("INVALID_RISK", "risk must be an object")
        if risk.get("category") not in RISK_CATEGORIES:
            raise VerifyDraftValidationError(
                "INVALID_RISK_CATEGORY",
                f"Unsupported category: {risk.get('category')!r}",
            )
        if risk.get("status") not in RISK_STATUSES:
            raise VerifyDraftValidationError(
                "INVALID_RISK_STATUS",
                f"Unsupported status: {risk.get('status')!r}",
            )
        for rid in risk.get("linkedRequirementIds") or []:
            if rid not in known_requirement_ids:
                raise VerifyDraftValidationError(
                    "UNKNOWN_REQUIREMENT_REF",
                    f"Risk references unknown requirement {rid!r}",
                )
        for tid in risk.get("verificationTestIds") or []:
            if known_test_ids is not None and tid not in known_test_ids:
                raise VerifyDraftValidationError(
                    "UNKNOWN_TEST_REF",
                    f"Risk references unknown test {tid!r}",
                )
