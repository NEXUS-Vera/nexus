"""Assemble ComponentPlanContent and artifact envelopes."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import artifact_envelope, new_id

from .coverage import compute_coverage_summary
from .derive_constraints import derive_constraints_from_requirements
from .derive_roles import derive_roles_from_architecture
from .maturity import compute_maturity
from .propose_candidates import propose_candidates_for_roles


def compose_component_plan_content(
    *,
    architecture_content: dict[str, Any],
    requirement_set_content: dict[str, Any],
    include_candidates: bool = True,
    source: str = "inferred",
) -> dict[str, Any]:
    """Deterministically derive a minimal valid Component Plan from architecture + requirements."""

    roles = derive_roles_from_architecture(architecture_content, source=source)
    requirements = list(requirement_set_content.get("requirements") or [])
    constraints = derive_constraints_from_requirements(roles=roles, requirements=requirements)
    candidates = (
        propose_candidates_for_roles(roles, max_per_role=1, source="fixture")
        if include_candidates
        else []
    )
    selections: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []

    # Phase 12 minimum: leave selections empty unless candidates exist and we want proposals.
    # Roles-defined maturity matches golden fixture style when candidates are omitted.
    content: dict[str, Any] = {
        "componentPlanId": new_id("cplan_"),
        "maturity": "roles-defined",
        "summary": _summary(roles, candidates),
        "componentRoles": roles,
        "selectionConstraints": constraints,
        "candidates": candidates,
        "selectionDecisions": selections,
        "compatibilityChecks": checks,
        "openQuestions": open_questions,
        "assumptions": [
            "Candidate retrieval and datasheet grounding are deferred until constraints "
            "are confirmed."
            if not candidates
            else "Provisional candidates are fixture-backed placeholders pending grounding."
        ],
        "evidenceReferences": [],
        "coverageSummary": {
            "totalArchitectureNodes": 0,
            "coveredArchitectureNodes": 0,
            "uncoveredArchitectureNodeIds": [],
            "totalRelevantRequirements": 0,
            "coveredRequirementIds": [],
            "uncoveredRequirementIds": [],
            "rolesWithoutArchitectureMapping": 0,
            "rolesWithoutRequirementMapping": 0,
            "rolesWithoutCandidates": 0,
            "rolesWithBlockedSelection": 0,
            "rolesAwaitingApproval": 0,
        },
        "validationSummary": {
            "issueCount": 0,
            "blockingIssueCount": 0,
            "warningCount": 0,
            "status": "ok",
        },
    }
    content["coverageSummary"] = compute_coverage_summary(
        content, architecture_content=architecture_content
    )
    content["maturity"] = compute_maturity(content)
    return content


def compose_component_plan_envelope(
    *,
    content: dict[str, Any],
    project_id: str,
    turn_id: str,
    workflow_run_id: str,
    created_by: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    return artifact_envelope(
        artifact_type="component-plan",
        content=content,
        project_id=project_id,
        turn_id=turn_id,
        workflow_run_id=workflow_run_id,
        created_by=created_by,
        now=now,
        lifecycle_status="drafted",
        evidence_status="unverified",
        approval_status="not-required",
    )


def _summary(roles: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    role_count = len(roles)
    candidate_count = len(candidates)
    if candidate_count:
        return (
            f"Provisional component plan with {role_count} role(s) and "
            f"{candidate_count} fixture candidate(s) pending grounding and approval."
        )
    return (
        f"Initial component roles ({role_count}) derived from functional architecture "
        "for provisional sensor/compute planning."
    )
