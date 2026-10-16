"""Deterministic criterion evaluation for TestCases (Phase 17C).

LLMs must never author PASS/FAIL/INCONCLUSIVE for evidence-backed criteria.
"""

from __future__ import annotations

from typing import Any, Literal

AssessmentResult = Literal["PASS", "FAIL", "INCONCLUSIVE"]

VERIFICATION_METHODS = frozenset(
    {
        "inspection",
        "simulation",
        "firmware-test",
        "analysis",
        "execution-output",
        "manual",
    }
)

TEST_STATUSES = frozenset(
    {
        "planned",
        "ready",
        "running",
        "passed",
        "failed",
        "blocked",
        "inconclusive",
    }
)

CRITERION_TYPES = frozenset(
    {
        "numeric-comparison",
        "exact-match",
        "contains",
        "existence",
        "structural-mapping",
        "range",
    }
)


def evaluate_criterion(
    criterion: dict[str, Any] | None,
    *,
    actual: Any = None,
    present: bool | None = None,
) -> tuple[AssessmentResult, str]:
    """Evaluate a typed criterion against a resolved actual.

    Returns (assessment, human-readable detail).
    Missing required actuals → INCONCLUSIVE (not FAIL).
    """

    if not isinstance(criterion, dict):
        return "INCONCLUSIVE", "No criterion defined."

    ctype = criterion.get("criterionType")
    if ctype not in CRITERION_TYPES:
        return "INCONCLUSIVE", f"Unknown criterionType: {ctype!r}"

    if ctype == "numeric-comparison":
        return _numeric(criterion, actual)
    if ctype == "range":
        return _range(criterion, actual)
    if ctype == "exact-match":
        if actual is None:
            return "INCONCLUSIVE", "Expected exact value was not observed."
        expected = criterion.get("expectedValue", criterion.get("marker"))
        ok = str(actual) == str(expected)
        return ("PASS" if ok else "FAIL"), f"{actual!r} == {expected!r}"
    if ctype == "contains":
        if actual is None:
            return "INCONCLUSIVE", "Expected marker was not observed."
        marker = str(criterion.get("marker") or criterion.get("expectedValue") or "")
        text = str(actual)
        ok = marker in text
        return ("PASS" if ok else "FAIL"), f"contains {marker!r}"
    if ctype == "existence":
        if present is None and actual is None:
            return "INCONCLUSIVE", "Existence could not be resolved."
        exists = bool(present) if present is not None else bool(actual)
        name = criterion.get("outputName") or criterion.get("expectedValue") or "output"
        return ("PASS" if exists else "FAIL"), f"{name} {'present' if exists else 'missing'}"
    if ctype == "structural-mapping":
        if actual is None:
            return "INCONCLUSIVE", "Structural mapping evidence missing."
        expected = str(criterion.get("expectedMapping") or criterion.get("expectedValue") or "")
        observed = str(actual)
        ok = observed.upper() == expected.upper() or expected.upper() in observed.upper()
        signal = criterion.get("signal") or "signal"
        return ("PASS" if ok else "FAIL"), f"{signal}: {observed} (expected {expected})"

    return "INCONCLUSIVE", "Unsupported criterion."


def _numeric(criterion: dict[str, Any], actual: Any) -> tuple[AssessmentResult, str]:
    if actual is None:
        metric = criterion.get("metricId") or "metric"
        return "INCONCLUSIVE", f"Expected metric {metric} was not produced."
    try:
        value = float(actual)
        threshold = float(criterion["expectedValue"])
    except (KeyError, TypeError, ValueError):
        return "INCONCLUSIVE", "Numeric criterion or actual is not comparable."
    operator = criterion.get("operator") or "<"
    ops = {
        "<": value < threshold,
        "<=": value <= threshold,
        ">": value > threshold,
        ">=": value >= threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }
    if operator not in ops:
        return "INCONCLUSIVE", f"Unknown operator {operator!r}"
    unit = criterion.get("unit") or ""
    detail = f"{value} {operator} {threshold}" + (f" {unit}" if unit else "")
    return ("PASS" if ops[operator] else "FAIL"), detail


def _range(criterion: dict[str, Any], actual: Any) -> tuple[AssessmentResult, str]:
    if actual is None:
        return "INCONCLUSIVE", "Range metric was not produced."
    try:
        value = float(actual)
        lo = float(criterion["minValue"])
        hi = float(criterion["maxValue"])
    except (KeyError, TypeError, ValueError):
        return "INCONCLUSIVE", "Range criterion or actual is not comparable."
    ok = lo <= value <= hi
    unit = criterion.get("unit") or ""
    detail = f"{value} in [{lo}, {hi}]" + (f" {unit}" if unit else "")
    return ("PASS" if ok else "FAIL"), detail


def status_from_assessment(assessment: AssessmentResult) -> str:
    if assessment == "PASS":
        return "passed"
    if assessment == "FAIL":
        return "failed"
    return "inconclusive"
