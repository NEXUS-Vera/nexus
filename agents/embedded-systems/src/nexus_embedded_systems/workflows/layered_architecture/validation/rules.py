"""Shared types for Electrical Architecture validation rules."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

RuleStatus = Literal["pass", "fail", "warning", "unknown", "not-applicable"]
RuleSeverity = Literal["info", "warning", "blocking"]


class RuleResult(TypedDict):
    """Outcome of a single Electrical Architecture validation rule evaluation."""

    ruleId: str
    status: RuleStatus
    severity: RuleSeverity
    subjectEntityIds: list[str]
    message: str
    details: NotRequired[dict[str, Any]]


def make_rule_result(
    *,
    rule_id: str,
    status: RuleStatus,
    severity: RuleSeverity,
    message: str,
    subject_entity_ids: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> RuleResult:
    result: RuleResult = {
        "ruleId": rule_id,
        "status": status,
        "severity": severity,
        "subjectEntityIds": list(subject_entity_ids or []),
        "message": message,
    }
    if details is not None:
        result["details"] = details
    return result
