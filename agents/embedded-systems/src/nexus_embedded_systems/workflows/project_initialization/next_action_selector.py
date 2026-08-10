"""Deterministic Next Action selection for the embedded initialization workflow.

Selection follows a fixed priority order over already-produced issues, open
questions, and missing dimensions. The model is never asked to choose the
Next Action; it may only contribute the drafts that produce issues, open
questions, and missing dimensions upstream. This module computes the
priority order and assembles the final `NextActionContent` deterministically,
minting the `actionId` via `ids.new_id`, matching the backend-owns-IDs rule
followed by the rest of this workflow.
"""

from __future__ import annotations

from typing import Any, Literal

from .ids import new_id

Priority = Literal["critical", "high", "medium", "low"]
ProjectStage = Literal["concept", "prototype-planning"]

_MEASUREMENT_DIMENSION_KEYWORDS: tuple[str, ...] = (
    "performance",
    "measurement",
    "accuracy",
    "precision",
    "latency",
    "throughput",
    "sampling rate",
    "power budget",
)

_INTERFACE_ENV_RESOURCE_DIMENSION_KEYWORDS: tuple[str, ...] = (
    "interface",
    "environment",
    "environmental",
    "resource",
    "connectivity",
    "power supply",
    "enclosure",
    "operating range",
)

_ARCHITECTURE_DIMENSION_KEYWORDS: tuple[str, ...] = (
    "architecture",
    "system boundary",
    "data flow",
    "control flow",
    "subsystem",
)


def select_next_action(
    *,
    issues: list[dict[str, Any]],
    open_questions: list[dict[str, Any]],
    missing_dimensions: list[str],
    project_stage: ProjectStage,
    component_plan_content: dict[str, Any] | None = None,
    electrical_content: dict[str, Any] | None = None,
    physical_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select and construct the single highest-priority Next Action.

    Priority order (highest to lowest):
      1. A blocking validation defect.
      2. An open question whose sourceReferences span more than one
         artifact (a user decision gating multiple downstream artifacts).
      3. A measurement/performance missing dimension.
      4. An interface/environment/resource missing dimension.
      5. An architecture missing dimension.
      6. Component-plan gaps (missing constraints, awaiting approval, no candidates).
      7. Electrical gaps (preferred implementations, unresolved connections/interfaces).
      8. Physical gaps (unresolved placement).
      9. Fallback: the project is ready for later component-selection.
    """

    blocking_issues = [issue for issue in issues if issue.get("blocking") is True]
    if blocking_issues:
        return _blocking_defect_action(blocking_issues)

    multi_artifact_question = _first_multi_artifact_question(open_questions)
    if multi_artifact_question is not None:
        return _user_decision_action(multi_artifact_question)

    measurement_hit = _first_matching_dimension(missing_dimensions, _MEASUREMENT_DIMENSION_KEYWORDS)
    if measurement_hit is not None:
        return _dimension_gap_action(
            dimension=measurement_hit,
            title="Clarify measurement and performance targets",
            description=(
                "The measurement or performance target for "
                f'"{measurement_hit}" is not yet established and is needed '
                "before this project can be planned with confidence."
            ),
            priority="high",
            open_questions=open_questions,
        )

    interface_hit = _first_matching_dimension(
        missing_dimensions, _INTERFACE_ENV_RESOURCE_DIMENSION_KEYWORDS
    )
    if interface_hit is not None:
        return _dimension_gap_action(
            dimension=interface_hit,
            title="Clarify interface, environment, or resource constraints",
            description=(
                f'The "{interface_hit}" dimension is not yet established and '
                "is needed before this project can be planned with "
                "confidence."
            ),
            priority="medium",
            open_questions=open_questions,
        )

    architecture_hit = _first_matching_dimension(
        missing_dimensions, _ARCHITECTURE_DIMENSION_KEYWORDS
    )
    if architecture_hit is not None:
        return _dimension_gap_action(
            dimension=architecture_hit,
            title="Resolve remaining functional architecture gaps",
            description=(
                f'The "{architecture_hit}" dimension of the functional '
                "architecture is not yet resolved."
            ),
            priority="medium",
            open_questions=open_questions,
        )

    component_gap = _component_plan_gap_action(component_plan_content)
    if component_gap is not None:
        return component_gap

    electrical_gap = _electrical_architecture_gap_action(electrical_content)
    if electrical_gap is not None:
        return electrical_gap

    physical_gap = _physical_architecture_gap_action(physical_content)
    if physical_gap is not None:
        return physical_gap

    return _component_selection_ready_action(project_stage)


def _component_plan_gap_action(
    component_plan_content: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(component_plan_content, dict):
        return None
    coverage = component_plan_content.get("coverageSummary") or {}
    roles = component_plan_content.get("componentRoles") or []
    constraints = component_plan_content.get("selectionConstraints") or []
    candidates = component_plan_content.get("candidates") or []
    open_qs = component_plan_content.get("openQuestions") or []

    awaiting = int(coverage.get("rolesAwaitingApproval") or 0)
    without_candidates = int(coverage.get("rolesWithoutCandidates") or 0)

    if awaiting > 0:
        return _build_action(
            title="Approve pending component selections",
            description=(
                f"{awaiting} component role(s) have provisional selections awaiting "
                "user approval before procurement planning."
            ),
            rationale=(
                "Selection approval is the highest-value component-plan gate once "
                "candidates have been proposed."
            ),
            priority="high",
            prerequisites=[],
            blocks=[],
            completion_condition_type="requirements-confirmed",
            completion_criteria="User approves or rejects pending component selections.",
            source_issue_ids=[],
            source_question_ids=[q["questionId"] for q in open_qs if q.get("questionId")][:3],
        )

    if roles and not constraints:
        return _build_action(
            title="Confirm component selection constraints",
            description=(
                "Component roles are defined but selection constraints (range, "
                "accuracy, budget, interface) are still missing."
            ),
            rationale=(
                "Constraints must be confirmed before candidates can be grounded "
                "or compared fairly."
            ),
            priority="high",
            prerequisites=[],
            blocks=[],
            completion_condition_type="unknowns-resolved",
            completion_criteria="User confirms key selection constraints for component roles.",
            source_issue_ids=[],
            source_question_ids=[],
        )

    if without_candidates > 0 or (roles and not candidates):
        return _build_action(
            title="Propose component candidates for uncovered roles",
            description=(
                f"{without_candidates or len(roles)} component role(s) still lack "
                "provisional part candidates."
            ),
            rationale=(
                "Roles without candidates block comparison-workspace planning and "
                "selection approval."
            ),
            priority="medium",
            prerequisites=[],
            blocks=[],
            completion_condition_type="requirements-confirmed",
            completion_criteria="At least one provisional candidate exists for each role.",
            source_issue_ids=[],
            source_question_ids=[],
        )

    if open_qs:
        qid = open_qs[0].get("questionId")
        return _build_action(
            title="Answer open component planning questions",
            description=str(open_qs[0].get("summary") or "Resolve a component-plan open question."),
            rationale="Open component questions block grounded selection.",
            priority="medium",
            prerequisites=[],
            blocks=[],
            completion_condition_type="unknowns-resolved",
            completion_criteria="Component-plan open questions are answered.",
            source_issue_ids=[],
            source_question_ids=[qid] if isinstance(qid, str) else [],
        )

    return None


def _electrical_architecture_gap_action(
    electrical_content: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(electrical_content, dict):
        return None
    coverage = electrical_content.get("coverageSummary") or {}
    preferred = int(coverage.get("preferredImplementationCount") or 0)
    unresolved_impl = int(coverage.get("unresolvedImplementationCount") or 0)
    unresolved_conn = int(coverage.get("unresolvedConnectionCount") or 0)

    nodes = electrical_content.get("nodes") or []
    preferred_nodes = [
        n
        for n in nodes
        if isinstance(n, dict)
        and n.get("implementationStatus") in {"preferred", "provisional"}
        and n.get("selectionState") == "preferred"
    ]
    if preferred > 0 or preferred_nodes:
        count = preferred or len(preferred_nodes)
        return _build_action(
            title="Approve preferred electrical implementations",
            description=(
                f"{count} electrical implementation(s) are preferred/provisional and "
                "await user approval before treating the Electrical Architecture as settled."
            ),
            rationale=(
                "Preferred implementations gate grounded electrical connectivity and "
                "downstream physical placement."
            ),
            priority="high",
            prerequisites=[],
            blocks=[],
            completion_condition_type="requirements-confirmed",
            completion_criteria=("User approves or rejects preferred electrical implementations."),
            source_issue_ids=[],
            source_question_ids=[],
        )

    unknown_ifaces = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for iface in node.get("interfaces") or []:
            if not isinstance(iface, dict):
                continue
            if iface.get("status") in {"unknown", "unresolved", "needs-resolution"}:
                unknown_ifaces += 1

    if unresolved_conn > 0 or unknown_ifaces > 0 or unresolved_impl > 0:
        return _build_action(
            title="Resolve electrical connections and interfaces",
            description=(
                "Electrical Architecture still has unresolved implementations, "
                "unknown interfaces, or connections that need resolution."
            ),
            rationale=(
                "Unresolved electrical links block trustworthy Physical Architecture "
                "placement and later netlist work."
            ),
            priority="medium",
            prerequisites=[],
            blocks=[],
            completion_condition_type="unknowns-resolved",
            completion_criteria=(
                "Unresolved electrical implementations, interfaces, and connections "
                "are clarified or accepted as provisional."
            ),
            source_issue_ids=[],
            source_question_ids=[],
        )

    return None


def _physical_architecture_gap_action(
    physical_content: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(physical_content, dict):
        return None
    coverage = physical_content.get("coverageSummary") or {}
    unresolved_placement = int(coverage.get("unresolvedPlacementCount") or 0)
    if unresolved_placement <= 0:
        return None
    return _build_action(
        title="Resolve unresolved physical placements",
        description=(
            f"{unresolved_placement} physical entit(y/ies) still lack a resolved "
            "qualitative placement."
        ),
        rationale=(
            "Unresolved placement prevents treating Physical Architecture as ready "
            "for enclosure and assembly planning."
        ),
        priority="medium",
        prerequisites=[],
        blocks=[],
        completion_condition_type="unknowns-resolved",
        completion_criteria="User clarifies or accepts provisional physical placements.",
        source_issue_ids=[],
        source_question_ids=[],
    )


def _blocking_defect_action(blocking_issues: list[dict[str, Any]]) -> dict[str, Any]:
    issue_ids = [issue["issueId"] for issue in blocking_issues if "issueId" in issue]
    codes = sorted({issue["code"] for issue in blocking_issues if issue.get("code")})
    codes_text = ", ".join(codes) if codes else "an unspecified blocking defect"
    return _build_action(
        title="Resolve blocking validation defect",
        description=(
            "One or more blocking validation issues must be resolved before "
            f"this project can proceed ({codes_text})."
        ),
        rationale=(
            "A blocking validation defect prevents any downstream artifact "
            "from being trusted, so it takes priority over every other gap."
        ),
        priority="critical",
        prerequisites=[],
        blocks=issue_ids,
        completion_condition_type="validation-issues-cleared",
        completion_criteria="All blocking validation issues on this project are resolved.",
        source_issue_ids=issue_ids,
        source_question_ids=[],
    )


def _user_decision_action(question: dict[str, Any]) -> dict[str, Any]:
    question_id = question["questionId"]
    blocked_issue_ids = list(question.get("blocks") or [])
    return _build_action(
        title="Resolve decision blocking multiple artifacts",
        description=(
            "A single open question is blocking more than one artifact: "
            f'"{question.get("question", "")}"'
        ),
        rationale=(
            "This decision gates multiple downstream artifacts at once, so "
            "resolving it unblocks more of the project than any single-"
            "artifact gap would."
        ),
        priority="high",
        prerequisites=[_question_reference(question)],
        blocks=blocked_issue_ids,
        completion_condition_type="unknowns-resolved",
        completion_criteria=f"Open question {question_id} is answered and resolved.",
        source_issue_ids=blocked_issue_ids,
        source_question_ids=[question_id],
    )


def _dimension_gap_action(
    *,
    dimension: str,
    title: str,
    description: str,
    priority: Priority,
    open_questions: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant_questions = [
        question
        for question in open_questions
        if question.get("status") == "open" and dimension in question.get("question", "").casefold()
    ]
    prerequisites = [_question_reference(question) for question in relevant_questions]
    source_question_ids = [question["questionId"] for question in relevant_questions]
    return _build_action(
        title=title,
        description=description,
        rationale=(
            f'The "{dimension}" gap was reported as a missing dimension and '
            "must be resolved before downstream artifacts can rely on it."
        ),
        priority=priority,
        prerequisites=prerequisites,
        blocks=[],
        completion_condition_type="unknowns-resolved",
        completion_criteria=f'The "{dimension}" dimension is confirmed with the user.',
        source_issue_ids=[],
        source_question_ids=source_question_ids,
    )


def _component_selection_ready_action(project_stage: ProjectStage) -> dict[str, Any]:
    return _build_action(
        title="Proceed to component-selection scoping",
        description=(
            "No blocking issues, multi-artifact decisions, or missing "
            "dimensions remain from this workflow. The project is ready for "
            "a later, dedicated component-selection workflow."
        ),
        rationale=(
            f"At the {project_stage} stage, with requirements and "
            "architecture free of known gaps, the highest-value next step "
            "is scoping component selection rather than revisiting this "
            "workflow's outputs."
        ),
        priority="low",
        prerequisites=[],
        blocks=[],
        completion_condition_type="requirements-confirmed",
        completion_criteria="All must/should requirements reach confirmed status.",
        source_issue_ids=[],
        source_question_ids=[],
    )


def _build_action(
    *,
    title: str,
    description: str,
    rationale: str,
    priority: Priority,
    prerequisites: list[dict[str, Any]],
    blocks: list[str],
    completion_condition_type: str,
    completion_criteria: str,
    source_issue_ids: list[str],
    source_question_ids: list[str],
) -> dict[str, Any]:
    return {
        "actionId": new_id("act_"),
        "title": title,
        "description": description,
        "rationale": rationale,
        "owner": "vera",
        "priority": priority,
        "prerequisites": prerequisites,
        "blocks": [{"issueId": issue_id} for issue_id in blocks],
        "completionCondition": {
            "conditionType": completion_condition_type,
            "completionCriteria": completion_criteria,
        },
        "sourceIssueIds": source_issue_ids,
        "sourceQuestionIds": source_question_ids,
    }


def _question_reference(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "questionId": question["questionId"],
    }


def _first_multi_artifact_question(open_questions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for question in open_questions:
        if question.get("status") != "open":
            continue
        artifact_ids = {
            ref["artifactId"]
            for ref in question.get("sourceReferences") or []
            if ref.get("kind") == "artifact" and ref.get("artifactId")
        }
        if len(artifact_ids) > 1:
            return question
    return None


def _first_matching_dimension(
    missing_dimensions: list[str], keywords: tuple[str, ...]
) -> str | None:
    for dimension in missing_dimensions:
        normalized = dimension.casefold()
        if any(keyword in normalized for keyword in keywords):
            return dimension
    return None
