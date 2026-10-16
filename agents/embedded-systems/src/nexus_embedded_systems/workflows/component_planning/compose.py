"""Assemble ComponentPlanContent and artifact envelopes."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import (
    artifact_envelope,
    default_actor,
    new_id,
    utc_now,
)

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
    proposed_by: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Derive a provisional Component Plan from architecture and requirements."""

    stamp = now or utc_now()
    actor = proposed_by or default_actor("vera", display_name="Vera")
    roles = derive_roles_from_architecture(architecture_content, source=source)
    requirements = list(requirement_set_content.get("requirements") or [])
    constraints = derive_constraints_from_requirements(roles=roles, requirements=requirements)
    candidates = (
        propose_candidates_for_roles(roles, max_per_role=2, source="fixture", prefer_first=True)
        if include_candidates
        else []
    )
    selections: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []

    if include_candidates and candidates:
        preferred_by_role: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            role_id = str(candidate["componentRoleId"])
            if candidate.get("candidateState") == "preferred" and role_id not in preferred_by_role:
                preferred_by_role[role_id] = candidate

        for role in roles:
            role_id = str(role["componentRoleId"])
            preferred = preferred_by_role.get(role_id)
            if preferred is None:
                role["status"] = "needs-clarification"
                continue
            check = _interface_check(role, preferred, actor=actor, now=stamp)
            checks.append(check)
            preferred["compatibilityCheckIds"] = [check["compatibilityCheckId"]]
            selections.append(
                {
                    "selectionDecisionId": new_id("sel_"),
                    "componentRoleId": role_id,
                    "selectedCandidateId": preferred["candidateId"],
                    "selectionState": "awaiting-user",
                    "rationale": (
                        f"Provisional preference for {preferred['displayName']} based on "
                        "known interface/supply assumptions pending user approval."
                    ),
                    "tradeoffs": list(preferred.get("limitations") or [])[:3]
                    or ["Evidence remains unverified"],
                    "source": "fixture" if source == "fixture" else "agent-proposed",
                    "proposedBy": actor,
                    "approvalRequirement": {
                        "schemaVersion": "1.0.0",
                        "required": True,
                        "reason": (
                            "Component selection requires user confirmation before procurement."
                        ),
                        "consequenceLevel": "high",
                        "allowedApproverKinds": ["user"],
                        "autoAcceptAllowed": False,
                    },
                    "createdAt": stamp,
                }
            )
            role["status"] = "selection-proposed"

        for role in roles:
            if not role.get("requirementIds"):
                qid = new_id("q_")
                open_questions.append(
                    {
                        "questionId": qid,
                        "summary": f"Which requirements justify the {role['name']}?",
                    }
                )
                role["openQuestionIds"] = [qid]

    content: dict[str, Any] = {
        "componentPlanId": new_id("cplan_"),
        "maturity": "roles-defined",
        "summary": _summary(roles, candidates, selections),
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
            else (
                "Provisional candidates are fixture-backed placeholders. "
                "Pricing, availability, and datasheet claims remain unverified."
            )
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
            "issueCount": len(open_questions) + sum(1 for c in checks if c.get("status") != "pass"),
            "blockingIssueCount": 0,
            "warningCount": sum(
                1 for c in checks if c.get("status") in {"unknown", "conditional", "warning"}
            ),
            "status": "warnings" if checks else "ok",
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
        approval_status="proposed",
    )


def _interface_check(
    role: dict[str, Any],
    candidate: dict[str, Any],
    *,
    actor: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    specs = candidate.get("specifications") or []
    has_interface = any(
        isinstance(s, dict) and s.get("specKey") == "interface" and not _is_unknown(s.get("value"))
        for s in specs
    )
    status = "conditional" if has_interface else "unknown"
    return {
        "compatibilityCheckId": new_id("cchk_"),
        "componentRoleId": role["componentRoleId"],
        "candidateId": candidate["candidateId"],
        "checkType": "interface-type",
        "status": status,
        "severity": "warning",
        "reason": (
            "Candidate declares an interface, but bus topology and address conflicts "
            "are not yet checked against the full architecture."
            if has_interface
            else "Interface requirement or candidate interface value is unknown."
        ),
        "inputReferences": list(role.get("architectureNodeIds") or [])[:4],
        "evidenceReferences": [],
        "performedBy": actor,
        "performedAt": now,
    }


def _is_unknown(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == "unknown"


def _summary(
    roles: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    selections: list[dict[str, Any]],
) -> str:
    role_count = len(roles)
    candidate_count = len(candidates)
    preferred = sum(
        1 for s in selections if s.get("selectionState") in {"proposed", "awaiting-user"}
    )
    if candidate_count:
        return (
            f"Provisional component plan with {role_count} role(s), "
            f"{candidate_count} fixture candidate(s), and {preferred} preferred "
            "proposal(s) awaiting user approval. Evidence remains unverified."
        )
    return (
        f"Initial component roles ({role_count}) derived from functional architecture "
        "for provisional sensor/compute planning."
    )
