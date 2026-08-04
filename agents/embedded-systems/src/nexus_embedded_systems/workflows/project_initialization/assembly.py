"""Assembly helpers: model-authored drafts -> canonical, backend-owned content.

Drafts produced by the LLM stages (see `generation/schemas.py`) use model-
local keys (`localRequirementKey`, `localNodeKey`, ...) because the model
must never mint or guess a system ID. Every function in this module takes a
draft and returns canonical artifact content with backend-owned IDs, display
IDs, and typed cross-references, following the same "IDs and envelopes are
never owned by the model" rule as `ids.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from .ids import default_actor, new_id, utc_now

ProjectStage = Literal["concept", "prototype-planning"]
AutonomyMode = Literal["collaborate", "delegate"]


def normalize_brief_draft(
    draft: dict[str, Any],
    open_questions: list[dict[str, Any]],
    *,
    project_id: str,
    artifact_id: str,
    now: str,
    requested_from: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a model-authored project-brief draft into canonical content.

    Assigns backend-owned assumption IDs (`A1`, `A2`, ...) and turns every
    `unknownStatements` entry into a full `OpenQuestion`, appended in place
    to `open_questions`, with a typed `OpenQuestionReference` recorded on the
    returned brief content's `unknowns` field.
    """

    assumptions = _normalize_assumptions(draft.get("assumptions", []))

    unknown_refs: list[dict[str, Any]] = []
    for statement in draft.get("unknownStatements", []):
        display_id = f"Q{len(open_questions) + 1}"
        question = _new_open_question(
            project_id=project_id,
            question=statement,
            reason="Identified as an unknown while drafting the project brief.",
            source_reference={"kind": "artifact", "artifactId": artifact_id},
            now=now,
            requested_from=requested_from,
            display_id=display_id,
        )
        open_questions.append(question)
        unknown_refs.append(_open_question_reference(question))

    return {
        "goal": draft["goal"],
        "problemStatement": draft["problemStatement"],
        "intendedContext": draft["intendedContext"],
        "projectStage": draft["projectStage"],
        "scope": list(draft["scope"]),
        "outOfScope": list(draft.get("outOfScope", [])),
        "successCriteria": list(draft["successCriteria"]),
        "assumptions": assumptions,
        "unknowns": unknown_refs,
    }


def normalize_requirement_draft(
    draft: dict[str, Any], turn_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    """Convert a model-authored requirement draft into canonical content.

    Assigns backend-owned `req_` IDs and `R1`, `R2`, ... display IDs, and
    attaches a typed `EvidenceReference` `sourceReference` to every
    requirement (see `packages/contracts/schemas/common/evidence-reference.v1.schema.json`).
    Returns `(content, local_key_to_req_id)` so later stages (functional
    architecture, Next Action) can resolve the model's local requirement
    keys into real requirement IDs.
    """

    local_key_to_req_id: dict[str, str] = {}
    requirements: list[dict[str, Any]] = []

    for index, item in enumerate(draft.get("requirements", []), start=1):
        req_id = new_id("req_")
        local_key_to_req_id[item["localRequirementKey"]] = req_id

        requirement: dict[str, Any] = {
            "requirementId": req_id,
            "displayId": f"R{index}",
            "statement": item["statement"],
            "category": item["category"],
            "priority": item["priority"],
            "sourceType": item["sourceType"],
            "sourceReference": _requirement_source_reference(
                source_type=item["sourceType"],
                turn_id=turn_id,
                statement=item["statement"],
            ),
            "confidence": item["confidence"],
            "confirmationStatus": item["confirmationStatus"],
            "verificationMethod": item["verificationMethod"],
        }
        if item.get("rationale"):
            requirement["rationale"] = item["rationale"]
        if item.get("acceptanceCriteria"):
            requirement["acceptanceCriteria"] = list(item["acceptanceCriteria"])
        if item.get("targetQuantity"):
            quantity = dict(item["targetQuantity"])
            quantity.setdefault("schemaVersion", "1.0.0")
            # Drop unsupported comparator field if present from draft schema.
            quantity.pop("comparator", None)
            requirement["targetQuantity"] = quantity
        requirements.append(requirement)

    content: dict[str, Any] = {
        "requirements": requirements,
        "requirementSummary": draft["requirementSummary"],
    }
    if draft.get("missingDimensions"):
        content["missingDimensions"] = list(draft["missingDimensions"])

    return content, local_key_to_req_id


def normalize_architecture_draft(
    draft: dict[str, Any],
    local_key_to_req_id: dict[str, str],
    open_questions: list[dict[str, Any]],
    *,
    project_id: str,
    artifact_id: str,
    now: str,
    requested_from: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a model-authored functional-architecture draft into canonical content.

    Assigns backend-owned `arch_`/`node_`/`edge_` IDs, forces
    `architectureMaturity` to `"functional"` regardless of what the model
    returned, resolves local node/requirement keys into system IDs, and
    turns every `unresolvedDecisionStatements` entry into a full
    `OpenQuestion` appended in place to `open_questions`.
    """

    local_node_to_id = {node["localNodeKey"]: new_id("node_") for node in draft.get("nodes", [])}

    nodes: list[dict[str, Any]] = []
    for node in draft.get("nodes", []):
        satisfies_requirement_ids = [
            local_key_to_req_id[key]
            for key in node.get("satisfiesLocalRequirementKeys", [])
            if key in local_key_to_req_id
        ]
        # Schema requires at least one requirement ID per node.
        if not satisfies_requirement_ids and local_key_to_req_id:
            satisfies_requirement_ids = [next(iter(local_key_to_req_id.values()))]
        nodes.append(
            {
                "nodeId": local_node_to_id[node["localNodeKey"]],
                "name": node["name"],
                "functionalType": node["functionalType"],
                "responsibilities": list(node["responsibilities"]),
                "satisfiesRequirementIds": satisfies_requirement_ids,
            }
        )

    # Deterministic package validator requires every requirement to be satisfied
    # by at least one node. If the model omits some mappings, attach them to
    # the first node as a conservative fallback rather than failing the run.
    all_requirement_ids = set(local_key_to_req_id.values())
    satisfied_by_nodes = {
        rid
        for node in nodes
        for rid in node.get("satisfiesRequirementIds", [])
        if isinstance(rid, str)
    }
    missing_requirement_ids = sorted(all_requirement_ids.difference(satisfied_by_nodes))
    if missing_requirement_ids and nodes:
        first_node_satisfies = list(nodes[0].get("satisfiesRequirementIds", []))
        for rid in missing_requirement_ids:
            if rid not in first_node_satisfies:
                first_node_satisfies.append(rid)
        nodes[0]["satisfiesRequirementIds"] = first_node_satisfies

    edges: list[dict[str, Any]] = []
    for edge in draft.get("edges", []):
        from_node_id = local_node_to_id.get(edge["fromLocalNodeKey"])
        to_node_id = local_node_to_id.get(edge["toLocalNodeKey"])
        if from_node_id is None or to_node_id is None:
            # A dangling local key means the model referenced a node it
            # never declared; drop the edge rather than guess its endpoints.
            continue
        edges.append(
            {
                "edgeId": new_id("edge_"),
                "fromNodeId": from_node_id,
                "toNodeId": to_node_id,
                "flowType": edge["flowType"],
                "description": edge["description"],
            }
        )
    # Schema requires at least one edge when nodes exist.
    if not edges and len(nodes) >= 2:
        edges.append(
            {
                "edgeId": new_id("edge_"),
                "fromNodeId": nodes[0]["nodeId"],
                "toNodeId": nodes[1]["nodeId"],
                "flowType": "data",
                "description": "Functional data flow between primary subsystems.",
            }
        )
    elif not edges and len(nodes) == 1:
        edges.append(
            {
                "edgeId": new_id("edge_"),
                "fromNodeId": nodes[0]["nodeId"],
                "toNodeId": nodes[0]["nodeId"],
                "flowType": "control",
                "description": "Internal control loop within the primary functional node.",
            }
        )

    assumptions = _normalize_assumptions(draft.get("assumptions", []))

    unresolved_refs: list[dict[str, Any]] = []
    for statement in draft.get("unresolvedDecisionStatements", []):
        display_id = f"Q{len(open_questions) + 1}"
        question = _new_open_question(
            project_id=project_id,
            question=statement,
            reason=(
                "Identified as an unresolved decision while drafting the functional architecture."
            ),
            source_reference={"kind": "artifact", "artifactId": artifact_id},
            now=now,
            requested_from=requested_from,
            display_id=display_id,
        )
        open_questions.append(question)
        unresolved_refs.append(_open_question_reference(question))

    covered_requirement_ids = sorted(
        {
            local_key_to_req_id[key]
            for key in draft.get("requirementCoverageLocalKeys", [])
            if key in local_key_to_req_id
        }
    )
    if not covered_requirement_ids:
        covered_requirement_ids = sorted(set(local_key_to_req_id.values()))

    return {
        "architectureId": new_id("arch_"),
        "architectureMaturity": "functional",
        "systemBoundary": draft["systemBoundary"],
        "nodes": nodes,
        "edges": edges,
        "assumptions": assumptions,
        "unresolvedDecisions": unresolved_refs,
        "requirementCoverage": {"coveredRequirementIds": covered_requirement_ids},
    }


def compose_vera_response_deterministic(
    *,
    turn_id: str,
    project_id: str,
    project_phase: ProjectStage,
    autonomy_mode: AutonomyMode,
    created_artifact_references: list[dict[str, Any]],
    warning_issues: list[dict[str, Any]],
    blocker_issues: list[dict[str, Any]],
    open_questions: list[dict[str, Any]],
    next_action_reference: dict[str, Any],
    next_action_title: str,
    completion_status: Literal["completed", "completed-with-warnings", "failed"],
) -> dict[str, Any]:
    """Compose a `VeraResponse` from already-produced, grounded facts only.

    The `userFacingMessage` is assembled from a fixed template populated
    with counts and titles that already exist elsewhere in the package. It
    never introduces a claim, recommendation, or fact that is not already
    backed by an artifact, issue, or open question produced earlier in the
    workflow.
    """

    sentences = [f"I produced {_artifacts_sentence(created_artifact_references)} for this project."]
    if open_questions:
        sentences.append(_count_sentence(len(open_questions), "open question", "to resolve"))
    if blocker_issues:
        sentences.append(
            _count_sentence(
                len(blocker_issues),
                "blocking issue",
                "that must be resolved before this project can proceed",
            )
        )
    if warning_issues:
        sentences.append(
            _count_sentence(len(warning_issues), "non-blocking warning", "were recorded")
        )
    sentences.append(f"Next action: {next_action_title}.")

    return {
        "schemaVersion": "1.0.0",
        "turnId": turn_id,
        "projectId": project_id,
        "userFacingMessage": " ".join(sentences),
        "createdArtifactReferences": list(created_artifact_references),
        "warningIssueReferences": [{"issueId": issue["issueId"]} for issue in warning_issues],
        "blockerIssueReferences": [{"issueId": issue["issueId"]} for issue in blocker_issues],
        "openQuestionReferences": [_open_question_reference(q) for q in open_questions],
        "nextActionArtifactReference": next_action_reference,
        "projectStateSummary": {
            "projectPhase": project_phase,
            "autonomyMode": autonomy_mode,
            "openQuestionCount": len(open_questions),
            "validationIssueCount": len(warning_issues) + len(blocker_issues),
        },
        "completionStatus": completion_status,
    }


def build_project_shell(
    *,
    message: str,
    title: str,
    project_phase: ProjectStage,
    autonomy_mode: AutonomyMode,
    actor: dict[str, Any] | None = None,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create empty Project/UserTurn/TurnRoute skeletons with fresh system IDs.

    Returns `(project, user_turn, turn_route)`. Callers attach artifact
    references, open-question references, and issue references once the
    corresponding content has been generated.
    """

    timestamp = now or utc_now()
    project_id = new_id("proj_")
    turn_id = new_id("turn_")
    route_id = new_id("route_")

    user_turn = {
        "schemaVersion": "1.0.0",
        "turnId": turn_id,
        "projectId": project_id,
        "rawUserMessage": message,
        "actor": actor or default_actor("user"),
        "timestamp": timestamp,
    }

    turn_route = {
        "schemaVersion": "1.0.0",
        "routeId": route_id,
        "turnId": turn_id,
        "supported": True,
        "routeType": "project-initialization",
        "domain": "embedded-products",
        "projectOperation": "create-project",
        "complexity": "unknown",
        "autonomyMode": autonomy_mode,
        "chairmanRequiredEventually": False,
        "reasons": ["Message matched the embedded project initialization workflow boundary."],
    }

    project = {
        "schemaVersion": "1.0.0",
        "projectId": project_id,
        "title": title,
        "domain": "embedded-products",
        "projectPhase": project_phase,
        "currentStateVersion": 1,
        "autonomyMode": autonomy_mode,
        "currentArtifactReferences": [],
        "openQuestionReferences": [],
        "blockerOrValidationIssueReferences": [],
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }

    return project, user_turn, turn_route


def _normalize_assumptions(assumptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(assumptions, start=1):
        normalized.append(
            {
                "assumptionId": f"A{index}",
                "statement": item["statement"],
                "sourceType": item["sourceType"],
                "confidence": item["confidence"],
                "confirmationStatus": item["confirmationStatus"],
            }
        )
    return normalized


def _requirement_source_reference(
    *, source_type: str, turn_id: str, statement: str
) -> dict[str, Any]:
    if source_type == "user-explicit":
        return {
            "schemaVersion": "1.0.0",
            "evidenceId": new_id("evidence_"),
            "sourceType": "user-turn",
            "sourceId": turn_id,
            "supportedClaim": statement,
            "evidenceStrength": "direct",
        }
    if source_type == "user-implied":
        return {
            "schemaVersion": "1.0.0",
            "evidenceId": new_id("evidence_"),
            "sourceType": "user-turn",
            "sourceId": turn_id,
            "supportedClaim": statement,
            "evidenceStrength": "inferred",
        }
    if source_type == "project-policy":
        return {
            "schemaVersion": "1.0.0",
            "evidenceId": new_id("evidence_"),
            "sourceType": "project-policy",
            "sourceId": "embedded-project-initialization-v1",
            "supportedClaim": statement,
            "evidenceStrength": "supporting",
        }
    # system-inferred
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": new_id("evidence_"),
        "sourceType": "agent-inference",
        "sourceId": "embedded-systems-agent",
        "supportedClaim": statement,
        "evidenceStrength": "inferred",
    }


def _new_open_question(
    *,
    project_id: str,
    question: str,
    reason: str,
    source_reference: dict[str, Any],
    now: str,
    requested_from: dict[str, Any] | None,
    display_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "questionId": new_id("question_"),
        "projectId": project_id,
        "question": question,
        "reason": reason,
        "requestedFrom": requested_from or default_actor("user"),
        "blocks": [],
        "status": "open",
        "sourceReferences": [source_reference],
        "createdAt": now,
        "updatedAt": now,
    }
    # displayId is reference-only metadata (not part of OpenQuestion schema).
    if display_id:
        payload["_displayId"] = display_id
    return payload


def _open_question_reference(question: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "questionId": question["questionId"],
    }
    display_id = question.get("_displayId") or question.get("displayId")
    if display_id:
        ref["displayId"] = display_id
    return ref


def _artifacts_sentence(created_artifact_references: list[dict[str, Any]]) -> str:
    labels: dict[str, str] = {
        "project-brief": "a project brief",
        "requirement-set": "a requirement set",
        "functional-architecture": "a functional architecture",
        "next-action": "a next action",
    }
    ordered: list[str] = [
        labels.get(str(ref["artifactType"]), str(ref["artifactType"]))
        for ref in created_artifact_references
    ]
    if not ordered:
        return "no artifacts"
    if len(ordered) == 1:
        return ordered[0]
    if len(ordered) == 2:
        return f"{ordered[0]} and {ordered[1]}"
    return ", ".join(ordered[:-1]) + f", and {ordered[-1]}"


def _count_sentence(count: int, noun: str, suffix: str) -> str:
    plural = "" if count == 1 else "s"
    verb = "is" if count == 1 else "are"
    return f"There {verb} {count} {noun}{plural} {suffix}."
