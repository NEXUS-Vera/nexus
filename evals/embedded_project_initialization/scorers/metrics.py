"""Aggregate metrics across a batch of eval case results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AggregateMetrics:
    total: int
    passed: int
    failed: int
    pass_rate: float
    outcome_match_rate: float
    structural_pass_rate: float
    claims_pass_rate: float
    by_category: dict[str, dict[str, float]] = field(default_factory=dict)


def aggregate_metrics(results: list[dict[str, Any]]) -> AggregateMetrics:
    """Summarize a list of per-case result dicts produced by `run_case`."""

    total = len(results)
    if total == 0:
        return AggregateMetrics(
            total=0,
            passed=0,
            failed=0,
            pass_rate=0.0,
            outcome_match_rate=0.0,
            structural_pass_rate=0.0,
            claims_pass_rate=0.0,
            by_category={},
        )

    passed = sum(1 for r in results if r.get("passed"))
    outcome_matches = sum(1 for r in results if r.get("outcomeMatch"))
    structural_passes = sum(
        1 for r in results if r.get("structural") is None or r["structural"].get("passed")
    )
    claims_passes = sum(1 for r in results if r.get("claims") is None or r["claims"].get("passed"))

    by_category: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_category.setdefault(result.get("category", "uncategorized"), []).append(result)

    category_summary = {
        category: {
            "total": float(len(items)),
            "pass_rate": sum(1 for item in items if item.get("passed")) / len(items),
        }
        for category, items in by_category.items()
    }

    return AggregateMetrics(
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=passed / total,
        outcome_match_rate=outcome_matches / total,
        structural_pass_rate=structural_passes / total,
        claims_pass_rate=claims_passes / total,
        by_category=category_summary,
    )
