"""Selective artifact regeneration for fixture-mode modifications."""

from __future__ import annotations

import copy
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from nexus_embedded_systems.workflows.component_planning import (
    apply_component_plan_operation,
    compose_component_plan_content,
)
from nexus_embedded_systems.workflows.project_initialization.next_action_selector import (
    select_next_action,
)

CURRENT_ARTIFACT_ORDER = (
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "component-plan",
    "next-action",
)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def revise_artifacts(
    *,
    current_state: dict[str, Any],
    intent: dict[str, Any],
    impact: dict[str, Any],
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return (current_artifacts, new_revisions_only, updated_project)."""
    project = copy.deepcopy(current_state["project"])
    by_type = {a["artifactType"]: copy.deepcopy(a) for a in current_state["artifacts"]}
    new_revisions: list[dict[str, Any]] = []
    regenerate = set(impact.get("regenerate") or [])
    ts = _now()

    if "requirement-set" in regenerate:
        old = by_type["requirement-set"]
        new = _revise_requirements(
            old, intent=intent, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts
        )
        by_type["requirement-set"] = new
        new_revisions.append(new)
        _mark_superseded_in_place(old)

    if "functional-architecture" in regenerate:
        old = by_type["functional-architecture"]
        new = _revise_architecture(
            old,
            requirements=by_type["requirement-set"],
            turn_id=turn_id,
            run_id=run_id,
            actor=actor,
            ts=ts,
        )
        by_type["functional-architecture"] = new
        new_revisions.append(new)

    if "project-brief" in regenerate:
        old = by_type["project-brief"]
        new = _bump_envelope(old, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts)
        content = copy.deepcopy(old["content"])
        content["summary"] = (
            f"{content.get('summary', '')} Updated scope: {intent['requestedChange']}".strip()
        )
        new["content"] = content
        by_type["project-brief"] = new
        new_revisions.append(new)

    if "component-plan" in regenerate and "component-plan" in by_type:
        old = by_type["component-plan"]
        new = _revise_component_plan(
            old,
            intent=intent,
            architecture=by_type.get("functional-architecture"),
            requirements=by_type.get("requirement-set"),
            turn_id=turn_id,
            run_id=run_id,
            actor=actor,
            ts=ts,
        )
        by_type["component-plan"] = new
        new_revisions.append(new)

    if "next-action" in regenerate:
        old = by_type["next-action"]
        new = _revise_next_action(
            old,
            project=project,
            requirements=by_type["requirement-set"],
            open_questions=current_state.get("openQuestions") or [],
            intent=intent,
            component_plan=by_type.get("component-plan"),
            turn_id=turn_id,
            run_id=run_id,
            actor=actor,
            ts=ts,
        )
        by_type["next-action"] = new
        new_revisions.append(new)

    # Resolve open questions in the returned openQuestions list (caller updates).
    project["currentStateVersion"] = int(project["currentStateVersion"]) + 1
    project["updatedAt"] = ts
    project["currentArtifactReferences"] = [
        {
            "artifactType": atype,
            "artifactId": by_type[atype]["artifactId"],
            "artifactVersion": by_type[atype]["artifactVersion"],
            "contentSchemaVersion": "1.0.0",
        }
        for atype in CURRENT_ARTIFACT_ORDER
        if atype in by_type
    ]
    return (
        [by_type[t] for t in CURRENT_ARTIFACT_ORDER if t in by_type],
        new_revisions,
        project,
    )


def apply_open_question_resolution(
    questions: list[dict[str, Any]], intent: dict[str, Any]
) -> list[dict[str, Any]]:
    out = copy.deepcopy(questions)
    qid = intent.get("targetQuestionId")
    if not qid:
        # Auto-resolve runtime questions when answering runtime constraints.
        if (intent.get("_meta") or {}).get("category") == "runtime":
            for q in out:
                if q.get("status") == "open" and any(
                    t in f"{q.get('question', '')} {q.get('reason', '')}".lower()
                    for t in ("runtime", "battery", "operating time", "power")
                ):
                    q["status"] = "resolved"
                    q["updatedAt"] = _now()
        return out
    found = False
    for q in out:
        if q["questionId"] == qid:
            q["status"] = "resolved"
            q["updatedAt"] = _now()
            found = True
    if not found:
        raise ValueError("OPEN_QUESTION_NOT_FOUND")
    return out


def _revise_requirements(
    old: dict[str, Any],
    *,
    intent: dict[str, Any],
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    new = _bump_envelope(old, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts)
    content = copy.deepcopy(old["content"])
    reqs = list(content.get("requirements") or [])
    op = intent["operation"]
    category = (intent.get("_meta") or {}).get("category") or "other"
    schema_category = _map_category(category)
    target = intent.get("targetRequirementId")
    statement = intent["requestedChange"]

    if op == "remove-proposed-requirement" and target:
        for req in reqs:
            if req["requirementId"] == target:
                req["confirmationStatus"] = "rejected"
    elif target:
        for req in reqs:
            if req["requirementId"] == target:
                req["statement"] = _compose_requirement_statement(statement, category)
                req["confirmationStatus"] = "confirmed"
                req["sourceType"] = "user-explicit"
                req["category"] = schema_category
                req["sourceReference"] = {
                    "schemaVersion": "1.0.0",
                    "evidenceId": _new_id("evi"),
                    "sourceType": "user-turn",
                    "sourceId": turn_id,
                    "evidenceStrength": "direct",
                    "sourceLocator": "rawUserMessage",
                }
    else:
        display_nums = []
        for req in reqs:
            m = re.match(r"R(\d+)", str(req.get("displayId", "")))
            if m:
                display_nums.append(int(m.group(1)))
        next_n = (max(display_nums) + 1) if display_nums else len(reqs) + 1
        reqs.append(
            {
                "requirementId": _new_id("req"),
                "displayId": f"R{next_n}",
                "statement": _compose_requirement_statement(statement, category),
                "category": schema_category,
                "priority": "must",
                "sourceType": "user-explicit",
                "sourceReference": {
                    "schemaVersion": "1.0.0",
                    "evidenceId": _new_id("evi"),
                    "sourceType": "user-turn",
                    "sourceId": turn_id,
                    "evidenceStrength": "direct",
                    "sourceLocator": "rawUserMessage",
                },
                "confidence": "high",
                "confirmationStatus": "confirmed",
                "verificationMethod": (
                    "Validate the updated constraint during prototype planning review."
                ),
            }
        )

    content["requirements"] = reqs
    content["requirementSummary"] = (
        f"Updated requirement set with {len(reqs)} requirements after {op}."
    )
    new["content"] = content
    return new


def _map_category(category: str) -> str:
    mapping = {
        "runtime": "resource",
        "power": "resource",
        "accuracy": "performance",
        "sampling": "performance",
        "environmental": "environmental",
        "communication": "interface",
        "size": "physical",
        "weight": "physical",
        "budget": "project-constraint",
        "sensing": "functional",
        "other": "functional",
    }
    return mapping.get(category, "functional")


def _compose_requirement_statement(message: str, category: str) -> str:
    if category == "runtime":
        return f"The device must satisfy this runtime/power constraint: {message}"
    if category == "accuracy":
        return f"Measurement accuracy must satisfy: {message}"
    return message


def _revise_architecture(
    old: dict[str, Any],
    *,
    requirements: dict[str, Any],
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    new = _bump_envelope(old, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts)
    content = copy.deepcopy(old["content"])
    req_ids = [
        r["requirementId"]
        for r in requirements["content"].get("requirements") or []
        if r.get("confirmationStatus") != "rejected"
    ]
    nodes = list(content.get("nodes") or [])
    satisfied: set[str] = set()
    for node in nodes:
        for rid in node.get("satisfiesRequirementIds") or []:
            satisfied.add(rid)
    missing = [rid for rid in req_ids if rid not in satisfied]
    if missing and nodes:
        first = dict(nodes[0])
        covers = list(first.get("satisfiesRequirementIds") or [])
        for rid in missing:
            if rid not in covers:
                covers.append(rid)
        first["satisfiesRequirementIds"] = covers
        # Ensure responsibilities mention power/runtime if needed.
        responsibilities = list(first.get("responsibilities") or [])
        responsibilities.append(
            "Represent confirmed runtime/power constraints for greenhouse operation."
        )
        first["responsibilities"] = responsibilities
        nodes[0] = first
        content["nodes"] = nodes
    coverage = content.get("requirementCoverage") or {"coveredRequirementIds": []}
    covered = list(coverage.get("coveredRequirementIds") or [])
    for rid in req_ids:
        if rid not in covered:
            covered.append(rid)
    if not covered and req_ids:
        covered = [req_ids[0]]
    content["requirementCoverage"] = {"coveredRequirementIds": covered}
    new["content"] = content
    new["lifecycleStatus"] = "ready"
    return new


def _revise_next_action(
    old: dict[str, Any],
    *,
    project: dict[str, Any],
    requirements: dict[str, Any],
    open_questions: list[dict[str, Any]],
    intent: dict[str, Any],
    component_plan: dict[str, Any] | None = None,
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    new = _bump_envelope(old, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts)
    open_q = [q for q in open_questions if q.get("status") == "open"]
    if intent.get("targetQuestionId"):
        open_q = [q for q in open_q if q["questionId"] != intent["targetQuestionId"]]
    if (intent.get("_meta") or {}).get("category") == "runtime":
        open_q = [
            q
            for q in open_q
            if not any(
                t in f"{q.get('question', '')}".lower()
                for t in ("runtime", "battery", "operating time", "power")
            )
        ]
    component_content = (component_plan or {}).get("content")
    if open_q:
        content = copy.deepcopy(old["content"])
        content["actionId"] = _new_id("act")
        content["title"] = "Clarify remaining unknowns"
        content["description"] = (
            "Answer the highest-priority open question so planning can continue."
        )
        content["rationale"] = "Open questions remain after the latest project update."
        content["completionCondition"] = {
            "conditionType": "unknowns-resolved",
            "completionCriteria": "User answers the highest-priority open question.",
        }
        content["sourceQuestionIds"] = [open_q[0]["questionId"]]
        content["prerequisites"] = [
            {
                "schemaVersion": "1.0.0",
                "questionId": open_q[0]["questionId"],
                **({"displayId": open_q[0]["displayId"]} if open_q[0].get("displayId") else {}),
            }
        ]
        content["owner"] = "vera"
        content["priority"] = "high"
        content["blocks"] = content.get("blocks") or []
        content["sourceIssueIds"] = content.get("sourceIssueIds") or []
        new["content"] = content
        return new

    selected = select_next_action(
        issues=[],
        open_questions=open_q,
        missing_dimensions=[],
        project_stage="prototype-planning",
        component_plan_content=component_content if isinstance(component_content, dict) else None,
    )
    new["content"] = selected
    return new


def _revise_component_plan(
    old: dict[str, Any],
    *,
    intent: dict[str, Any],
    architecture: dict[str, Any] | None,
    requirements: dict[str, Any] | None,
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    new = _bump_envelope(old, turn_id=turn_id, run_id=run_id, actor=actor, ts=ts)
    meta = intent.get("_meta") or {}
    operation = intent["operation"]
    architecture_content = (architecture or {}).get("content")
    if operation in {
        "reject-component-candidate",
        "approve-component-selection",
        "change-component-preference",
        "add-component-constraint",
        "change-interface-constraint",
        "request-component-alternatives",
        "answer-component-open-question",
    }:
        new["content"] = apply_component_plan_operation(
            old["content"],
            operation=operation,
            message=intent["requestedChange"],
            architecture_content=architecture_content
            if isinstance(architecture_content, dict)
            else None,
            target_role_id=meta.get("targetRoleId"),
            target_candidate_id=meta.get("targetCandidateId"),
            target_question_id=intent.get("targetQuestionId"),
        )
        return new

    # Architecture/requirement-driven refresh: recompose while preserving role IDs
    # when node mappings still match.
    if isinstance(architecture_content, dict) and isinstance(requirements, dict):
        fresh = compose_component_plan_content(
            architecture_content=architecture_content,
            requirement_set_content=requirements.get("content") or {},
            include_candidates=True,
            source="inferred",
        )
        old_roles = {
            tuple(sorted(r.get("architectureNodeIds") or [])): r
            for r in (old["content"].get("componentRoles") or [])
            if isinstance(r, dict)
        }
        id_remap: dict[str, str] = {}
        for role in fresh.get("componentRoles") or []:
            key = tuple(sorted(role.get("architectureNodeIds") or []))
            prior = old_roles.get(key)
            if prior and isinstance(prior.get("componentRoleId"), str):
                new_id = role.get("componentRoleId")
                if isinstance(new_id, str):
                    id_remap[new_id] = prior["componentRoleId"]
                role["componentRoleId"] = prior["componentRoleId"]
                role["displayId"] = prior.get("displayId") or role.get("displayId")
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
        new["content"] = fresh
        return new

    new["content"] = copy.deepcopy(old["content"])
    return new


def _bump_envelope(
    old: dict[str, Any],
    *,
    turn_id: str,
    run_id: str,
    actor: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    new = copy.deepcopy(old)
    new["artifactId"] = _new_id("art")
    new["artifactVersion"] = int(old["artifactVersion"]) + 1
    new["supersedesArtifactId"] = old["artifactId"]
    new["supersedesArtifactVersion"] = int(old["artifactVersion"])
    new["sourceTurnId"] = turn_id
    new["workflowRunId"] = run_id
    new["createdBy"] = actor
    new["createdAt"] = ts
    new["updatedAt"] = ts
    new["lifecycleStatus"] = "ready"
    return new


def _mark_superseded_in_place(old: dict[str, Any]) -> None:
    # Historical rows are immutable in the store; this only affects local copies.
    old["lifecycleStatus"] = "superseded"
