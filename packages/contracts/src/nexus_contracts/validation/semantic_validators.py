from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticValidationError:
    code: str
    message: str
    path: str | None = None
    blocking: bool = True


_FORBIDDEN_VERA_REASONING_KEYS = {
    "hiddenReasoning",
    "chainOfThought",
    "chain_of_thought",
    "hiddenReasoningText",
    "internalReasoning",
}


def find_hidden_reasoning_fields(value: Any) -> list[str]:
    """
    Deterministically find forbidden reasoning-related keys inside a payload.

    This is stricter than JSON Schema because some hidden reasoning fields can be
    accidentally nested under allowed objects.
    """

    hits: list[str] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                next_path = f"{path}.{k}" if path else k
                k_lower = k.lower()
                if k in _FORBIDDEN_VERA_REASONING_KEYS or (
                    "reasoning" in k_lower and k_lower not in {"reason"}
                ):
                    hits.append(next_path)
                _walk(v, next_path)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")

    _walk(value, "")
    # Deterministic ordering for stable test assertions.
    return sorted(set(hits))


_COMPONENT_SPECIFIC_PATTERNS: list[str] = [
    # MCU-like identifiers
    r"\bESP32[A-Z0-9\-]*\b",
    r"\bSTM32[A-Z0-9\-]*\b",
    r"\bATMEGA\d+\b",
    # Sensor / chip model-like identifiers
    r"\bBME\d+\b",
    r"\bBMI\d+\b",
    r"\bBNO\d+\b",
    r"\bMPU\d+\b",
    r"\bnRF\d+\b",
    # Example in prompt: VL53L1X
    r"\bVL\d+L\d+X\b",
    # Board name example in prompt
    r"\bRaspberry\s+Pi\s+Pico\b",
]

_TECHNOLOGY_LEVEL_PHRASES: list[str] = [
    "inertial sensing",
    "radio communication",
    "analog signal acquisition",
    "digital communication interface",
    "local nonvolatile storage",
]


def _component_specific_hits(text: str) -> list[str]:
    import re

    if not isinstance(text, str):
        return []

    hits: list[str] = []
    for pattern in _COMPONENT_SPECIFIC_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def _technology_level_hits(text: str) -> list[str]:
    if not isinstance(text, str):
        return []

    lower = text.lower()
    return [phrase for phrase in _TECHNOLOGY_LEVEL_PHRASES if phrase in lower]


def semantic_validate_bundle(bundle: dict[str, Any]) -> list[SemanticValidationError]:
    """
    Semantic validation across a *complete project package* (fixture directory).

    This intentionally stays conservative and deterministic:
    - component-specific language is treated as blocking at functional maturity
    - technology-level language is treated as non-blocking warnings
    - `user-explicit` provenance is validated against the referenced UserTurn
      using conservative token overlap and numeric/unit matching.
    """

    errors: list[SemanticValidationError] = []

    project = bundle.get("project")
    user_turn = bundle.get("user_turn") or {}
    turn_route = bundle.get("turn_route") or {}
    workflow_run = bundle.get("workflow_run") or {}
    validation_issues: list[dict[str, Any]] = bundle.get("validation_issues", []) or []
    open_questions: list[dict[str, Any]] = bundle.get("open_questions", []) or []

    requirement_set = bundle.get("requirement_set_content")
    functional_arch = bundle.get("functional_architecture_content")
    next_action_content = bundle.get("next_action_content")
    vera_response = bundle.get("vera_response")

    artifact_envelopes: list[dict[str, Any]] = bundle.get("artifact_envelopes", []) or []

    user_turn_id = user_turn.get("turnId") if isinstance(user_turn, dict) else None
    user_turn_message = user_turn.get("rawUserMessage") if isinstance(user_turn, dict) else None

    def _requirement_ids_from_requirement_set(req_set: Any) -> set[str]:
        if not isinstance(req_set, dict):
            return set()
        ids: set[str] = set()
        for r in req_set.get("requirements", []) or []:
            if isinstance(r, dict) and isinstance(r.get("requirementId"), str):
                ids.add(r["requirementId"])
        return ids

    # --- Artifact envelope status dimensions stay separate ---
    for artifact in artifact_envelopes:
        if isinstance(artifact, dict) and "status" in artifact:
            errors.append(
                SemanticValidationError(
                    code="ARTIFACT_STATUS_DIMENSIONS_COMBINED",
                    message="Found forbidden combined artifact status field 'status'.",
                    path="artifact.status",
                    blocking=True,
                )
            )

        # Defensive: ensure the schemaVersion and artifactVersion are separate types.
        if isinstance(artifact, dict):
            schema_version = artifact.get("schemaVersion")
            artifact_version = artifact.get("artifactVersion")
            if schema_version is not None and not isinstance(schema_version, str):
                errors.append(
                    SemanticValidationError(
                        code="ARTIFACT_SCHEMA_VERSION_WRONG_TYPE",
                        message="artifact.schemaVersion must be a string.",
                        path="artifact.schemaVersion",
                        blocking=True,
                    )
                )
            if artifact_version is not None and not isinstance(artifact_version, int):
                errors.append(
                    SemanticValidationError(
                        code="ARTIFACT_VERSION_WRONG_TYPE",
                        message="artifact.artifactVersion must be an integer.",
                        path="artifact.artifactVersion",
                        blocking=True,
                    )
                )

    artifact_by_id: dict[str, dict[str, Any]] = {
        a["artifactId"]: a
        for a in artifact_envelopes
        if isinstance(a, dict) and isinstance(a.get("artifactId"), str)
    }
    issue_by_id: dict[str, dict[str, Any]] = {
        i["issueId"]: i
        for i in validation_issues
        if isinstance(i, dict) and isinstance(i.get("issueId"), str)
    }
    question_by_id: dict[str, dict[str, Any]] = {
        q["questionId"]: q
        for q in open_questions
        if isinstance(q, dict) and isinstance(q.get("questionId"), str)
    }

    # --- Cross-object: projectId/turnId/workflowRunId consistency ---
    project_id = project.get("projectId") if isinstance(project, dict) else None
    workflow_run_id = workflow_run.get("workflowRunId") if isinstance(workflow_run, dict) else None
    turn_id = user_turn.get("turnId") if isinstance(user_turn, dict) else None

    def _record_project_mismatch(path: str, other_project_id: Any) -> None:
        if project_id is None:
            return
        if other_project_id != project_id:
            errors.append(
                SemanticValidationError(
                    code="PROJECT_ID_MISMATCH",
                    message="projectId mismatch across project package objects.",
                    path=path,
                    blocking=True,
                )
            )

    if isinstance(user_turn, dict) and isinstance(user_turn.get("projectId"), str):
        _record_project_mismatch("user_turn.projectId", user_turn.get("projectId"))
    if isinstance(workflow_run, dict) and isinstance(workflow_run.get("projectId"), str):
        _record_project_mismatch("workflow_run.projectId", workflow_run.get("projectId"))
    if isinstance(vera_response, dict) and isinstance(vera_response.get("projectId"), str):
        _record_project_mismatch("vera_response.projectId", vera_response.get("projectId"))

    for art_id, artifact in artifact_by_id.items():
        if isinstance(artifact.get("projectId"), str):
            _record_project_mismatch(f"artifact[{art_id}].projectId", artifact.get("projectId"))
    for issue_id, issue in issue_by_id.items():
        if isinstance(issue.get("projectId"), str):
            _record_project_mismatch(
                f"validation_issues[{issue_id}].projectId", issue.get("projectId")
            )
    for q_id, q in question_by_id.items():
        if isinstance(q.get("projectId"), str):
            _record_project_mismatch(f"open_questions[{q_id}].projectId", q.get("projectId"))

    def _record_turn_mismatch(path: str, other_turn_id: Any) -> None:
        if turn_id is None:
            return
        if other_turn_id != turn_id:
            errors.append(
                SemanticValidationError(
                    code="TURN_ID_MISMATCH",
                    message="turnId mismatch across project package objects.",
                    path=path,
                    blocking=True,
                )
            )

    if isinstance(turn_route, dict) and isinstance(turn_route.get("turnId"), str):
        _record_turn_mismatch("turn_route.turnId", turn_route.get("turnId"))
    if isinstance(workflow_run, dict) and isinstance(workflow_run.get("turnId"), str):
        _record_turn_mismatch("workflow_run.turnId", workflow_run.get("turnId"))
    if isinstance(vera_response, dict) and isinstance(vera_response.get("turnId"), str):
        _record_turn_mismatch("vera_response.turnId", vera_response.get("turnId"))

    for art_id, artifact in artifact_by_id.items():
        if isinstance(artifact.get("sourceTurnId"), str):
            _record_turn_mismatch(f"artifact[{art_id}].sourceTurnId", artifact.get("sourceTurnId"))

    def _record_workflow_run_mismatch(path: str, other_workflow_run_id: Any) -> None:
        if workflow_run_id is None:
            return
        if other_workflow_run_id != workflow_run_id:
            errors.append(
                SemanticValidationError(
                    code="WORKFLOW_RUN_ID_MISMATCH",
                    message="workflowRunId mismatch across project package objects.",
                    path=path,
                    blocking=True,
                )
            )

    if isinstance(vera_response, dict) and isinstance(
        vera_response.get("createdArtifactReferences"), list
    ):
        for ref in vera_response.get("createdArtifactReferences") or []:
            # artifact reference objects validate via schema elsewhere; keep deterministic here.
            if isinstance(ref, dict) and isinstance(ref.get("artifactId"), str):
                pass

    if isinstance(workflow_run, dict) and isinstance(workflow_run.get("workflowRunId"), str):
        _record_workflow_run_mismatch(
            "workflow_run.workflowRunId", workflow_run.get("workflowRunId")
        )

    for art_id, artifact in artifact_by_id.items():
        if isinstance(artifact.get("workflowRunId"), str):
            _record_workflow_run_mismatch(
                f"artifact[{art_id}].workflowRunId", artifact.get("workflowRunId")
            )

    # --- Requirement semantic invariants ---
    if isinstance(requirement_set, dict):
        requirements: list[dict[str, Any]] = requirement_set.get("requirements", []) or []

        display_ids: list[str] = []
        for req in requirements:
            display_id = req.get("displayId")
            if isinstance(display_id, str):
                display_ids.append(display_id)
        counts = Counter(display_ids)
        duplicates = sorted([d for d, c in counts.items() if c > 1])
        if duplicates:
            errors.append(
                SemanticValidationError(
                    code="REQ_DUPLICATE_DISPLAY_ID",
                    message=f"Duplicate requirement displayId values detected: {duplicates}.",
                    path="requirementSet.requirements.displayId",
                    blocking=True,
                )
            )

        # Provenance: validate `user-explicit` against the referenced UserTurn.
        stopwords = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "but",
            "by",
            "for",
            "from",
            "in",
            "into",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "their",
            "then",
            "there",
            "to",
            "with",
            "will",
            "would",
            "should",
            "can",
            "could",
            "may",
            "might",
            "i",
            "you",
            "we",
            "they",
            "them",
            "your",
        }

        import re

        def _tokenize(text: str) -> set[str]:
            words = re.findall(r"[a-z0-9]+", text.lower())
            return {w for w in words if w not in stopwords and len(w) >= 3}

        unit_map = {
            "h": "hour",
            "hour": "hour",
            "hours": "hour",
            "hr": "hour",
            "hrs": "hour",
            "m": "minute",
            "min": "minute",
            "mins": "minute",
            "minute": "minute",
            "minutes": "minute",
            "s": "second",
            "sec": "second",
            "secs": "second",
            "second": "second",
            "seconds": "second",
        }

        num_unit_re = re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(hours?|hour|h|hr|mins?|minutes?|m|seconds?|second|sec|s)\b",
            flags=re.IGNORECASE,
        )

        def _extract_num_units(text: str) -> set[tuple[str, str]]:
            claims: set[tuple[str, str]] = set()
            for match in num_unit_re.finditer(text):
                num = match.group(1)
                unit_raw = match.group(2).lower()
                unit_norm = unit_map.get(unit_raw)
                if unit_norm:
                    claims.add((num, unit_norm))
            return claims

        for req in requirements:
            source_type = req.get("sourceType")
            source_reference = req.get("sourceReference") or {}
            evidence_strength = source_reference.get("evidenceStrength")
            evidence_source_type = source_reference.get("sourceType")
            evidence_source_id = source_reference.get("sourceId")

            if source_type != "user-explicit":
                continue

            # Evidence must be direct user evidence for this slice.
            if evidence_strength == "inferred":
                errors.append(
                    SemanticValidationError(
                        code="REQ_SOURCE_INFERRED_MISLABELED",
                        message=(
                            "Requirement marked user-explicit is backed by inferred "
                            "evidenceStrength."
                        ),
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )
                continue

            if evidence_strength != "direct":
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_EVIDENCE_NOT_DIRECT",
                        message="user-explicit requirements require direct user evidence.",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )
                continue

            if evidence_source_type != "user-turn":
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_REFERENCE_NOT_USER_TURN",
                        message="user-explicit requirements must reference user-turn evidence.",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )
                continue

            if not isinstance(evidence_source_id, str) or not user_turn_id:
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_REFERENCE_MISSING_TURN",
                        message="user-explicit requirements must reference a UserTurn by turnId.",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )
                continue

            if evidence_source_id != user_turn_id:
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_REFERENCE_WRONG_TURN",
                        message="user-explicit requirements reference a different package turnId.",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )
                continue

            if not isinstance(user_turn_message, str) or not user_turn_message:
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_MISSING_USER_TURN_TEXT",
                        message="Cannot validate provenance without UserTurn.rawUserMessage.",
                        path="user_turn.rawUserMessage",
                        blocking=True,
                    )
                )
                continue

            # Numeric/unit matching (when the requirement contains explicit numeric claims).
            req_num_units = _extract_num_units(str(req.get("statement") or ""))
            if req_num_units:
                user_num_units = _extract_num_units(user_turn_message)
                if not req_num_units.issubset(user_num_units):
                    errors.append(
                        SemanticValidationError(
                            code="REQ_USER_EXPLICIT_NUMERIC_UNSUPPORTED",
                            message="user-explicit numeric claims are not supported by UserTurn.",
                            path=f"requirementSet.requirements[{req.get('requirementId')}].statement",
                            blocking=True,
                        )
                    )
                    continue

            # Conservative lexical overlap check.
            req_statement = str(req.get("statement") or "")
            req_tokens = _tokenize(req_statement)
            user_tokens = _tokenize(user_turn_message)
            if not req_tokens:
                continue

            overlap = req_tokens.intersection(user_tokens)
            overlap_count = len(overlap)
            overlap_ratio = overlap_count / max(len(req_tokens), 1)

            if overlap_count >= 3 or overlap_ratio >= 0.25:
                continue

            if overlap_count >= 1:
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT",
                        message="user-explicit provenance is weak/ambiguous (low text overlap).",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=False,
                    )
                )
            else:
                errors.append(
                    SemanticValidationError(
                        code="REQ_USER_EXPLICIT_UNSUPPORTED",
                        message="user-explicit provenance not supported by referenced UserTurn.",
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                        blocking=True,
                    )
                )

        # --- Source-reference integrity (requirements -> referenced objects) ---
        # Evidence references should point to actual objects within the same
        # package when they are represented by artifact/turn IDs.
        if turn_id or artifact_by_id:
            for req in requirements:
                source_reference = req.get("sourceReference") or {}
                evidence_source_type = source_reference.get("sourceType")
                evidence_source_id = source_reference.get("sourceId")

                if (
                    evidence_source_type == "user-turn"
                    and turn_id is not None
                    and isinstance(evidence_source_id, str)
                    and evidence_source_id != turn_id
                ):
                    errors.append(
                        SemanticValidationError(
                            code="REQ_SOURCE_REFERENCE_USER_TURN_MISMATCH",
                            message="user-turn evidence sourceId does not match package UserTurn.",
                            path="requirementSet.requirements.sourceReference.sourceId",
                            blocking=True,
                        )
                    )

                if (
                    isinstance(evidence_source_id, str)
                    and evidence_source_id.startswith("art_")
                    and evidence_source_id not in artifact_by_id
                ):
                    errors.append(
                        SemanticValidationError(
                            code="REQ_SOURCE_REFERENCE_UNKNOWN_ARTIFACT",
                            message="Requirement evidence references unknown artifactId.",
                            path="requirementSet.requirements.sourceReference.sourceId",
                            blocking=True,
                        )
                    )

                if (
                    isinstance(evidence_source_id, str)
                    and evidence_source_id.startswith("turn_")
                    and turn_id is not None
                    and evidence_source_id != turn_id
                ):
                    errors.append(
                        SemanticValidationError(
                            code="REQ_SOURCE_REFERENCE_UNKNOWN_TURN",
                            message="Requirement evidence references unknown turnId.",
                            path="requirementSet.requirements.sourceReference.sourceId",
                            blocking=True,
                        )
                    )

    # --- Architecture semantic invariants ---
    if isinstance(functional_arch, dict):
        nodes = functional_arch.get("nodes", []) or []
        node_ids = {
            n.get("nodeId")
            for n in nodes
            if isinstance(n, dict) and isinstance(n.get("nodeId"), str)
        }

        edges = functional_arch.get("edges", []) or []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            from_id = edge.get("fromNodeId")
            to_id = edge.get("toNodeId")
            if isinstance(from_id, str) and from_id not in node_ids:
                errors.append(
                    SemanticValidationError(
                        code="ARCH_EDGE_REFERENCES_MISSING_NODE",
                        message=f"Edge fromNodeId '{from_id}' does not exist in nodes.",
                        path="functionalArchitecture.edges",
                        blocking=True,
                    )
                )
            if isinstance(to_id, str) and to_id not in node_ids:
                errors.append(
                    SemanticValidationError(
                        code="ARCH_EDGE_REFERENCES_MISSING_NODE",
                        message=f"Edge toNodeId '{to_id}' does not exist in nodes.",
                        path="functionalArchitecture.edges",
                        blocking=True,
                    )
                )

        req_ids = (
            _requirement_ids_from_requirement_set(requirement_set)
            if isinstance(requirement_set, dict)
            else set()
        )

        # Component/part identifiers must not appear at functional maturity.
        if functional_arch.get("architectureMaturity") == "functional":
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = node.get("nodeId")
                node_name = node.get("name") or ""
                resp_list = node.get("responsibilities") or []
                resp_text = " ".join([r for r in resp_list if isinstance(r, str)])

                # High-confidence component-specific language => blocking error.
                name_hits = _component_specific_hits(str(node_name))
                resp_hits = _component_specific_hits(resp_text)
                if name_hits or resp_hits:
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_SPECIFIC_ARCHITECTURE",
                            message="Concrete component identifier in functional architecture.",
                            path=f"functionalArchitecture.nodes[{node_id}]",
                            blocking=True,
                        )
                    )
                    continue

                # Technology-level language => non-blocking warning.
                tech_name_hits = _technology_level_hits(str(node_name))
                tech_resp_hits = _technology_level_hits(resp_text)
                if tech_name_hits or tech_resp_hits:
                    errors.append(
                        SemanticValidationError(
                            code="TECHNOLOGY_LEVEL_TERM_IN_FUNCTIONAL_ARCHITECTURE",
                            message="technology-level terms detected in functional architecture.",
                            path=f"functionalArchitecture.nodes[{node_id}]",
                            blocking=False,
                        )
                    )

                # Node-level traceability: node.satisfiesRequirementIds must exist.
                satisfies = node.get("satisfiesRequirementIds") or []
                for rid in satisfies:
                    if isinstance(rid, str) and req_ids and rid not in req_ids:
                        errors.append(
                            SemanticValidationError(
                                code="ARCH_NODE_SATISFIES_MISSING_REQUIREMENTS",
                                message="satisfiesRequirementIds references unknown requirementId.",
                                path=f"functionalArchitecture.nodes[{node_id}].satisfiesRequirementIds",
                                blocking=True,
                            )
                        )

    # --- Cross-object semantic invariants (Requirement coverage) ---
    if isinstance(functional_arch, dict) and isinstance(requirement_set, dict):
        req_ids = _requirement_ids_from_requirement_set(requirement_set)
        covered = (functional_arch.get("requirementCoverage", {}) or {}).get(
            "coveredRequirementIds", []
        ) or []
        missing = [rid for rid in covered if isinstance(rid, str) and rid not in req_ids]
        if missing:
            errors.append(
                SemanticValidationError(
                    code="ARCH_REQUIREMENT_COVERAGE_MISSING_REQUIREMENTS",
                    message="requirementCoverage references missing requirementIds.",
                    path="functionalArchitecture.requirementCoverage.coveredRequirementIds",
                    blocking=True,
                )
            )

    # --- Next Action semantic invariants ---
    if isinstance(next_action_content, dict):
        issue_ids = {
            i.get("issueId")
            for i in validation_issues
            if isinstance(i, dict) and isinstance(i.get("issueId"), str)
        }
        question_ids = {
            q.get("questionId")
            for q in open_questions
            if isinstance(q, dict) and isinstance(q.get("questionId"), str)
        }

        blocks = next_action_content.get("blocks") or []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            issue_block_id = b.get("issueId")
            if isinstance(issue_block_id, str) and issue_block_id not in issue_ids:
                errors.append(
                    SemanticValidationError(
                        code="NEXT_ACTION_BLOCKS_UNKNOWN_ISSUE",
                        message="Next Action blocks references an unknown issueId.",
                        path="nextAction.blocks",
                        blocking=True,
                    )
                )
            if isinstance(issue_block_id, str) and issue_block_id in issue_by_id:
                issue_obj = issue_by_id.get(issue_block_id) or {}
                if isinstance(issue_obj.get("blocking"), bool) and not issue_obj["blocking"]:
                    errors.append(
                        SemanticValidationError(
                            code="NEXT_ACTION_BLOCKS_NON_BLOCKING_ISSUE",
                            message="Next Action blocks references a non-blocking issue.",
                            path="nextAction.blocks",
                            blocking=True,
                        )
                    )

        prereq_refs = next_action_content.get("prerequisites") or []
        for p in prereq_refs:
            if not isinstance(p, dict):
                continue
            qid = p.get("questionId")
            if isinstance(qid, str) and qid not in question_ids:
                errors.append(
                    SemanticValidationError(
                        code="NEXT_ACTION_PREREQUISITES_UNKNOWN_QUESTION",
                        message="Next Action prerequisites reference an unknown questionId.",
                        path="nextAction.prerequisites",
                        blocking=True,
                    )
                )

    # --- Vera response semantic invariants ---
    if isinstance(vera_response, dict):
        hits = find_hidden_reasoning_fields(vera_response)
        if hits:
            errors.append(
                SemanticValidationError(
                    code="VERA_HIDDEN_REASONING_FORBIDDEN",
                    message=f"Hidden reasoning fields are forbidden: {hits}.",
                    path="veraResponse",
                    blocking=True,
                )
            )

        # Deterministic reference integrity checks for this slice.
        next_action_ref = vera_response.get("nextActionArtifactReference") or {}
        if isinstance(next_action_ref, dict):
            next_action_artifact_id = next_action_ref.get("artifactId")
            if (
                isinstance(next_action_artifact_id, str)
                and next_action_artifact_id not in artifact_by_id
            ):
                errors.append(
                    SemanticValidationError(
                        code="VERA_NEXT_ACTION_ARTIFACT_UNKNOWN",
                        message="nextActionArtifactReference artifactId not in package.",
                        path="veraResponse.nextActionArtifactReference.artifactId",
                        blocking=True,
                    )
                )

            next_action_artifact = (
                artifact_by_id.get(next_action_artifact_id)
                if isinstance(next_action_artifact_id, str)
                else None
            )
            if (
                isinstance(next_action_artifact, dict)
                and next_action_artifact.get("artifactType") != "next-action"
            ):
                errors.append(
                    SemanticValidationError(
                        code="VERA_NEXT_ACTION_ARTIFACT_WRONG_TYPE",
                        message="Vera nextActionArtifactReference points to wrong artifact type.",
                        path="veraResponse.nextActionArtifactReference.artifactType",
                        blocking=True,
                    )
                )

        created_refs = vera_response.get("createdArtifactReferences") or []
        if isinstance(created_refs, list):
            for ref in created_refs:
                if not isinstance(ref, dict):
                    continue
                artifact_id = ref.get("artifactId")
                if isinstance(artifact_id, str) and artifact_id not in artifact_by_id:
                    errors.append(
                        SemanticValidationError(
                            code="VERA_CREATED_ARTIFACT_REFERENCE_UNKNOWN",
                            message="createdArtifactReferences artifactId not in package.",
                            path="veraResponse.createdArtifactReferences",
                            blocking=True,
                        )
                    )

        for issue_list_name in ["warningIssueReferences", "blockerIssueReferences"]:
            refs = vera_response.get(issue_list_name) or []
            if isinstance(refs, list):
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    issue_ref_id = ref.get("issueId")
                    if isinstance(issue_ref_id, str) and issue_ref_id not in issue_by_id:
                        errors.append(
                            SemanticValidationError(
                                code="VERA_ISSUE_REFERENCE_UNKNOWN",
                                message="issueId not in package.",
                                path=f"veraResponse.{issue_list_name}",
                                blocking=True,
                            )
                        )

        open_question_refs = vera_response.get("openQuestionReferences") or []
        if isinstance(open_question_refs, list):
            for ref in open_question_refs:
                if not isinstance(ref, dict):
                    continue
                qid = ref.get("questionId")
                if isinstance(qid, str) and qid not in question_by_id:
                    errors.append(
                        SemanticValidationError(
                            code="VERA_OPEN_QUESTION_REFERENCE_UNKNOWN",
                            message="Vera openQuestion reference references an unknown questionId.",
                            path="veraResponse.openQuestionReferences",
                            blocking=True,
                        )
                    )

    # --- Component Plan semantic rules ---
    architecture_node_ids: set[str] | None = None
    if isinstance(functional_arch, dict):
        nodes = functional_arch.get("nodes") or []
        if isinstance(nodes, list):
            architecture_node_ids = {
                node_id
                for node in nodes
                if isinstance(node, dict)
                for node_id in [node.get("nodeId")]
                if isinstance(node_id, str)
            }

    requirement_ids: set[str] | None = None
    if isinstance(requirement_set, dict):
        requirements = requirement_set.get("requirements") or []
        if isinstance(requirements, list):
            requirement_ids = {
                requirement_id
                for req in requirements
                if isinstance(req, dict)
                for requirement_id in [req.get("requirementId")]
                if isinstance(requirement_id, str)
            }

    component_plan_content = bundle.get("component_plan_content")
    for artifact in artifact_envelopes:
        if not isinstance(artifact, dict) or artifact.get("artifactType") != "component-plan":
            continue
        content = artifact.get("content")
        if not isinstance(content, dict):
            continue
        if component_plan_content is None:
            component_plan_content = content
        errors.extend(
            _validate_component_plan_content(
                content,
                architecture_node_ids=architecture_node_ids,
                requirement_ids=requirement_ids,
            )
        )

    if isinstance(component_plan_content, dict) and not any(
        isinstance(a, dict) and a.get("artifactType") == "component-plan"
        for a in artifact_envelopes
    ):
        errors.extend(
            _validate_component_plan_content(
                component_plan_content,
                architecture_node_ids=architecture_node_ids,
                requirement_ids=requirement_ids,
            )
        )

    return errors


_OVERSTATED_EVIDENCE_STATUSES = {"grounded", "calculated", "tested"}
_PHASE12_FORBIDDEN_CANDIDATE_EVIDENCE = {"tested"}
_AWAITING_SELECTION_STATES = {"proposed", "awaiting-user"}


def compute_component_plan_coverage_summary(
    content: dict[str, Any],
    *,
    architecture_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Compute coverage summary fields from component-plan content."""

    roles = [r for r in (content.get("componentRoles") or []) if isinstance(r, dict)]
    candidates = [c for c in (content.get("candidates") or []) if isinstance(c, dict)]
    selections = [s for s in (content.get("selectionDecisions") or []) if isinstance(s, dict)]

    role_arch_ids: set[str] = set()
    covered_requirement_ids: set[str] = set()
    roles_without_arch = 0
    roles_without_req = 0
    for role in roles:
        arch_ids = [i for i in (role.get("architectureNodeIds") or []) if isinstance(i, str)]
        req_ids = [i for i in (role.get("requirementIds") or []) if isinstance(i, str)]
        if not arch_ids:
            roles_without_arch += 1
        else:
            role_arch_ids.update(arch_ids)
        if not req_ids:
            roles_without_req += 1
        else:
            covered_requirement_ids.update(req_ids)

    candidates_by_role: Counter[str] = Counter()
    for candidate in candidates:
        role_id = candidate.get("componentRoleId")
        if isinstance(role_id, str):
            candidates_by_role[role_id] += 1

    roles_without_candidates = 0
    for role in roles:
        role_id = role.get("componentRoleId")
        if isinstance(role_id, str) and candidates_by_role[role_id] == 0:
            roles_without_candidates += 1

    blocked_roles: set[str] = set()
    awaiting_roles: set[str] = set()
    for selection in selections:
        role_id = selection.get("componentRoleId")
        if not isinstance(role_id, str):
            continue
        state = selection.get("selectionState")
        if state in _AWAITING_SELECTION_STATES:
            awaiting_roles.add(role_id)
        if state == "blocked":
            blocked_roles.add(role_id)
        candidate_id = selection.get("selectedCandidateId")
        if state == "approved" and isinstance(candidate_id, str):
            for candidate in candidates:
                if (
                    candidate.get("candidateId") == candidate_id
                    and candidate.get("candidateState") == "blocked"
                ):
                    blocked_roles.add(role_id)

    if architecture_node_ids is not None:
        covered = sorted(role_arch_ids.intersection(architecture_node_ids))
        uncovered = sorted(architecture_node_ids.difference(role_arch_ids))
        total_nodes = len(architecture_node_ids)
        covered_count = len(covered)
    else:
        covered = sorted(role_arch_ids)
        uncovered = [
            node_id
            for node_id in (content.get("coverageSummary") or {}).get(
                "uncoveredArchitectureNodeIds"
            )
            or []
            if isinstance(node_id, str)
        ]
        covered_count = len(covered)
        declared_total = (content.get("coverageSummary") or {}).get("totalArchitectureNodes")
        total_nodes = (
            int(declared_total)
            if isinstance(declared_total, int)
            else covered_count + len(uncovered)
        )

    covered_reqs = sorted(covered_requirement_ids)
    uncovered_reqs = [
        req_id
        for req_id in (content.get("coverageSummary") or {}).get("uncoveredRequirementIds") or []
        if isinstance(req_id, str)
    ]
    total_relevant = len(covered_reqs) + len(uncovered_reqs)

    return {
        "totalArchitectureNodes": total_nodes,
        "coveredArchitectureNodes": covered_count,
        "uncoveredArchitectureNodeIds": uncovered,
        "totalRelevantRequirements": total_relevant,
        "coveredRequirementIds": covered_reqs,
        "uncoveredRequirementIds": uncovered_reqs,
        "rolesWithoutArchitectureMapping": roles_without_arch,
        "rolesWithoutRequirementMapping": roles_without_req,
        "rolesWithoutCandidates": roles_without_candidates,
        "rolesWithBlockedSelection": len(blocked_roles),
        "rolesAwaitingApproval": len(awaiting_roles),
    }


def validate_component_plan_content(
    content: dict[str, Any],
    *,
    architecture_node_ids: set[str] | None = None,
    requirement_ids: set[str] | None = None,
) -> list[SemanticValidationError]:
    """Public entry point for Component Plan content semantic validation."""

    return _validate_component_plan_content(
        content,
        architecture_node_ids=architecture_node_ids,
        requirement_ids=requirement_ids,
    )


def _validate_component_plan_content(
    content: dict[str, Any],
    *,
    architecture_node_ids: set[str] | None = None,
    requirement_ids: set[str] | None = None,
) -> list[SemanticValidationError]:
    errors: list[SemanticValidationError] = []

    roles = content.get("componentRoles") or []
    candidates = content.get("candidates") or []
    selections = content.get("selectionDecisions") or []
    checks = content.get("compatibilityChecks") or []
    constraints = content.get("selectionConstraints") or []

    role_ids: set[str] = set()
    seen_role_ids: Counter[str] = Counter()
    if isinstance(roles, list):
        for idx, role in enumerate(roles):
            if not isinstance(role, dict):
                continue
            role_id = role.get("componentRoleId")
            if isinstance(role_id, str):
                seen_role_ids[role_id] += 1
                role_ids.add(role_id)
            arch_ids = role.get("architectureNodeIds") or []
            if not isinstance(arch_ids, list) or len(arch_ids) == 0:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_ROLE_MISSING_ARCHITECTURE_REF",
                        message="Component role must reference at least one architecture node.",
                        path=f"componentPlan.componentRoles[{idx}].architectureNodeIds",
                        blocking=True,
                    )
                )
            elif architecture_node_ids is not None:
                for arch_id in arch_ids:
                    if isinstance(arch_id, str) and arch_id not in architecture_node_ids:
                        errors.append(
                            SemanticValidationError(
                                code="COMPONENT_UNKNOWN_ARCHITECTURE_NODE",
                                message=(
                                    "Component role references an architecture node that is "
                                    "not present in the functional architecture artifact."
                                ),
                                path=f"componentPlan.componentRoles[{idx}].architectureNodeIds",
                                blocking=True,
                            )
                        )
            req_ids = role.get("requirementIds") or []
            if isinstance(req_ids, list) and requirement_ids is not None:
                for req_id in req_ids:
                    if isinstance(req_id, str) and req_id not in requirement_ids:
                        errors.append(
                            SemanticValidationError(
                                code="COMPONENT_UNKNOWN_REQUIREMENT",
                                message=(
                                    "Component role references a requirementId that is not "
                                    "present in the requirement-set artifact."
                                ),
                                path=f"componentPlan.componentRoles[{idx}].requirementIds",
                                blocking=True,
                            )
                        )

    for role_id, count in sorted(seen_role_ids.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_DUPLICATE_ROLE_ID",
                    message=f"Duplicate componentRoleId: {role_id}.",
                    path="componentPlan.componentRoles",
                    blocking=True,
                )
            )

    candidates_by_id: dict[str, dict[str, Any]] = {}
    seen_candidate_ids: Counter[str] = Counter()
    if isinstance(candidates, list):
        for idx, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            candidate_id = candidate.get("candidateId")
            role_id = candidate.get("componentRoleId")
            if isinstance(candidate_id, str):
                seen_candidate_ids[candidate_id] += 1
                candidates_by_id[candidate_id] = candidate
            if isinstance(role_id, str) and role_id not in role_ids:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_CANDIDATE_MISSING_ROLE",
                        message="Candidate references an unknown componentRoleId.",
                        path=f"componentPlan.candidates[{idx}].componentRoleId",
                        blocking=True,
                    )
                )
            evidence_status = candidate.get("evidenceStatus")
            evidence_refs = candidate.get("evidenceReferences") or []
            if evidence_status in _PHASE12_FORBIDDEN_CANDIDATE_EVIDENCE:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_CANDIDATE_OVERSTATED_EVIDENCE",
                        message=(
                            "Candidate evidenceStatus 'tested' is not allowed in Phase 12 "
                            "component planning."
                        ),
                        path=f"componentPlan.candidates[{idx}].evidenceStatus",
                        blocking=True,
                    )
                )
            elif evidence_status in _OVERSTATED_EVIDENCE_STATUSES and (
                not isinstance(evidence_refs, list) or len(evidence_refs) == 0
            ):
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_CANDIDATE_OVERSTATED_EVIDENCE",
                        message=(
                            "Candidate evidenceStatus is stronger than available "
                            "evidenceReferences support."
                        ),
                        path=f"componentPlan.candidates[{idx}].evidenceStatus",
                        blocking=True,
                    )
                )

    for candidate_id, count in sorted(seen_candidate_ids.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_DUPLICATE_CANDIDATE_ID",
                    message=f"Duplicate candidateId: {candidate_id}.",
                    path="componentPlan.candidates",
                    blocking=True,
                )
            )

    seen_constraint_ids: Counter[str] = Counter()
    if isinstance(constraints, list):
        for idx, constraint in enumerate(constraints):
            if not isinstance(constraint, dict):
                continue
            constraint_id = constraint.get("constraintId")
            if isinstance(constraint_id, str):
                seen_constraint_ids[constraint_id] += 1
            role_id = constraint.get("componentRoleId")
            if isinstance(role_id, str) and role_id not in role_ids:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_CONSTRAINT_MISSING_ROLE",
                        message="Selection constraint references an unknown componentRoleId.",
                        path=f"componentPlan.selectionConstraints[{idx}].componentRoleId",
                        blocking=True,
                    )
                )
            for req_id in constraint.get("sourceRequirementIds") or []:
                if (
                    isinstance(req_id, str)
                    and requirement_ids is not None
                    and req_id not in requirement_ids
                ):
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_UNKNOWN_REQUIREMENT",
                            message=(
                                "Selection constraint references a requirementId missing "
                                "from the requirement-set artifact."
                            ),
                            path=(
                                f"componentPlan.selectionConstraints[{idx}].sourceRequirementIds"
                            ),
                            blocking=True,
                        )
                    )
            for arch_id in constraint.get("sourceArchitectureNodeIds") or []:
                if (
                    isinstance(arch_id, str)
                    and architecture_node_ids is not None
                    and arch_id not in architecture_node_ids
                ):
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_UNKNOWN_ARCHITECTURE_NODE",
                            message=(
                                "Selection constraint references an architecture node missing "
                                "from the functional architecture artifact."
                            ),
                            path=(
                                "componentPlan.selectionConstraints"
                                f"[{idx}].sourceArchitectureNodeIds"
                            ),
                            blocking=True,
                        )
                    )

    for constraint_id, count in sorted(seen_constraint_ids.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_DUPLICATE_CONSTRAINT_ID",
                    message=f"Duplicate constraintId: {constraint_id}.",
                    path="componentPlan.selectionConstraints",
                    blocking=True,
                )
            )

    approved_roles: Counter[str] = Counter()
    seen_selection_ids: Counter[str] = Counter()
    if isinstance(selections, list):
        for idx, selection in enumerate(selections):
            if not isinstance(selection, dict):
                continue
            selection_id = selection.get("selectionDecisionId")
            if isinstance(selection_id, str):
                seen_selection_ids[selection_id] += 1
            role_id = selection.get("componentRoleId")
            candidate_id = selection.get("selectedCandidateId")
            selection_state = selection.get("selectionState")

            if isinstance(role_id, str) and role_id not in role_ids:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_SELECTION_MISSING_ROLE",
                        message="Selection decision references an unknown componentRoleId.",
                        path=f"componentPlan.selectionDecisions[{idx}].componentRoleId",
                        blocking=True,
                    )
                )

            candidate = (
                candidates_by_id.get(candidate_id) if isinstance(candidate_id, str) else None
            )
            if isinstance(candidate_id, str) and candidate is None:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_SELECTION_MISSING_CANDIDATE",
                        message="Selection decision references an unknown selectedCandidateId.",
                        path=f"componentPlan.selectionDecisions[{idx}].selectedCandidateId",
                        blocking=True,
                    )
                )
            elif isinstance(candidate, dict):
                candidate_role = candidate.get("componentRoleId")
                if (
                    isinstance(role_id, str)
                    and isinstance(candidate_role, str)
                    and candidate_role != role_id
                ):
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_SELECTION_ROLE_CANDIDATE_MISMATCH",
                            message="Selected candidate does not belong to the selection role.",
                            path=f"componentPlan.selectionDecisions[{idx}]",
                            blocking=True,
                        )
                    )
                if selection_state == "approved" and candidate.get("candidateState") == "blocked":
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_SELECTION_BLOCKED_CANDIDATE_APPROVED",
                            message="Blocked candidates cannot be approved selections.",
                            path=f"componentPlan.selectionDecisions[{idx}]",
                            blocking=True,
                        )
                    )
                if selection_state == "approved" and candidate.get("candidateState") == "rejected":
                    errors.append(
                        SemanticValidationError(
                            code="COMPONENT_SELECTION_REJECTED_CANDIDATE_APPROVED",
                            message="Rejected candidates cannot be current approved selections.",
                            path=f"componentPlan.selectionDecisions[{idx}]",
                            blocking=True,
                        )
                    )

            if selection_state == "approved" and isinstance(role_id, str):
                approved_roles[role_id] += 1

    for selection_id, count in sorted(seen_selection_ids.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_DUPLICATE_SELECTION_ID",
                    message=f"Duplicate selectionDecisionId: {selection_id}.",
                    path="componentPlan.selectionDecisions",
                    blocking=True,
                )
            )

    for role_id, count in sorted(approved_roles.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_SELECTION_DUPLICATE_APPROVED",
                    message=f"Role {role_id} has multiple approved selection decisions.",
                    path="componentPlan.selectionDecisions",
                    blocking=True,
                )
            )

    seen_check_ids: Counter[str] = Counter()
    if isinstance(checks, list):
        for idx, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            check_id = check.get("compatibilityCheckId")
            if isinstance(check_id, str):
                seen_check_ids[check_id] += 1
            role_id = check.get("componentRoleId")
            candidate_id = check.get("candidateId")
            if isinstance(role_id, str) and role_id not in role_ids:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_COMPATIBILITY_MISSING_ROLE",
                        message="Compatibility check references an unknown componentRoleId.",
                        path=f"componentPlan.compatibilityChecks[{idx}].componentRoleId",
                        blocking=True,
                    )
                )
            if isinstance(candidate_id, str) and candidate_id not in candidates_by_id:
                errors.append(
                    SemanticValidationError(
                        code="COMPONENT_COMPATIBILITY_MISSING_CANDIDATE",
                        message="Compatibility check references an unknown candidateId.",
                        path=f"componentPlan.compatibilityChecks[{idx}].candidateId",
                        blocking=True,
                    )
                )

    for check_id, count in sorted(seen_check_ids.items()):
        if count > 1:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_DUPLICATE_COMPATIBILITY_CHECK_ID",
                    message=f"Duplicate compatibilityCheckId: {check_id}.",
                    path="componentPlan.compatibilityChecks",
                    blocking=True,
                )
            )

    declared = content.get("coverageSummary")
    if isinstance(declared, dict):
        expected = compute_component_plan_coverage_summary(
            content,
            architecture_node_ids=architecture_node_ids,
        )
        comparable_keys = (
            "rolesWithoutArchitectureMapping",
            "rolesWithoutRequirementMapping",
            "rolesWithoutCandidates",
            "rolesWithBlockedSelection",
            "rolesAwaitingApproval",
            "coveredRequirementIds",
        )
        mismatched = []
        for key in comparable_keys:
            if declared.get(key) != expected.get(key):
                mismatched.append(key)
        if architecture_node_ids is not None:
            for key in ("totalArchitectureNodes", "coveredArchitectureNodes"):
                if declared.get(key) != expected.get(key):
                    mismatched.append(key)
            declared_uncovered = declared.get("uncoveredArchitectureNodeIds") or []
            expected_uncovered = expected.get("uncoveredArchitectureNodeIds") or []
            if set(declared_uncovered) != set(expected_uncovered):
                mismatched.append("uncoveredArchitectureNodeIds")
        else:
            # Without an architecture artifact, still require internal arithmetic consistency.
            uncovered = declared.get("uncoveredArchitectureNodeIds") or []
            covered_count = declared.get("coveredArchitectureNodes")
            total = declared.get("totalArchitectureNodes")
            if (
                isinstance(covered_count, int)
                and isinstance(total, int)
                and isinstance(uncovered, list)
                and total != covered_count + len(uncovered)
            ):
                mismatched.append("totalArchitectureNodes")
            if covered_count != expected.get("coveredArchitectureNodes"):
                mismatched.append("coveredArchitectureNodes")
        if mismatched:
            errors.append(
                SemanticValidationError(
                    code="COMPONENT_COVERAGE_MISMATCH",
                    message=(
                        "coverageSummary does not match computed coverage for fields: "
                        + ", ".join(sorted(set(mismatched)))
                        + "."
                    ),
                    path="componentPlan.coverageSummary",
                    blocking=True,
                )
            )

    return errors
