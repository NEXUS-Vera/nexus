"""Electrical Architecture validation rule registry."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from nexus_embedded_systems.workflows.layered_architecture.validation.rules import (
    RuleResult,
)


@runtime_checkable
class ElectricalValidationRule(Protocol):
    """Protocol for a deterministic Electrical Architecture validation rule."""

    @property
    def rule_id(self) -> str: ...

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]: ...


class ElectricalValidationRegistry:
    """Ordered registry of Electrical Architecture validation rules."""

    def __init__(self) -> None:
        self._rules: dict[str, ElectricalValidationRule] = {}

    def register(self, rule: ElectricalValidationRule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule already registered: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def run_all(self, content: dict[str, Any]) -> list[RuleResult]:
        results: list[RuleResult] = []
        for rule in self._rules.values():
            results.extend(rule.evaluate(content))
        return results

    @property
    def rule_ids(self) -> list[str]:
        return list(self._rules.keys())


def rule_results_to_warnings(results: list[RuleResult]) -> list[dict[str, Any]]:
    """Map rule results into Electrical Architecture warning objects."""

    warnings: list[dict[str, Any]] = []
    for result in results:
        if result.get("status") in {"pass", "not-applicable"}:
            continue
        related = [
            entity_id
            for entity_id in (result.get("subjectEntityIds") or [])
            if isinstance(entity_id, str) and entity_id.startswith("enode_")
        ]
        warning: dict[str, Any] = {
            "code": result["ruleId"],
            "message": result["message"],
            "severity": result["severity"],
        }
        if related:
            warning["relatedNodeIds"] = related
        warnings.append(warning)
    return warnings
