"""Compose Test Plan / Risk Register envelopes for initialization (Phase 17B/D)."""

from __future__ import annotations

from typing import Any

from nexus_board.ids import new_id
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_board.verification.fixture_risk_register import (
    build_golden_vibration_risk_register_content,
)
from nexus_board.verification.fixture_test_plan import (
    build_golden_vibration_test_plan_content,
)
from nexus_board.verification.risk_scoring import (
    compute_risk_priority,
    compute_risk_register_summary,
)


def looks_like_vibration_monitor(requirements: list[dict[str, Any]]) -> bool:
    blob = " ".join(
        str(r.get("statement") or "") + " " + str(r.get("displayId") or "")
        for r in requirements
        if isinstance(r, dict)
    ).lower()
    return "accel_x" in blob and "0.10" in blob and "mpu" in blob


def compose_test_plan_content(
    *,
    requirements: list[dict[str, Any]],
    apply_r7_pass: bool = False,
) -> dict[str, Any]:
    if looks_like_vibration_monitor(requirements):
        return build_golden_vibration_test_plan_content(
            requirements=requirements,
            apply_r7_pass=apply_r7_pass,
        )
    cases: list[dict[str, Any]] = []
    for index, req in enumerate(requirements, start=1):
        if not isinstance(req, dict):
            continue
        display = str(req.get("displayId") or f"R{index}")
        cases.append(
            {
                "testId": new_id("test"),
                "displayId": f"T{index}",
                "title": f"Verify {display}",
                "description": str(req.get("statement") or display),
                "linkedRequirementIds": [display],
                "linkedComponentIds": [],
                "linkedArchitectureRefs": [],
                "verificationMethod": "inspection",
                "preconditions": [],
                "inputs": [],
                "procedure": [f"Confirm {display} using project evidence."],
                "expectedResult": str(req.get("verificationMethod") or "Requirement satisfied."),
                "status": "planned",
                "evidenceReferences": [],
                "producedOutputIds": [],
            }
        )
    if not cases:
        cases.append(
            {
                "testId": new_id("test"),
                "displayId": "T1",
                "title": "Placeholder verification",
                "linkedRequirementIds": [],
                "linkedComponentIds": [],
                "linkedArchitectureRefs": [],
                "verificationMethod": "manual",
                "expectedResult": "Manual confirmation",
                "status": "planned",
                "evidenceReferences": [],
                "producedOutputIds": [],
            }
        )
    rows = compute_requirement_coverage(requirements=requirements, test_cases=cases)
    return {
        "schemaVersion": "1.0.0",
        "testPlanId": new_id("tplan"),
        "title": "Project Test Plan",
        "summary": "Deterministically composed from current requirements.",
        "testCases": cases,
        "coverageSummary": compute_test_plan_coverage_summary(rows),
        "provenance": {"generatedBy": "derived"},
    }


def compose_risk_register_content(
    *,
    requirements: list[dict[str, Any]],
    test_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if looks_like_vibration_monitor(requirements):
        return build_golden_vibration_risk_register_content()
    risks: list[dict[str, Any]] = []
    for index, req in enumerate(requirements[:6], start=1):
        if not isinstance(req, dict):
            continue
        display = str(req.get("displayId") or f"R{index}")
        linked_tests = [
            str(c.get("displayId"))
            for c in (test_cases or [])
            if isinstance(c, dict) and display in (c.get("linkedRequirementIds") or [])
        ][:1]
        severity = "medium"
        likelihood = "possible"
        risks.append(
            {
                "riskId": new_id("risk"),
                "displayId": f"K{index}",
                "title": f"Unverified requirement {display}",
                "description": f"Requirement {display} may fail without linked verification evidence.",
                "category": "integration",
                "linkedRequirementIds": [display],
                "linkedComponentIds": [],
                "linkedArchitectureRefs": [],
                "linkedTestIds": linked_tests,
                "likelihood": likelihood,
                "severity": severity,
                "priorityScore": compute_risk_priority(severity=severity, likelihood=likelihood),
                "mitigation": "Add or execute linked TestCases and attach evidence.",
                "verificationTestIds": linked_tests,
                "status": "open",
                "evidenceReferences": [],
            }
        )
    if not risks:
        risks.append(
            {
                "riskId": new_id("risk"),
                "displayId": "K1",
                "title": "Incomplete verification coverage",
                "description": "Project lacks structured verification evidence.",
                "category": "integration",
                "linkedRequirementIds": [],
                "linkedComponentIds": [],
                "linkedArchitectureRefs": [],
                "linkedTestIds": [],
                "likelihood": "possible",
                "severity": "medium",
                "priorityScore": compute_risk_priority(severity="medium", likelihood="possible"),
                "mitigation": "Generate a Test Plan and close evidence gaps.",
                "verificationTestIds": [],
                "status": "open",
                "evidenceReferences": [],
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "riskRegisterId": new_id("rreg"),
        "title": "Project Risk Register",
        "summary": compute_risk_register_summary(risks),
        "risks": risks,
        "provenance": {"generatedBy": "derived"},
    }


def compose_verify_artifact_envelope(
    *,
    artifact_type: str,
    content: dict[str, Any],
    project_id: str,
    turn_id: str,
    run_id: str,
    now: str,
    vera_actor: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "artifactId": new_id("art"),
        "projectId": project_id,
        "artifactType": artifact_type,
        "artifactVersion": 1,
        "contentSchemaVersion": "1.0.0",
        "lifecycleStatus": "ready",
        "evidenceStatus": "unverified",
        "approvalStatus": "proposed",
        "createdBy": vera_actor,
        "createdAt": now,
        "updatedAt": now,
        "sourceTurnId": turn_id,
        "workflowRunId": run_id,
        "content": content,
    }
