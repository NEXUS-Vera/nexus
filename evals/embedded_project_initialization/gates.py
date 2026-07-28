"""Quality gates applied to aggregate embedded-project-initialization eval results.

Gates are intentionally conservative: they fail a run only on outcomes that
indicate a real regression (a wrong supported/unsupported decision, an
invalid package, or a leaked forbidden claim/component), not on cosmetic
differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scorers.metrics import AggregateMetrics

MIN_PASS_RATE = 1.0
MIN_OUTCOME_MATCH_RATE = 1.0


@dataclass(frozen=True)
class GateResult:
    passed: bool
    failures: tuple[str, ...] = field(default_factory=tuple)


def evaluate_gates(
    results: list[dict[str, Any]],
    metrics: AggregateMetrics,
    *,
    min_pass_rate: float = MIN_PASS_RATE,
    min_outcome_match_rate: float = MIN_OUTCOME_MATCH_RATE,
) -> GateResult:
    """Evaluate hard quality gates for a completed eval run."""

    failures: list[str] = []

    if metrics.total == 0:
        failures.append("No eval cases were run.")

    if metrics.outcome_match_rate < min_outcome_match_rate:
        failures.append(
            f"outcome_match_rate {metrics.outcome_match_rate:.2f} is below the "
            f"required {min_outcome_match_rate:.2f}."
        )

    if metrics.pass_rate < min_pass_rate:
        failures.append(
            f"pass_rate {metrics.pass_rate:.2f} is below the required {min_pass_rate:.2f}."
        )

    forbidden_leak_case_ids = sorted(
        result["caseId"]
        for result in results
        if result.get("claims") and result["claims"].get("forbidden_hits")
    )
    if forbidden_leak_case_ids:
        failures.append(
            f"Forbidden component/claim leakage detected in cases: {forbidden_leak_case_ids}."
        )

    return GateResult(passed=not failures, failures=tuple(failures))
