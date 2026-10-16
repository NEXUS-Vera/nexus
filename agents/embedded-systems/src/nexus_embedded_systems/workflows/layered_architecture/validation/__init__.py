"""Electrical Architecture validation (Phase 13A continuation)."""

from .electrical_rules import (
    electrical_validation_warnings,
    run_electrical_validation,
)
from .registry import ElectricalValidationRegistry, rule_results_to_warnings
from .rules import RuleResult, make_rule_result

__all__ = [
    "ElectricalValidationRegistry",
    "RuleResult",
    "electrical_validation_warnings",
    "make_rule_result",
    "rule_results_to_warnings",
    "run_electrical_validation",
]
