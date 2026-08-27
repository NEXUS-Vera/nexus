"""Requirement coverage aggregation from TestCases (Phase 17B/C)."""

from __future__ import annotations

from typing import Any, Literal

RequirementVerificationState = Literal[
    "UNCOVERED",
    "UNVERIFIED",
    "VERIFIED",
    "FAILED",
    "BLOCKED",
    "INCONCLUSIVE",
]


def _req_key(requirement: dict[str, Any]) -> str:
    display = requirement.get("displayId")
    if isinstance(display, str) and display.strip():
        return display.strip()
    rid = requirement.get("requirementId")
    return str(rid) if rid else ""


def compute_requirement_coverage(
    *,
    requirements: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive per-requirement verification rows.

    Rules:
    - no linked test → UNCOVERED
    - any linked test failed → FAILED
    - all linked tests passed → VERIFIED
    - no failures and any blocked → BLOCKED
    - no failures and any inconclusive → INCONCLUSIVE
    - otherwise (planned/ready/running only) → UNVERIFIED
    """

    by_req: dict[str, list[dict[str, Any]]] = {}
    for case in test_cases:
        if not isinstance(case, dict):
            continue
        for rid in case.get("linkedRequirementIds") or []:
            if isinstance(rid, str) and rid:
                by_req.setdefault(rid, []).append(case)

    rows: list[dict[str, Any]] = []
    for req in requirements:
        if not isinstance(req, dict):
            continue
        key = _req_key(req)
        if not key:
            continue
        linked = by_req.get(key, [])
        # Also allow linking by full requirementId.
        rid = req.get("requirementId")
        if isinstance(rid, str) and rid != key:
            linked = [*linked, *by_req.get(rid, [])]
        state = _aggregate(linked)
        rows.append(
            {
                "requirementId": rid,
                "displayId": key,
                "statement": req.get("statement"),
                "linkedTestIds": [
                    c.get("displayId") or c.get("testId") for c in linked if isinstance(c, dict)
                ],
                "verificationMethods": sorted(
                    {
                        str(c.get("verificationMethod"))
                        for c in linked
                        if isinstance(c, dict) and c.get("verificationMethod")
                    }
                ),
                "verificationState": state,
                "tests": [
                    {
                        "testId": c.get("testId"),
                        "displayId": c.get("displayId"),
                        "status": c.get("status"),
                        "assessment": c.get("assessment"),
                        "verificationMethod": c.get("verificationMethod"),
                    }
                    for c in linked
                    if isinstance(c, dict)
                ],
            }
        )
    return rows


def _aggregate(linked: list[dict[str, Any]]) -> RequirementVerificationState:
    if not linked:
        return "UNCOVERED"
    statuses = [str(c.get("status") or "") for c in linked]
    assessments = [str(c.get("assessment") or "") for c in linked]
    if any(s == "failed" or a == "FAIL" for s, a in zip(statuses, assessments, strict=False)):
        return "FAILED"
    if linked and all(s == "passed" or a == "PASS" for s, a in zip(statuses, assessments, strict=False)):
        return "VERIFIED"
    if any(s == "blocked" for s in statuses):
        return "BLOCKED"
    if any(s == "inconclusive" or a == "INCONCLUSIVE" for s, a in zip(statuses, assessments, strict=False)):
        return "INCONCLUSIVE"
    return "UNVERIFIED"


def compute_test_plan_coverage_summary(
    coverage_rows: list[dict[str, Any]],
) -> dict[str, int]:
    total = len(coverage_rows)
    counts = {
        "UNCOVERED": 0,
        "UNVERIFIED": 0,
        "VERIFIED": 0,
        "FAILED": 0,
        "BLOCKED": 0,
        "INCONCLUSIVE": 0,
    }
    for row in coverage_rows:
        state = str(row.get("verificationState") or "UNCOVERED")
        counts[state] = counts.get(state, 0) + 1
    covered = total - counts["UNCOVERED"]
    return {
        "totalRequirements": total,
        "coveredRequirements": covered,
        "verifiedRequirements": counts["VERIFIED"],
        "failedRequirements": counts["FAILED"],
        "blockedRequirements": counts["BLOCKED"],
        "unverifiedRequirements": counts["UNVERIFIED"] + counts["INCONCLUSIVE"],
        "uncoveredRequirements": counts["UNCOVERED"],
    }
