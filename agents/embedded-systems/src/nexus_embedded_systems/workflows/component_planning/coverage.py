"""Coverage summary helpers for Component Plan."""

from __future__ import annotations

from typing import Any

from nexus_contracts.validation.semantic_validators import (
    compute_component_plan_coverage_summary,
)


def compute_coverage_summary(
    content: dict[str, Any],
    *,
    architecture_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    architecture_node_ids: set[str] | None = None
    if isinstance(architecture_content, dict):
        nodes = architecture_content.get("nodes") or []
        architecture_node_ids = {
            node.get("nodeId")
            for node in nodes
            if isinstance(node, dict) and isinstance(node.get("nodeId"), str)
        }
    summary = compute_component_plan_coverage_summary(
        content,
        architecture_node_ids=architecture_node_ids,
    )
    if architecture_node_ids is not None:
        # Prefer sorted uncovered list for stable outputs.
        summary["uncoveredArchitectureNodeIds"] = sorted(
            architecture_node_ids.difference(
                {
                    node_id
                    for role in (content.get("componentRoles") or [])
                    if isinstance(role, dict)
                    for node_id in (role.get("architectureNodeIds") or [])
                    if isinstance(node_id, str)
                }
            )
        )
        summary["uncoveredRequirementIds"] = []
        summary["totalRelevantRequirements"] = len(summary["coveredRequirementIds"])
    return summary
