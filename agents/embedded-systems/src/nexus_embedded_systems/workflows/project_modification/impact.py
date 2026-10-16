"""Deterministic impact analysis for project modifications."""

from __future__ import annotations

from typing import Any

ARTIFACT_TYPES = (
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "component-plan",
    "electrical-architecture",
    "physical-architecture",
    "next-action",
)

# Categories that typically force architecture regeneration.
ARCHITECTURE_CATEGORIES = {
    "runtime",
    "power",
    "communication",
    "sensing",
    "environmental",
    "size",
    "weight",
    "mechanical",
    "safety",
}

COMPONENT_PLAN_OPS = {
    "reject-component-candidate",
    "approve-component-selection",
    "change-component-preference",
    "add-component-constraint",
    "change-interface-constraint",
    "request-component-alternatives",
    "answer-component-open-question",
}


def _append_layered_cascade(
    *,
    affected: list[str],
    stale: list[str],
    regenerate: list[str],
    reasons: list[dict[str, str]],
    include_component_plan: bool = False,
) -> None:
    """Cascade Functional → Component Plan → Electrical → Physical when needed."""

    if include_component_plan:
        affected.append("component-plan")
        stale.append("component-plan")
        regenerate.append("component-plan")
        reasons.append(
            {
                "artifactType": "component-plan",
                "reason": "Component plan depends on architecture and requirements.",
            }
        )

    affected.append("electrical-architecture")
    stale.append("electrical-architecture")
    regenerate.append("electrical-architecture")
    reasons.append(
        {
            "artifactType": "electrical-architecture",
            "reason": (
                "Electrical Architecture depends on Functional Architecture and Component Plan."
            ),
        }
    )
    affected.append("physical-architecture")
    stale.append("physical-architecture")
    regenerate.append("physical-architecture")
    reasons.append(
        {
            "artifactType": "physical-architecture",
            "reason": "Physical Architecture depends on Electrical Architecture.",
        }
    )


def analyze_impact(
    *,
    operation: str,
    requirement_categories: list[str] | None = None,
    semantic_change: bool = True,
    architecture_coverage_changed: bool = False,
) -> dict[str, Any]:
    """Return ProjectImpactAnalysis-shaped dict."""
    categories = {c.lower() for c in (requirement_categories or [])}
    changed: list[str] = []
    affected: list[str] = []
    stale: list[str] = []
    regenerate: list[str] = []
    reasons: list[dict[str, str]] = []

    if operation in COMPONENT_PLAN_OPS:
        changed.append("component-plan")
        regenerate.append("component-plan")
        reasons.append(
            {
                "artifactType": "component-plan",
                "reason": f"Component plan revised due to {operation}.",
            }
        )
        _append_layered_cascade(
            affected=affected,
            stale=stale,
            regenerate=regenerate,
            reasons=reasons,
            include_component_plan=False,
        )
        affected.append("next-action")
        regenerate.append("next-action")
        reasons.append(
            {
                "artifactType": "next-action",
                "reason": "Next action refreshed after component-plan change.",
            }
        )
        # Downstream planning surfaces that may later depend on selections.
        for downstream in ("firmware", "test", "risk"):
            if downstream in ARTIFACT_TYPES:
                affected.append(downstream)
        regenerate = list(dict.fromkeys(regenerate))
        changed = list(dict.fromkeys(changed))
        affected = list(dict.fromkeys(affected))
        stale = list(dict.fromkeys(stale))
        unchanged = [
            t for t in ARTIFACT_TYPES if t not in set(changed) | set(affected) | set(regenerate)
        ]
        return {
            "schemaVersion": "1.0.0",
            "changed": changed,
            "affected": affected,
            "stale": stale,
            "regenerate": regenerate,
            "unchanged": unchanged,
            "reasonByArtifact": reasons,
        }

    if operation in {
        "clarify-requirement",
        "add-requirement",
        "change-requirement",
        "remove-proposed-requirement",
        "answer-open-question",
        "change-project-scope",
    }:
        changed.append("requirement-set")
        regenerate.append("requirement-set")
        reasons.append(
            {
                "artifactType": "requirement-set",
                "reason": f"Requirement set revised due to {operation}.",
            }
        )

    needs_architecture = (
        operation == "change-project-scope"
        or (operation == "remove-proposed-requirement" and architecture_coverage_changed)
        or (semantic_change and bool(categories & ARCHITECTURE_CATEGORIES))
        or (
            operation == "add-requirement"
            and semantic_change
            and bool(categories & ARCHITECTURE_CATEGORIES)
        )
    )

    if needs_architecture:
        affected.append("functional-architecture")
        stale.append("functional-architecture")
        regenerate.append("functional-architecture")
        reasons.append(
            {
                "artifactType": "functional-architecture",
                "reason": "Architecture impacted by requirement/category change.",
            }
        )
        _append_layered_cascade(
            affected=affected,
            stale=stale,
            regenerate=regenerate,
            reasons=reasons,
            include_component_plan=True,
        )

    # Next action nearly always refreshes after a modification.
    if changed or affected:
        affected.append("next-action")
        regenerate.append("next-action")
        reasons.append(
            {
                "artifactType": "next-action",
                "reason": "Next action refreshed after project state change.",
            }
        )

    if operation == "change-project-scope":
        changed.append("project-brief")
        regenerate.append("project-brief")
        reasons.append(
            {
                "artifactType": "project-brief",
                "reason": "Project scope change updates the brief.",
            }
        )

    regenerate = list(dict.fromkeys(regenerate))
    changed = list(dict.fromkeys(changed))
    affected = list(dict.fromkeys(affected))
    stale = list(dict.fromkeys(stale))
    unchanged = [
        t for t in ARTIFACT_TYPES if t not in set(changed) | set(affected) | set(regenerate)
    ]

    return {
        "schemaVersion": "1.0.0",
        "changed": changed,
        "affected": affected,
        "stale": stale,
        "regenerate": regenerate,
        "unchanged": unchanged,
        "reasonByArtifact": reasons,
    }
