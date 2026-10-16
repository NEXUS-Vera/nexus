"""Reconcile Component Plan content across architecture-driven refreshes."""

from __future__ import annotations

import copy
from typing import Any

from .compose import compose_component_plan_content
from .coverage import compute_coverage_summary
from .maturity import compute_maturity


def reconcile_component_plan_after_architecture_change(
    old_content: dict[str, Any],
    *,
    architecture_content: dict[str, Any],
    requirement_set_content: dict[str, Any],
) -> dict[str, Any]:
    """Recompose roles/candidates while preserving compatible approved selections.

    An approved selection survives when:
    - its role's architecture-node binding still exists on a fresh role; and
    - the approved candidate is still present (or can be restored) for that role; and
    - the candidate is not blocked/rejected.

    If the role disappears or binding materially changes, the prior approval is
    marked ``superseded`` with an explicit rationale rather than silently dropped.
    """

    fresh = compose_component_plan_content(
        architecture_content=architecture_content,
        requirement_set_content=requirement_set_content,
        include_candidates=True,
        source="inferred",
    )

    old_roles = [r for r in (old_content.get("componentRoles") or []) if isinstance(r, dict)]
    old_by_nodes: dict[tuple[str, ...], dict[str, Any]] = {}
    old_by_id: dict[str, dict[str, Any]] = {}
    for role in old_roles:
        role_id = role.get("componentRoleId")
        if isinstance(role_id, str):
            old_by_id[role_id] = role
        key = tuple(
            sorted(i for i in (role.get("architectureNodeIds") or []) if isinstance(i, str))
        )
        if key:
            old_by_nodes[key] = role

    old_candidates = [c for c in (old_content.get("candidates") or []) if isinstance(c, dict)]
    old_candidates_by_id = {
        c["candidateId"]: c for c in old_candidates if isinstance(c.get("candidateId"), str)
    }
    old_selections = [
        s for s in (old_content.get("selectionDecisions") or []) if isinstance(s, dict)
    ]
    approved_by_role: dict[str, dict[str, Any]] = {}
    for selection in old_selections:
        if selection.get("selectionState") != "approved":
            continue
        role_id = selection.get("componentRoleId")
        if isinstance(role_id, str):
            approved_by_role[role_id] = selection

    id_remap: dict[str, str] = {}
    surviving_role_ids: set[str] = set()
    for role in fresh.get("componentRoles") or []:
        if not isinstance(role, dict):
            continue
        key = tuple(
            sorted(i for i in (role.get("architectureNodeIds") or []) if isinstance(i, str))
        )
        prior = old_by_nodes.get(key)
        new_role_id = role.get("componentRoleId")
        if prior and isinstance(prior.get("componentRoleId"), str) and isinstance(new_role_id, str):
            prior_id = prior["componentRoleId"]
            id_remap[new_role_id] = prior_id
            role["componentRoleId"] = prior_id
            role["displayId"] = prior.get("displayId") or role.get("displayId")
            surviving_role_ids.add(prior_id)
            # Preserve selected status if approval will be restored.
            if prior_id in approved_by_role:
                role["status"] = prior.get("status") or "selected"

    if id_remap:
        for collection_key in (
            "selectionConstraints",
            "candidates",
            "selectionDecisions",
            "compatibilityChecks",
        ):
            for item in fresh.get(collection_key) or []:
                if not isinstance(item, dict):
                    continue
                role_id = item.get("componentRoleId")
                if isinstance(role_id, str) and role_id in id_remap:
                    item["componentRoleId"] = id_remap[role_id]

    # Restore approved selections onto surviving roles.
    fresh_candidates = list(fresh.get("candidates") or [])
    fresh_candidate_ids = {
        c.get("candidateId")
        for c in fresh_candidates
        if isinstance(c, dict) and isinstance(c.get("candidateId"), str)
    }
    fresh_selections = [s for s in (fresh.get("selectionDecisions") or []) if isinstance(s, dict)]
    preserved_approvals: list[dict[str, Any]] = []
    orphaned_approvals: list[dict[str, Any]] = []

    for old_role_id, approval in approved_by_role.items():
        if old_role_id not in surviving_role_ids:
            orphaned = copy.deepcopy(approval)
            orphaned["selectionState"] = "superseded"
            orphaned["rationale"] = (
                "Approved selection superseded because the Component Role binding "
                "no longer exists after architecture reconciliation."
            )
            orphaned_approvals.append(orphaned)
            continue

        candidate_id = approval.get("selectedCandidateId")
        if not isinstance(candidate_id, str):
            continue
        candidate = old_candidates_by_id.get(candidate_id)
        if candidate is None or candidate.get("candidateState") in {"blocked", "rejected"}:
            orphaned = copy.deepcopy(approval)
            orphaned["selectionState"] = "superseded"
            orphaned["rationale"] = (
                "Approved selection superseded because the approved candidate is "
                "missing or blocking after architecture reconciliation."
            )
            orphaned_approvals.append(orphaned)
            continue

        # Ensure candidate exists in fresh plan under the surviving role id.
        if candidate_id not in fresh_candidate_ids:
            restored = copy.deepcopy(candidate)
            restored["componentRoleId"] = old_role_id
            restored["candidateState"] = "selected"
            fresh_candidates.append(restored)
            fresh_candidate_ids.add(candidate_id)
        else:
            for cand in fresh_candidates:
                if cand.get("candidateId") == candidate_id:
                    cand["candidateState"] = "selected"
                    cand["componentRoleId"] = old_role_id

        # Drop provisional awaiting-user selections for this role.
        fresh_selections = [
            s
            for s in fresh_selections
            if not (
                s.get("componentRoleId") == old_role_id
                and s.get("selectionState") in {"proposed", "awaiting-user", "not-started"}
            )
        ]
        preserved = copy.deepcopy(approval)
        preserved["componentRoleId"] = old_role_id
        preserved_approvals.append(preserved)

    fresh["candidates"] = fresh_candidates
    fresh["selectionDecisions"] = preserved_approvals + fresh_selections + orphaned_approvals

    # Note orphaned role disappearances in assumptions.
    assumptions = list(fresh.get("assumptions") or [])
    if orphaned_approvals:
        assumptions.append(
            "One or more previously approved Component selections were superseded "
            "because their role binding or candidate compatibility no longer holds."
        )
    fresh["assumptions"] = assumptions

    arch_for_coverage = architecture_content
    fresh["coverageSummary"] = compute_coverage_summary(
        fresh, architecture_content=arch_for_coverage
    )
    fresh["maturity"] = compute_maturity(fresh)
    return fresh
