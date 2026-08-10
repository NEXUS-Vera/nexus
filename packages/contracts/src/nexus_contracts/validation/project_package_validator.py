from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .semantic_validators import SemanticValidationError, semantic_validate_bundle


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_project_package_bundle(folder: Path) -> dict[str, Any]:
    """
    Load a fixture directory as a single coherent validation bundle.

    This is intentionally deterministic (no filesystem ordering surprises).
    """

    bundle: dict[str, Any] = {
        "artifact_envelopes": [],
        "project": None,
        "user_turn": None,
        "turn_route": None,
        "workflow_run": None,
        "requirement_set_content": None,
        "functional_architecture_content": None,
        "next_action_content": None,
        "component_plan_content": None,
        # Phase 13 layered artifacts are optional for backwards-compatible golden fixtures.
        "electrical_architecture_content": None,
        "physical_architecture_content": None,
        "validation_issues": [],
        "open_questions": [],
        "vera_response": None,
    }

    for path in sorted(folder.glob("*.json")):
        filename = path.name
        payload = _load_json(path)

        if filename == "project.json":
            bundle["project"] = payload
        elif filename == "user-turn.json":
            bundle["user_turn"] = payload
        elif filename == "turn-route.json":
            bundle["turn_route"] = payload
        elif filename == "workflow-run.json":
            bundle["workflow_run"] = payload
        elif filename == "validation-issues.json":
            bundle["validation_issues"] = payload
        elif filename == "open-questions.json":
            bundle["open_questions"] = payload
        elif filename == "vera-response.json":
            bundle["vera_response"] = payload
        elif filename.endswith("-artifact.json"):
            if not isinstance(payload, dict):
                continue
            bundle["artifact_envelopes"].append(payload)
            artifact_type = payload.get("artifactType")
            content = payload.get("content")
            if artifact_type == "requirement-set":
                bundle["requirement_set_content"] = content
            elif artifact_type == "functional-architecture":
                bundle["functional_architecture_content"] = content
            elif artifact_type == "next-action":
                bundle["next_action_content"] = content
            elif artifact_type == "component-plan":
                bundle["component_plan_content"] = content
            elif artifact_type == "electrical-architecture":
                bundle["electrical_architecture_content"] = content
            elif artifact_type == "physical-architecture":
                bundle["physical_architecture_content"] = content

    return bundle


def validate_project_package_bundle(bundle: dict[str, Any]) -> list[SemanticValidationError]:
    errors = semantic_validate_bundle(bundle)

    project = bundle.get("project") or {}
    project_current = project.get("currentArtifactReferences") or []

    artifact_envelopes: list[dict[str, Any]] = bundle.get("artifact_envelopes") or []
    artifact_by_type = {}
    for art in artifact_envelopes:
        if isinstance(art, dict) and isinstance(art.get("artifactType"), str):
            artifact_by_type[art["artifactType"]] = art

    # electrical-architecture / physical-architecture are intentionally optional so
    # pre-Phase-13 golden fixtures remain valid; new init packages may include them.
    required_types = {
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "next-action",
        "component-plan",
    }
    missing_types = sorted(required_types.difference(artifact_by_type.keys()))
    if missing_types:
        errors.append(
            SemanticValidationError(
                code="PKG_MISSING_REQUIRED_ARTIFACT_TYPES",
                message=f"Package is missing required artifact types: {missing_types}.",
                path="artifact_envelopes",
                blocking=True,
            )
        )

    # Deterministic traceability: every requirement should be satisfied by at least one node.
    req_set = bundle.get("requirement_set_content") or {}
    requirements = req_set.get("requirements") or []
    req_ids: set[str] = set()
    for r in requirements:
        if not isinstance(r, dict):
            continue
        rid = r.get("requirementId")
        if isinstance(rid, str):
            req_ids.add(rid)

    func_arch = bundle.get("functional_architecture_content") or {}
    nodes = func_arch.get("nodes") or []
    satisfied_ids: set[str] = set()
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for rid in node.get("satisfiesRequirementIds") or []:
                if isinstance(rid, str):
                    satisfied_ids.add(rid)

    missing_traceability = sorted(req_ids.difference(satisfied_ids))
    if missing_traceability:
        errors.append(
            SemanticValidationError(
                code="PKG_REQUIREMENT_NOT_SATISFIED_BY_ANY_NODE",
                message=(
                    "Requirement-to-architecture traceability is incomplete; "
                    f"unsatisfied requirementIds: {missing_traceability}."
                ),
                path="functionalArchitecture.nodes[].satisfiesRequirementIds",
                blocking=True,
            )
        )

    # Verify Vera response artifact references align with package artifacts (by type and id).
    vera = bundle.get("vera_response") or {}
    if isinstance(vera, dict):
        vera_created = vera.get("createdArtifactReferences") or []
        vera_next_ref = vera.get("nextActionArtifactReference") or {}

        if isinstance(vera_created, list):
            vera_created_by_type = {
                r.get("artifactType"): r.get("artifactId")
                for r in vera_created
                if isinstance(r, dict) and isinstance(r.get("artifactType"), str)
            }

            for a_type, art in artifact_by_type.items():
                if a_type in vera_created_by_type:
                    expected_id = art.get("artifactId")
                    actual_id = vera_created_by_type.get(a_type)
                    if isinstance(expected_id, str) and expected_id != actual_id:
                        errors.append(
                            SemanticValidationError(
                                code="PKG_VERA_CREATED_ARTIFACT_ID_MISMATCH",
                                message="Vera createdArtifactReferences artifactId mismatch.",
                                path="veraResponse.createdArtifactReferences",
                                blocking=True,
                            )
                        )

        if isinstance(vera_next_ref, dict) and "artifactType" in vera_next_ref:
            next_id = vera_next_ref.get("artifactId")
            expected_next_id = (
                artifact_by_type.get("next-action", {}).get("artifactId")
                if isinstance(artifact_by_type.get("next-action"), dict)
                else None
            )
            if (
                isinstance(next_id, str)
                and isinstance(expected_next_id, str)
                and next_id != expected_next_id
            ):
                errors.append(
                    SemanticValidationError(
                        code="PKG_VERA_NEXT_ACTION_ARTIFACT_ID_MISMATCH",
                        message="Vera nextActionArtifactReference artifactId mismatch.",
                        path="veraResponse.nextActionArtifactReference",
                        blocking=True,
                    )
                )

    # Verify project.currentArtifactReferences align with package artifacts by type/id.
    if isinstance(project_current, list):
        current_by_type = {
            r.get("artifactType"): r.get("artifactId")
            for r in project_current
            if isinstance(r, dict) and isinstance(r.get("artifactType"), str)
        }
        for a_type, art in artifact_by_type.items():
            expected_id = art.get("artifactId")
            actual_id = current_by_type.get(a_type)
            if isinstance(expected_id, str) and actual_id is not None and expected_id != actual_id:
                errors.append(
                    SemanticValidationError(
                        code="PKG_PROJECT_CURRENT_ARTIFACT_ID_MISMATCH",
                        message="project.currentArtifactReferences artifactId mismatch.",
                        path="project.currentArtifactReferences",
                        blocking=True,
                    )
                )

    return errors


def validate_project_package_folder(folder: Path) -> list[SemanticValidationError]:
    bundle = load_project_package_bundle(folder)
    return validate_project_package_bundle(bundle)
