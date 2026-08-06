"""Selective Component Plan revisions for fixture-mode modifications."""

from __future__ import annotations

import copy
from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id, utc_now

from .coverage import compute_coverage_summary
from .maturity import compute_maturity
from .propose_candidates import propose_candidates_for_roles


class ComponentPlanRevisionError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def apply_component_plan_operation(
    content: dict[str, Any],
    *,
    operation: str,
    message: str,
    architecture_content: dict[str, Any] | None = None,
    target_role_id: str | None = None,
    target_candidate_id: str | None = None,
    target_question_id: str | None = None,
) -> dict[str, Any]:
    """Apply a selective component-plan mutation, preserving unaffected role IDs."""

    updated = copy.deepcopy(content)
    roles = list(updated.get("componentRoles") or [])
    candidates = list(updated.get("candidates") or [])
    selections = list(updated.get("selectionDecisions") or [])
    constraints = list(updated.get("selectionConstraints") or [])
    open_questions = list(updated.get("openQuestions") or [])

    if operation == "reject-component-candidate":
        candidate_id = target_candidate_id or _single_candidate_id(candidates)
        found = False
        for candidate in candidates:
            if candidate.get("candidateId") == candidate_id:
                candidate["candidateState"] = "rejected"
                found = True
        if not found:
            raise ComponentPlanRevisionError(
                code="COMPONENT_CANDIDATE_NOT_FOUND",
                message="No matching component candidate to reject.",
            )
        selections = [
            s for s in selections if s.get("selectedCandidateId") != candidate_id
        ]

    elif operation == "approve-component-selection":
        candidate_id = target_candidate_id or _single_candidate_id(candidates)
        candidate = next((c for c in candidates if c.get("candidateId") == candidate_id), None)
        if candidate is None:
            raise ComponentPlanRevisionError(
                code="COMPONENT_CANDIDATE_NOT_FOUND",
                message="No matching component candidate to approve.",
            )
        if candidate.get("candidateState") in {"blocked", "rejected"}:
            raise ComponentPlanRevisionError(
                code="COMPONENT_SELECTION_BLOCKED_CANDIDATE_APPROVED",
                message="Blocked or rejected candidates cannot be approved.",
            )
        role_id = candidate["componentRoleId"]
        # Demote other approved selections for this role.
        for selection in selections:
            if (
                selection.get("componentRoleId") == role_id
                and selection.get("selectionState") == "approved"
            ):
                selection["selectionState"] = "superseded"
        selections.append(
            {
                "selectionDecisionId": new_id("sel_"),
                "componentRoleId": role_id,
                "selectedCandidateId": candidate_id,
                "selectionState": "approved",
                "rationale": f"User approved selection: {message[:160]}",
                "tradeoffs": [],
                "source": "user-explicit",
                "proposedBy": {
                    "schemaVersion": "1.0.0",
                    "actorId": new_id("actor_"),
                    "actorType": "user",
                    "displayName": "User",
                },
                "approvalRequirement": {
                    "schemaVersion": "1.0.0",
                    "required": True,
                    "reason": "Component selection requires user confirmation before procurement.",
                    "consequenceLevel": "high",
                    "allowedApproverKinds": ["user"],
                    "autoAcceptAllowed": False,
                },
                "createdAt": utc_now(),
            }
        )
        candidate["candidateState"] = "selected"
        for role in roles:
            if role.get("componentRoleId") == role_id:
                role["status"] = "selected"

    elif operation == "change-component-preference":
        candidate_id = target_candidate_id or _single_candidate_id(candidates)
        for candidate in candidates:
            if candidate.get("candidateId") == candidate_id:
                candidate["candidateState"] = "preferred"
                candidate["notes"] = f"Preferred per user: {message[:160]}"
            elif candidate.get("componentRoleId") == (
                next(
                    (
                        c.get("componentRoleId")
                        for c in candidates
                        if c.get("candidateId") == candidate_id
                    ),
                    None,
                )
            ) and candidate.get("candidateState") == "preferred":
                candidate["candidateState"] = "proposed"

    elif operation == "add-component-constraint":
        role_id = target_role_id or _single_role_id(roles)
        constraints.append(
            {
                "constraintId": new_id("cstr_"),
                "componentRoleId": role_id,
                "constraintType": "cost",
                "operator": "unknown",
                "targetValue": {"kind": "unknown"},
                "unit": "USD",
                "sourceRequirementIds": [],
                "sourceArchitectureNodeIds": _role_arch_ids(roles, role_id),
                "importance": "required",
                "confirmationStatus": "confirmed",
                "rationale": f"Budget constraint from user: {message[:160]}",
            }
        )

    elif operation == "change-interface-constraint":
        role_id = target_role_id or _single_role_id(roles)
        updated_existing = False
        for constraint in constraints:
            if (
                constraint.get("componentRoleId") == role_id
                and constraint.get("constraintType") == "interface"
            ):
                constraint["rationale"] = f"Updated interface constraint: {message[:160]}"
                constraint["confirmationStatus"] = "confirmed"
                constraint["operator"] = "unknown"
                constraint["targetValue"] = {"kind": "unknown"}
                updated_existing = True
        if not updated_existing:
            constraints.append(
                {
                    "constraintId": new_id("cstr_"),
                    "componentRoleId": role_id,
                    "constraintType": "interface",
                    "operator": "unknown",
                    "targetValue": {"kind": "unknown"},
                    "unit": None,
                    "sourceRequirementIds": [],
                    "sourceArchitectureNodeIds": _role_arch_ids(roles, role_id),
                    "importance": "required",
                    "confirmationStatus": "confirmed",
                    "rationale": f"Interface constraint from user: {message[:160]}",
                }
            )

    elif operation == "request-component-alternatives":
        role_id = target_role_id or _single_role_id(roles)
        role = next((r for r in roles if r.get("componentRoleId") == role_id), None)
        if role is None:
            raise ComponentPlanRevisionError(
                code="COMPONENT_ROLE_NOT_FOUND",
                message="No matching component role for alternatives.",
            )
        existing_for_role = [
            c for c in candidates if c.get("componentRoleId") == role_id
        ]
        # Add one alternative at a time to keep selective updates unambiguous.
        extras = propose_candidates_for_roles([role], max_per_role=2, source="fixture")
        for candidate in extras:
            if any(
                c.get("componentRoleId") == role_id
                and c.get("partNumber") == candidate.get("partNumber")
                for c in existing_for_role
            ):
                continue
            candidates.append(candidate)
            break
        if len(candidates) == len(updated.get("candidates") or []):
            # No new part numbers available; still mint a distinct alternate label.
            extras = propose_candidates_for_roles([role], max_per_role=1, source="fixture")
            if extras:
                alt = dict(extras[0])
                alt["candidateId"] = new_id("cand_")
                alt["partNumber"] = f"{alt['partNumber']}-ALT"
                alt["displayName"] = f"{alt['displayName']} alternative"
                candidates.append(alt)

    elif operation == "answer-component-open-question":
        qid = target_question_id
        if qid:
            open_questions = [q for q in open_questions if q.get("questionId") != qid]
        elif open_questions:
            open_questions = open_questions[1:]
        # Mirror answer into a constraint when accuracy language is present.
        if "accur" in message.casefold() or "tolerance" in message.casefold():
            role_id = target_role_id or _single_role_id(roles)
            constraints.append(
                {
                    "constraintId": new_id("cstr_"),
                    "componentRoleId": role_id,
                    "constraintType": "accuracy",
                    "operator": "unknown",
                    "targetValue": {"kind": "unknown"},
                    "unit": None,
                    "sourceRequirementIds": [],
                    "sourceArchitectureNodeIds": _role_arch_ids(roles, role_id),
                    "importance": "required",
                    "confirmationStatus": "confirmed",
                    "rationale": f"Accuracy answer: {message[:160]}",
                }
            )

    else:
        raise ComponentPlanRevisionError(
            code="UNSUPPORTED_COMPONENT_PLAN_OPERATION",
            message=f"Unsupported component plan operation: {operation}",
        )

    updated["componentRoles"] = roles
    updated["candidates"] = candidates
    updated["selectionDecisions"] = selections
    updated["selectionConstraints"] = constraints
    updated["openQuestions"] = open_questions
    updated["coverageSummary"] = compute_coverage_summary(
        updated, architecture_content=architecture_content
    )
    updated["maturity"] = compute_maturity(updated)
    updated["summary"] = (
        f"Updated component plan after {operation}. "
        f"{len(roles)} role(s), {len(candidates)} candidate(s)."
    )
    return updated


def _single_candidate_id(candidates: list[dict[str, Any]]) -> str:
    if len(candidates) == 0:
        raise ComponentPlanRevisionError(
            code="COMPONENT_CANDIDATE_NOT_FOUND",
            message="No component candidates are available.",
        )
    if len(candidates) > 1:
        raise ComponentPlanRevisionError(
            code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
            message="Multiple component candidates match. Specify which candidate to update.",
        )
    return candidates[0]["candidateId"]


def _single_role_id(roles: list[dict[str, Any]]) -> str:
    if len(roles) == 0:
        raise ComponentPlanRevisionError(
            code="COMPONENT_ROLE_NOT_FOUND",
            message="No component roles are available.",
        )
    if len(roles) > 1:
        raise ComponentPlanRevisionError(
            code="AMBIGUOUS_PROJECT_CHANGE_TARGET",
            message="Multiple component roles match. Specify which role to update.",
        )
    return roles[0]["componentRoleId"]


def _role_arch_ids(roles: list[dict[str, Any]], role_id: str) -> list[str]:
    for role in roles:
        if role.get("componentRoleId") == role_id:
            return [i for i in (role.get("architectureNodeIds") or []) if isinstance(i, str)]
    return []
