"""Execution-plan schema and cross-record checks against its initialization basis."""

from __future__ import annotations

from typing import Any

from .schema_validator import validate_against_schema_id
from .semantic_validators import SemanticValidationError

SCHEMA_ID = "https://nexus.local/schemas/project/execution-plan.v1.schema.json"


def validate_execution_plan(
    plan: dict[str, Any], artifacts: list[dict[str, Any]], open_questions: list[dict[str, Any]]
) -> list[SemanticValidationError]:
    errors = [
        SemanticValidationError(e.code, e.message, e.path)
        for e in validate_against_schema_id(plan, SCHEMA_ID)
    ]
    if errors:
        return errors

    def reject(message: str) -> None:
        errors.append(SemanticValidationError("EXECUTION_PLAN_INVALID_LINK", message))

    by_id = {a["artifactId"]: a for a in artifacts}
    sources = {s["artifactId"] for s in plan["sourceArtifacts"]}
    if sources != set(by_id):
        reject("Source artifacts must cover the initialization basis.")
    if len(sources) != len(plan["sourceArtifacts"]):
        reject("Duplicate source artifact.")
    for source in plan["sourceArtifacts"]:
        artifact = by_id.get(source["artifactId"])
        if artifact is None or artifact["artifactVersion"] != source["artifactVersion"]:
            reject(f"Unknown artifact revision: {source}.")
    collections = {
        "requirements": ("requirement-set", "requirements", "requirementId"),
        "assumptions": (None, "assumptions", "assumptionId"),
        "components": ("component-plan", "componentRoles", "componentRoleId"),
        "interfaces": ("electrical-architecture", "connections", "connectionId"),
    }
    for field, (kind, collection, id_key) in collections.items():
        seen: set[tuple[str, str]] = set()
        for ref in plan[field]:
            artifact = by_id.get(ref["artifactId"], {})
            identity = (ref["artifactId"], ref["entityId"])
            if identity in seen:
                reject(f"Duplicate {field} reference: {ref}.")
            seen.add(identity)
            valid_ids = {
                e.get(id_key)
                for e in artifact.get("content", {}).get(collection, [])
                if isinstance(e, dict)
            }
            if (
                ref["artifactId"] not in sources
                or ref["entityId"] not in valid_ids
                or (kind and artifact.get("artifactType") != kind)
            ):
                reject(f"Dangling {field} reference: {ref}.")

        expected = {
            (a["artifactId"], e[id_key])
            for a in artifacts
            if kind is None or a["artifactType"] == kind
            for e in a.get("content", {}).get(collection, [])
            if isinstance(e, dict) and id_key in e
        }
        if seen != expected:
            reject(f"Incomplete {field} links for the initialization basis.")

    def unique(items: list[dict[str, Any]], key: str) -> set[str]:
        values = {i[key] for i in items}
        if len(values) != len(items):
            reject(f"Duplicate {key}.")
        return values

    workspace_keys = unique(plan["workspaces"], "workspaceKey")
    for workspace in plan["workspaces"]:
        if workspace["availability"] == "artifact-available" and not any(
            a["artifactType"] == workspace["artifactType"] for a in artifacts
        ):
            reject(f"Workspace artifact unavailable: {workspace}.")
    requirement_ids = {r["entityId"] for r in plan["requirements"]}
    objective_ids = unique(plan["verificationObjectives"], "objectiveId")
    for objective in plan["verificationObjectives"]:
        if objective["requirementId"] not in requirement_ids:
            reject(f"Unknown objective requirement: {objective}.")
        if objective["workspaceKey"] not in workspace_keys:
            reject(f"Unknown objective workspace: {objective}.")
    if requirement_ids != {o["requirementId"] for o in plan["verificationObjectives"]}:
        reject("Every linked requirement needs a verification objective.")
    question_ids = {q["questionId"] for q in open_questions if q["status"] == "open"}
    if set(plan["openDecisionIds"]) != question_ids:
        reject("Open decisions must preserve all unresolved questions.")
    unique(plan["steps"], "stepId")
    preceding: set[str] = set()
    for step in plan["steps"]:
        if not set(step["dependsOn"]) <= preceding:
            reject(f"Dependency must reference an earlier step: {step['stepId']}.")
        if not set(step["workspaceKeys"]) <= workspace_keys:
            reject(f"Unknown step workspace: {step['stepId']}.")
        if not set(step["objectiveIds"]) <= objective_ids:
            reject(f"Unknown step objective: {step['stepId']}.")
        preceding.add(step["stepId"])
    return errors
