"""Live structured Test Plan / Risk Register generation via model gateway (Phase 17F)."""

from __future__ import annotations

from typing import Any

from nexus_board.ids import new_id
from nexus_board.verification.assessment import CRITERION_TYPES, VERIFICATION_METHODS
from nexus_board.verification.compose import (
    compose_risk_register_content,
    compose_test_plan_content,
)
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_board.verification.live_validate import (
    VerifyDraftValidationError,
    validate_risk_register_draft,
    validate_test_plan_draft,
)
from nexus_board.verification.risk_scoring import (
    RISK_CATEGORIES,
    RISK_STATUSES,
    compute_risk_priority,
    compute_risk_register_summary,
)

TEST_PLAN_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "testCases"],
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "testCases": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "displayId",
                    "title",
                    "linkedRequirementIds",
                    "verificationMethod",
                    "expectedResult",
                ],
                "properties": {
                    "displayId": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "linkedRequirementIds": {"type": "array", "items": {"type": "string"}},
                    "linkedComponentIds": {"type": "array", "items": {"type": "string"}},
                    "verificationMethod": {"type": "string"},
                    "procedure": {"type": "array", "items": {"type": "string"}},
                    "expectedResult": {"type": "string"},
                    "criterion": {"type": "object"},
                },
            },
        },
    },
}

RISK_REGISTER_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "risks"],
    "properties": {
        "title": {"type": "string"},
        "risks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "displayId",
                    "title",
                    "description",
                    "category",
                    "likelihood",
                    "severity",
                    "mitigation",
                ],
                "properties": {
                    "displayId": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "linkedRequirementIds": {"type": "array", "items": {"type": "string"}},
                    "linkedComponentIds": {"type": "array", "items": {"type": "string"}},
                    "linkedTestIds": {"type": "array", "items": {"type": "string"}},
                    "verificationTestIds": {"type": "array", "items": {"type": "string"}},
                    "likelihood": {"type": "string"},
                    "severity": {"type": "string"},
                    "mitigation": {"type": "string"},
                    "residualRisk": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
    },
}


def normalize_live_test_plan_draft(
    draft: dict[str, Any],
    *,
    requirements: list[dict[str, Any]],
    known_requirement_ids: set[str],
    known_component_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Normalize LLM draft into schema-shaped Test Plan content; never marks PASS."""

    method_aliases = {
        "analysis-run": "analysis",
        "firmware": "firmware-test",
        "code-inspection": "inspection",
        "structural": "inspection",
        "log": "execution-output",
        "runtime": "execution-output",
        "wokwi": "simulation",
    }
    criterion_aliases = {
        "numeric": "numeric-comparison",
        "comparison": "numeric-comparison",
        "threshold": "numeric-comparison",
        "match": "exact-match",
        "equals": "exact-match",
        "contains-text": "contains",
        "marker": "contains",
        "exists": "existence",
        "file-exists": "existence",
        "pin-mapping": "structural-mapping",
        "mapping": "structural-mapping",
    }

    cases: list[dict[str, Any]] = []
    for index, raw in enumerate(draft.get("testCases") or [], start=1):
        if not isinstance(raw, dict):
            continue
        method = str(raw.get("verificationMethod") or "inspection")
        method = method_aliases.get(method, method)
        if method not in VERIFICATION_METHODS:
            method = "inspection"
        req_ids = [
            str(rid)
            for rid in (raw.get("linkedRequirementIds") or [])
            if str(rid) in known_requirement_ids
        ]
        comp_ids = [str(cid) for cid in (raw.get("linkedComponentIds") or [])]
        if known_component_ids is not None:
            comp_ids = [cid for cid in comp_ids if cid in known_component_ids]
        case: dict[str, Any] = {
            "testId": new_id("test"),
            "displayId": str(raw.get("displayId") or f"T{index}"),
            "title": str(raw.get("title") or f"Test {index}"),
            "description": str(raw.get("description") or raw.get("title") or ""),
            "linkedRequirementIds": req_ids,
            "linkedComponentIds": comp_ids,
            "linkedArchitectureRefs": list(raw.get("linkedArchitectureRefs") or []),
            "verificationMethod": method,
            "preconditions": list(raw.get("preconditions") or []),
            "inputs": list(raw.get("inputs") or []),
            "procedure": list(raw.get("procedure") or ["Execute verification procedure."]),
            "expectedResult": str(raw.get("expectedResult") or "Requirement satisfied."),
            "status": "planned",
            "evidenceReferences": [],
            "producedOutputIds": [],
        }
        if isinstance(raw.get("criterion"), dict):
            criterion = dict(raw["criterion"])
            ctype = str(criterion.get("criterionType") or "")
            ctype = criterion_aliases.get(ctype, ctype)
            if ctype in CRITERION_TYPES:
                criterion["criterionType"] = ctype
                case["criterion"] = criterion
            # Invalid criterion types are dropped (draft remains usable; not authoritative PASS).
        # LLM must never author authoritative PASS/FAIL.
        case.pop("assessment", None)
        case.pop("assessmentAuthority", None)
        cases.append(case)

    if not cases:
        raise VerifyDraftValidationError("MISSING_TEST_CASES", "Normalized draft has no testCases")

    content = {
        "schemaVersion": "1.0.0",
        "testPlanId": new_id("tplan"),
        "title": str(draft.get("title") or "Project Test Plan"),
        "summary": str(
            draft.get("summary") or "Live model draft; assessments are not authoritative."
        ),
        "testCases": cases,
        "coverageSummary": {},
        "provenance": {"generatedBy": "llm"},
    }
    validate_test_plan_draft(
        content,
        known_requirement_ids=known_requirement_ids,
        known_component_ids=known_component_ids,
    )
    rows = compute_requirement_coverage(requirements=requirements, test_cases=cases)
    content["coverageSummary"] = compute_test_plan_coverage_summary(rows)
    return content


def normalize_live_risk_draft(
    draft: dict[str, Any],
    *,
    known_requirement_ids: set[str],
    known_test_ids: set[str] | None = None,
    known_component_ids: set[str] | None = None,
) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    for index, raw in enumerate(draft.get("risks") or [], start=1):
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity") or "medium").strip().lower()
        likelihood = str(raw.get("likelihood") or "possible").strip().lower()
        status = str(raw.get("status") or "open").strip().lower()
        category = str(raw.get("category") or "integration").strip().lower()
        # LLM prose cannot make risks mitigated.
        if status == "mitigated":
            status = "mitigating"
        req_ids = [
            str(rid)
            for rid in (raw.get("linkedRequirementIds") or [])
            if str(rid) in known_requirement_ids
        ]
        test_ids = [str(tid) for tid in (raw.get("linkedTestIds") or [])]
        verify_ids = [str(tid) for tid in (raw.get("verificationTestIds") or [])]
        if known_test_ids is not None:
            test_ids = [tid for tid in test_ids if tid in known_test_ids]
            verify_ids = [tid for tid in verify_ids if tid in known_test_ids]
        comp_ids = [str(cid) for cid in (raw.get("linkedComponentIds") or [])]
        if known_component_ids is not None:
            comp_ids = [cid for cid in comp_ids if cid in known_component_ids]
        try:
            priority = compute_risk_priority(severity=severity, likelihood=likelihood)
        except ValueError:
            severity = "medium"
            likelihood = "possible"
            priority = compute_risk_priority(severity=severity, likelihood=likelihood)
        if category not in RISK_CATEGORIES:
            category = "integration"
        if status not in RISK_STATUSES:
            status = "open"
        risks.append(
            {
                "riskId": new_id("risk"),
                "displayId": str(raw.get("displayId") or f"K{index}"),
                "title": str(raw.get("title") or f"Risk {index}"),
                "description": str(raw.get("description") or ""),
                "category": category,
                "linkedRequirementIds": req_ids,
                "linkedComponentIds": comp_ids,
                "linkedArchitectureRefs": list(raw.get("linkedArchitectureRefs") or []),
                "linkedTestIds": test_ids,
                "likelihood": likelihood,
                "severity": severity,
                "priorityScore": priority,
                "mitigation": str(raw.get("mitigation") or "Mitigate with linked verification."),
                "verificationTestIds": verify_ids,
                "status": status,
                "evidenceReferences": [],
                **(
                    {"residualRisk": str(raw["residualRisk"])}
                    if isinstance(raw.get("residualRisk"), str)
                    else {}
                ),
            }
        )
    if not risks:
        raise VerifyDraftValidationError("MISSING_RISKS", "Normalized draft has no risks")
    content = {
        "schemaVersion": "1.0.0",
        "riskRegisterId": new_id("rreg"),
        "title": str(draft.get("title") or "Project Risk Register"),
        "summary": compute_risk_register_summary(risks),
        "risks": risks,
        "provenance": {"generatedBy": "llm"},
    }
    validate_risk_register_draft(
        content,
        known_requirement_ids=known_requirement_ids,
        known_test_ids=known_test_ids,
    )
    return content


async def generate_live_test_plan_content(
    *,
    gateway: Any,
    model_policy: Any,
    system_instructions: str,
    context: dict[str, Any],
    requirements: list[dict[str, Any]],
    known_requirement_ids: set[str],
    known_component_ids: set[str] | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Call model gateway; optionally fall back to deterministic compose on failure."""

    try:
        gen = await gateway.generate_structured(
            task_name="generate-test-plan",
            system_instructions=system_instructions,
            input_payload=context,
            output_schema=TEST_PLAN_DRAFT_SCHEMA,
            model_policy=model_policy,
            prompt_id="embedded.test-plan.v1",
            prompt_version="1.0.0",
        )
        draft = gen.parsed_output if isinstance(gen.parsed_output, dict) else {}
        return normalize_live_test_plan_draft(
            draft,
            requirements=requirements,
            known_requirement_ids=known_requirement_ids,
            known_component_ids=known_component_ids,
        )
    except (VerifyDraftValidationError, Exception):
        if not allow_fallback:
            raise
        return compose_test_plan_content(requirements=requirements, apply_r7_pass=False)


async def generate_live_risk_register_content(
    *,
    gateway: Any,
    model_policy: Any,
    system_instructions: str,
    context: dict[str, Any],
    requirements: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    known_requirement_ids: set[str],
    known_test_ids: set[str] | None = None,
    known_component_ids: set[str] | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    try:
        gen = await gateway.generate_structured(
            task_name="generate-risk-register",
            system_instructions=system_instructions,
            input_payload=context,
            output_schema=RISK_REGISTER_DRAFT_SCHEMA,
            model_policy=model_policy,
            prompt_id="embedded.risk-register.v1",
            prompt_version="1.0.0",
        )
        draft = gen.parsed_output if isinstance(gen.parsed_output, dict) else {}
        return normalize_live_risk_draft(
            draft,
            known_requirement_ids=known_requirement_ids,
            known_test_ids=known_test_ids,
            known_component_ids=known_component_ids,
        )
    except (VerifyDraftValidationError, Exception):
        if not allow_fallback:
            raise
        return compose_risk_register_content(requirements=requirements, test_cases=test_cases)
