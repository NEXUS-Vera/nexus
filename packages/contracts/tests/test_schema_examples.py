from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, RefResolver

CONTRACTS_DIR = Path(__file__).resolve().parents[1]
SCHEMA_DIR = CONTRACTS_DIR / "schemas"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"
SRC_DIR = CONTRACTS_DIR / "src"

sys.path.insert(0, str(SRC_DIR))
from nexus_contracts.validation.project_package_validator import (  # noqa: E402
    validate_project_package_folder,
)
from nexus_contracts.validation.semantic_validators import (  # noqa: E402
    semantic_validate_bundle,
)

# Fixture filenames validated against a single root schema only.
RECORD_SCHEMA_IDS_BY_FILENAME: dict[str, str] = {
    "project-history.json": "https://nexus.local/schemas/responses/project-history.v1.schema.json",
    "project-turn-result.json": (
        "https://nexus.local/schemas/responses/project-turn-result.v1.schema.json"
    ),
    "project-change-intent.json": (
        "https://nexus.local/schemas/modification/project-change-intent.v1.schema.json"
    ),
    "project-impact-analysis.json": (
        "https://nexus.local/schemas/modification/project-impact-analysis.v1.schema.json"
    ),
    "artifact-dependency.json": (
        "https://nexus.local/schemas/dependencies/artifact-dependency.v1.schema.json"
    ),
    "artifact-type-definition.json": (
        "https://nexus.local/schemas/artifacts/artifact-type-definition.v1.schema.json"
    ),
    "artifact-command.json": (
        "https://nexus.local/schemas/artifacts/artifact-command.v1.schema.json"
    ),
    "artifact-command-result.json": (
        "https://nexus.local/schemas/artifacts/artifact-command-result.v1.schema.json"
    ),
    "artifact-proposal.json": (
        "https://nexus.local/schemas/artifacts/artifact-proposal.v1.schema.json"
    ),
    "workspace-descriptor.json": (
        "https://nexus.local/schemas/workspaces/workspace-descriptor.v1.schema.json"
    ),
    "workspace-snapshot.json": (
        "https://nexus.local/schemas/workspaces/workspace-snapshot.v1.schema.json"
    ),
    "workspace-draft-state.json": (
        "https://nexus.local/schemas/workspaces/workspace-draft-state.v1.schema.json"
    ),
    "execution-request.json": (
        "https://nexus.local/schemas/executions/execution-request.v1.schema.json"
    ),
    "execution-run.json": ("https://nexus.local/schemas/executions/execution-run.v1.schema.json"),
    "execution-result.json": (
        "https://nexus.local/schemas/executions/execution-result.v1.schema.json"
    ),
    "produced-output.json": (
        "https://nexus.local/schemas/executions/produced-output.v1.schema.json"
    ),
    "circuit-simulation-support-assessment.json": (
        "https://nexus.local/schemas/executions/"
        "circuit-simulation-support-assessment.v1.schema.json"
    ),
    "runtime-capability.json": (
        "https://nexus.local/schemas/executions/runtime-capability.v1.schema.json"
    ),
    "external-workspace-reference.json": (
        "https://nexus.local/schemas/providers/external-workspace-reference.v1.schema.json"
    ),
    "project-event.json": ("https://nexus.local/schemas/events/project-event.v1.schema.json"),
    "project-board-projection.json": (
        "https://nexus.local/schemas/projections/project-board-projection.v1.schema.json"
    ),
    "artifact-authority.json": (
        "https://nexus.local/schemas/governance/artifact-authority.v1.schema.json"
    ),
    "approval-requirement.json": (
        "https://nexus.local/schemas/governance/approval-requirement.v1.schema.json"
    ),
    "project-graph-node.json": (
        "https://nexus.local/schemas/graph/project-graph-node.v1.schema.json"
    ),
    "project-graph-edge.json": (
        "https://nexus.local/schemas/graph/project-graph-edge.v1.schema.json"
    ),
    "graph-traversal-result.json": (
        "https://nexus.local/schemas/graph/graph-traversal-result.v1.schema.json"
    ),
}

# Package wrappers that inline a full project package and are also expanded into the
# cross-record semantic bundle.
PACKAGE_WRAPPER_SCHEMA_IDS_BY_FILENAME: dict[str, str] = {
    "project-initialization-result.json": (
        "https://nexus.local/schemas/responses/project-initialization-result.v1.schema.json"
    ),
    "project-current-state.json": (
        "https://nexus.local/schemas/responses/project-current-state.v1.schema.json"
    ),
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("**/*.schema.json"))


def _load_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in _iter_schema_files():
        data = _load_json(path)
        schema_id = data.get("$id")
        assert isinstance(schema_id, str) and schema_id
        schemas[schema_id] = data
    return schemas


def _assert_additional_properties_false_in_objects(schema: Any) -> None:
    """
    Deterministic traversal: any schema node that declares object-typed payloads
    must also explicitly forbid undeclared fields.
    """

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                # Wrapper union/intersection schemas may declare `type: object` without listing
                # concrete payload fields; the branches (or referenced schemas) enforce
                # `additionalProperties` constraints.
                is_wrapper = (
                    any(k in node for k in ("oneOf", "allOf", "anyOf")) and "properties" not in node
                )
                # `artifact.v1` uses constraint-only object nodes (artifactType/content).
                # In those cases, `additionalProperties` must be omitted to avoid conflicting
                # with the envelope schema restrictions.
                is_constraint_only = set(node.keys()).issubset({"type", "properties", "required"})

                if not is_wrapper and not is_constraint_only:
                    assert node.get("additionalProperties") is False, (
                        f"Expected additionalProperties:false in schema node: {node.get('title')}"
                    )
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(schema)


def _make_validator(schema: dict[str, Any], store: dict[str, Any]) -> Draft202012Validator:
    resolver = RefResolver.from_schema(schema, store=store, cache_remote=False)
    return Draft202012Validator(schema, resolver=resolver)


@pytest.fixture(scope="session")
def schemas_by_id() -> dict[str, dict[str, Any]]:
    return _load_schemas()


@pytest.fixture(scope="session")
def store(schemas_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return dict(schemas_by_id)


def test_schemas_are_valid_json_schema_draft_2020_12(
    schemas_by_id: dict[str, dict[str, Any]],
) -> None:
    for _schema_id, schema in sorted(schemas_by_id.items(), key=lambda x: x[0]):
        Draft202012Validator.check_schema(schema)
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


def test_all_local_ref_targets_resolve(schemas_by_id: dict[str, dict[str, Any]]) -> None:
    known_ids = set(schemas_by_id.keys())

    def _walk(node: Any) -> list[str]:
        refs: list[str] = []
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    refs.append(v)
                else:
                    refs.extend(_walk(v))
        elif isinstance(node, list):
            for v in node:
                refs.extend(_walk(v))
        return refs

    for schema_id, schema in sorted(schemas_by_id.items(), key=lambda x: x[0]):
        refs = _walk(schema)
        for ref in refs:
            if ref.startswith("https://nexus.local/schemas/"):
                base = ref.split("#", 1)[0]
                assert base in known_ids, f"{schema_id} has unresolved $ref: {ref}"


def test_no_core_schema_allows_undeclared_fields(schemas_by_id: dict[str, dict[str, Any]]) -> None:
    for schema in schemas_by_id.values():
        _assert_additional_properties_false_in_objects(schema)


def _validate_bundle_assets(
    folder: Path,
    schemas_by_id: dict[str, dict[str, Any]],
    store: dict[str, Any],
) -> tuple[list[str], list[Any]]:
    project_schema = schemas_by_id["https://nexus.local/schemas/project/project.v1.schema.json"]
    user_turn_schema = schemas_by_id["https://nexus.local/schemas/turns/user-turn.v1.schema.json"]
    turn_route_schema = schemas_by_id["https://nexus.local/schemas/turns/turn-route.v1.schema.json"]
    workflow_run_schema = schemas_by_id[
        "https://nexus.local/schemas/workflows/workflow-run.v1.schema.json"
    ]
    artifact_union_schema = schemas_by_id[
        "https://nexus.local/schemas/artifacts/artifact.v1.schema.json"
    ]
    validation_issue_schema = schemas_by_id[
        "https://nexus.local/schemas/validation/validation-issue.v1.schema.json"
    ]
    open_question_schema = schemas_by_id[
        "https://nexus.local/schemas/responses/open-question.v1.schema.json"
    ]
    vera_response_schema = schemas_by_id[
        "https://nexus.local/schemas/responses/vera-response.v1.schema.json"
    ]

    validators = {
        "project": _make_validator(project_schema, store),
        "user-turn": _make_validator(user_turn_schema, store),
        "turn-route": _make_validator(turn_route_schema, store),
        "workflow-run": _make_validator(workflow_run_schema, store),
        "artifact": _make_validator(artifact_union_schema, store),
        "validation-issue": _make_validator(validation_issue_schema, store),
        "open-question": _make_validator(open_question_schema, store),
        "vera-response": _make_validator(vera_response_schema, store),
    }
    for record_filename, record_schema_id in {
        **RECORD_SCHEMA_IDS_BY_FILENAME,
        **PACKAGE_WRAPPER_SCHEMA_IDS_BY_FILENAME,
    }.items():
        validators[record_filename] = _make_validator(schemas_by_id[record_schema_id], store)

    schema_errors: list[str] = []
    artifact_envelopes: list[dict[str, Any]] = []
    project: dict[str, Any] | None = None
    user_turn: dict[str, Any] | None = None
    turn_route: dict[str, Any] | None = None
    workflow_run: dict[str, Any] | None = None
    requirement_set_content: dict[str, Any] | None = None
    functional_architecture_content: dict[str, Any] | None = None
    next_action_content: dict[str, Any] | None = None
    validation_issues: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []
    vera_response: dict[str, Any] | None = None

    for path in sorted(folder.glob("*.json")):
        payload = _load_json(path)
        filename = path.name
        try:
            if filename in PACKAGE_WRAPPER_SCHEMA_IDS_BY_FILENAME:
                assert isinstance(payload, dict)
                errs = sorted(
                    validators[filename].iter_errors(payload),
                    key=lambda e: list(e.path),
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
                project = (
                    payload.get("project") if isinstance(payload.get("project"), dict) else project
                )
                user_turn = (
                    payload.get("userTurn")
                    if isinstance(payload.get("userTurn"), dict)
                    else user_turn
                )
                turn_route = (
                    payload.get("turnRoute")
                    if isinstance(payload.get("turnRoute"), dict)
                    else turn_route
                )
                workflow_run = (
                    payload.get("workflowRun")
                    if isinstance(payload.get("workflowRun"), dict)
                    else workflow_run
                )
                vera_response = (
                    payload.get("veraResponse")
                    if isinstance(payload.get("veraResponse"), dict)
                    else vera_response
                )
                if isinstance(payload.get("validationIssues"), list):
                    validation_issues = payload["validationIssues"]
                if isinstance(payload.get("openQuestions"), list):
                    open_questions = payload["openQuestions"]
                if isinstance(payload.get("artifacts"), list):
                    for art in payload["artifacts"]:
                        if not isinstance(art, dict):
                            continue
                        artifact_envelopes.append(art)
                        if art.get("artifactType") == "requirement-set":
                            requirement_set_content = art.get("content")
                        if art.get("artifactType") == "functional-architecture":
                            functional_architecture_content = art.get("content")
                        if art.get("artifactType") == "next-action":
                            next_action_content = art.get("content")
            elif filename == "project.json":
                assert isinstance(payload, dict)
                project = payload
                errs = sorted(
                    validators["project"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "user-turn.json":
                assert isinstance(payload, dict)
                user_turn = payload
                errs = sorted(
                    validators["user-turn"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "turn-route.json":
                assert isinstance(payload, dict)
                turn_route = payload
                errs = sorted(
                    validators["turn-route"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "workflow-run.json":
                assert isinstance(payload, dict)
                workflow_run = payload
                errs = sorted(
                    validators["workflow-run"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename.endswith("-artifact.json"):
                assert isinstance(payload, dict)
                artifact_envelopes.append(payload)
                errs = sorted(
                    validators["artifact"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
                if payload.get("artifactType") == "requirement-set":
                    requirement_set_content = payload.get("content")
                if payload.get("artifactType") == "functional-architecture":
                    functional_architecture_content = payload.get("content")
                if payload.get("artifactType") == "next-action":
                    next_action_content = payload.get("content")
            elif filename == "validation-issues.json":
                assert isinstance(payload, list)
                validation_issues = payload
                for item in payload:
                    errs = sorted(
                        validators["validation-issue"].iter_errors(item), key=lambda e: list(e.path)
                    )
                    if errs:
                        schema_errors.append(f"{filename} item: {[e.message for e in errs[:2]]}")
            elif filename == "open-questions.json":
                assert isinstance(payload, list)
                open_questions = payload
                for item in payload:
                    errs = sorted(
                        validators["open-question"].iter_errors(item), key=lambda e: list(e.path)
                    )
                    if errs:
                        schema_errors.append(f"{filename} item: {[e.message for e in errs[:2]]}")
            elif filename == "vera-response.json":
                assert isinstance(payload, dict)
                vera_response = payload
                errs = sorted(
                    validators["vera-response"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename in RECORD_SCHEMA_IDS_BY_FILENAME:
                assert isinstance(payload, dict)
                errs = sorted(validators[filename].iter_errors(payload), key=lambda e: list(e.path))
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
        except Exception as exc:  # noqa: BLE001
            schema_errors.append(f"{filename}: exception during validation: {exc}")

    semantic_bundle = {
        "artifact_envelopes": artifact_envelopes,
        "project": project,
        "user_turn": user_turn,
        "turn_route": turn_route,
        "workflow_run": workflow_run,
        "requirement_set_content": requirement_set_content,
        "functional_architecture_content": functional_architecture_content,
        "next_action_content": next_action_content,
        "validation_issues": validation_issues,
        "open_questions": open_questions,
        "vera_response": vera_response,
    }
    semantic_errors = semantic_validate_bundle(semantic_bundle)
    return schema_errors, semantic_errors


def test_all_valid_examples_pass(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    valid_dir = EXAMPLES_DIR / "valid"
    assert valid_dir.exists()
    for folder in sorted([p for p in valid_dir.iterdir() if p.is_dir()]):
        schema_errors, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
        assert not schema_errors, f"Expected no schema errors for {folder}: {schema_errors[:5]}"
        blocking = [e for e in semantic_errors if getattr(e, "blocking", True)]
        nonblocking = [e for e in semantic_errors if not getattr(e, "blocking", True)]
        allowed_nonblocking_codes = {
            "TECHNOLOGY_LEVEL_TERM_IN_FUNCTIONAL_ARCHITECTURE",
            "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT",
        }
        unexpected = [
            e for e in nonblocking if getattr(e, "code", None) not in allowed_nonblocking_codes
        ]
        assert not blocking, f"Expected no blocking semantic errors for {folder}: {blocking[:5]}"
        assert not unexpected, (
            f"Expected allowlisted-only warnings for {folder}: {[e.code for e in unexpected[:5]]}"
        )


def test_all_invalid_examples_fail(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    invalid_dir = EXAMPLES_DIR / "invalid"
    assert invalid_dir.exists()
    for folder in sorted([p for p in invalid_dir.iterdir() if p.is_dir()]):
        schema_errors, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
        assert schema_errors or semantic_errors, f"Expected invalid fixture to fail: {folder}"


def test_artifact_union_discrimination_works(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    artifact_union_schema = schemas_by_id[
        "https://nexus.local/schemas/artifacts/artifact.v1.schema.json"
    ]
    validator = _make_validator(artifact_union_schema, store)

    valid_req = _load_json(
        EXAMPLES_DIR / "valid" / "indoor-environmental-rover" / "requirement-set-artifact.json"
    )
    assert isinstance(valid_req, dict)
    tampered = deepcopy(valid_req)
    tampered["artifactType"] = "project-brief"
    errors = list(validator.iter_errors(tampered))
    assert errors, "Expected tampered artifactType mismatch to fail artifact union validation"


def test_semantic_cross_object_invariants(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    # Duplicate requirement display IDs
    folder = EXAMPLES_DIR / "invalid" / "06-duplicate-displayid"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "REQ_DUPLICATE_DISPLAY_ID" for e in semantic_errors)

    # Architecture edges referencing missing nodes
    folder = EXAMPLES_DIR / "invalid" / "07-architecture-edges-missing-nodes"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "ARCH_EDGE_REFERENCES_MISSING_NODE" for e in semantic_errors)

    # Requirement coverage referencing missing requirements
    folder = EXAMPLES_DIR / "invalid" / "08-requirement-coverage-missing-requirements"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "ARCH_REQUIREMENT_COVERAGE_MISSING_REQUIREMENTS" for e in semantic_errors)

    # Component/part identifiers should not be silently introduced at functional maturity.
    folder = EXAMPLES_DIR / "invalid" / "04-component-specific-architecture-functional-maturity"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "COMPONENT_SPECIFIC_ARCHITECTURE" for e in semantic_errors)

    # Inferred requirements must not be labeled as user-explicit.
    folder = EXAMPLES_DIR / "invalid" / "05-inferred-requirement-marked-user-explicit"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "REQ_SOURCE_INFERRED_MISLABELED" for e in semantic_errors)


def test_vera_response_forbids_hidden_reasoning_fields(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    folder = EXAMPLES_DIR / "invalid" / "13-vera-response-hidden-reasoning"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.code == "VERA_HIDDEN_REASONING_FORBIDDEN" for e in semantic_errors)


def test_artifact_status_dimensions_remain_separate() -> None:
    artifact = _load_json(
        EXAMPLES_DIR / "valid" / "indoor-environmental-rover" / "next-action-artifact.json"
    )
    assert isinstance(artifact, dict)
    tampered = deepcopy(artifact)
    tampered["status"] = "combined"

    semantic_bundle = {"artifact_envelopes": [tampered]}
    semantic_errors = semantic_validate_bundle(semantic_bundle)
    assert any(e.code == "ARTIFACT_STATUS_DIMENSIONS_COMBINED" for e in semantic_errors)


def test_schema_version_and_artifact_version_remain_separate() -> None:
    artifact = _load_json(
        EXAMPLES_DIR / "valid" / "indoor-environmental-rover" / "next-action-artifact.json"
    )
    assert isinstance(artifact, dict)
    tampered = deepcopy(artifact)
    tampered["artifactVersion"] = "not-an-int"

    semantic_bundle = {"artifact_envelopes": [tampered]}
    semantic_errors = semantic_validate_bundle(semantic_bundle)
    assert any(e.code == "ARTIFACT_VERSION_WRONG_TYPE" for e in semantic_errors)


def test_functional_architecture_maturity_is_functional() -> None:
    artifact = _load_json(
        EXAMPLES_DIR
        / "valid"
        / "indoor-environmental-rover"
        / "functional-architecture-artifact.json"
    )
    assert isinstance(artifact, dict)
    content = artifact.get("content")
    assert isinstance(content, dict)
    assert content.get("architectureMaturity") == "functional"


def test_golden_set_packages_pass_project_package_validator() -> None:
    golden_dirs = [
        "indoor-environmental-rover",
        "wearable-tremor-monitor",
        "greenhouse-sensing-node",
        "vibration-monitoring-device",
        "robot-obstacle-detection-module",
    ]

    allowed_nonblocking_warning_codes = {
        "TECHNOLOGY_LEVEL_TERM_IN_FUNCTIONAL_ARCHITECTURE",
        "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT",
    }

    for d in golden_dirs:
        folder = EXAMPLES_DIR / "valid" / d
        assert folder.exists(), f"Missing golden fixture directory: {folder}"
        errors = validate_project_package_folder(folder)
        blocking = [e for e in errors if getattr(e, "blocking", True)]
        unexpected_warnings = [
            e
            for e in errors
            if not getattr(e, "blocking", True)
            and getattr(e, "code", None) not in allowed_nonblocking_warning_codes
        ]
        warning_codes = [e.code for e in unexpected_warnings[:10]]
        assert not blocking, (
            f"Golden fixture had blocking semantic errors in {d}: {[e.code for e in blocking[:10]]}"
        )
        assert not unexpected_warnings, (
            f"Golden fixture had unexpected warnings in {d}: {warning_codes}"
        )


def _make_user_turn(turn_id: str, message: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "turnId": turn_id,
        "projectId": "proj_0000000000000001",
        "rawUserMessage": message,
        "actor": {
            "schemaVersion": "1.0.0",
            "actorId": "actor_0000000000000001",
            "actorType": "user",
            "displayName": "User",
        },
        "timestamp": "2026-07-28T13:24:30Z",
    }


def _make_user_explicit_requirement(
    requirement_id: str,
    statement: str,
    turn_id: str,
    evidence_strength: str = "direct",
) -> dict[str, Any]:
    return {
        "requirementId": requirement_id,
        "displayId": "R1",
        "statement": statement,
        "category": "functional",
        "priority": "must",
        "sourceType": "user-explicit",
        "sourceReference": {
            "schemaVersion": "1.0.0",
            "evidenceId": f"evi_{requirement_id}",
            "sourceType": "user-turn",
            "sourceId": turn_id,
            "evidenceStrength": evidence_strength,
            "sourceLocator": "rawUserMessage",
        },
        "confidence": "high",
        "confirmationStatus": "confirmed",
        "verificationMethod": "Unit-test verification method.",
    }


def test_component_heuristic_does_not_flag_generic_terms() -> None:
    # IMU and BLE should not be treated as selected components in functional architecture.
    functional_arch = {
        "architectureId": "arch_0000000000000001",
        "architectureMaturity": "functional",
        "systemBoundary": "test",
        "nodes": [
            {
                "nodeId": "node_0000000000000001",
                "name": "Motion sensing using IMU and BLE",
                "functionalType": "sensing",
                "responsibilities": ["Collect motion samples over BLE."],
                "satisfiesRequirementIds": ["req_0000000000000001"],
            }
        ],
        "edges": [
            {
                "edgeId": "edge_0000000000000001",
                "fromNodeId": "node_0000000000000001",
                "toNodeId": "node_0000000000000001",
                "flowType": "data",
                "description": "self-edge",
            }
        ],
        "assumptions": [],
        "unresolvedDecisions": [],
        "requirementCoverage": {"coveredRequirementIds": ["req_0000000000000001"]},
    }

    errors = semantic_validate_bundle({"functional_architecture_content": functional_arch})
    blocking = [e for e in errors if getattr(e, "blocking", True)]
    assert not blocking, (
        f"Expected no blocking component heuristic errors, got {[e.code for e in blocking]}"
    )


def test_component_heuristic_flags_clear_part_identifiers() -> None:
    functional_arch = {
        "architectureId": "arch_0000000000000001",
        "architectureMaturity": "functional",
        "systemBoundary": "test",
        "nodes": [
            {
                "nodeId": "node_0000000000000001",
                "name": "Use ESP32-S3 for embedded control",
                "functionalType": "control",
                "responsibilities": ["Schedule acquisition using ESP32-S3."],
                "satisfiesRequirementIds": ["req_0000000000000001"],
            }
        ],
        "edges": [
            {
                "edgeId": "edge_0000000000000001",
                "fromNodeId": "node_0000000000000001",
                "toNodeId": "node_0000000000000001",
                "flowType": "data",
                "description": "self-edge",
            }
        ],
        "assumptions": [],
        "unresolvedDecisions": [],
        "requirementCoverage": {"coveredRequirementIds": ["req_0000000000000001"]},
    }

    errors = semantic_validate_bundle({"functional_architecture_content": functional_arch})
    assert any(e.code == "COMPONENT_SPECIFIC_ARCHITECTURE" and e.blocking for e in errors)


def test_technology_level_language_is_non_blocking_warning() -> None:
    functional_arch = {
        "architectureId": "arch_0000000000000001",
        "architectureMaturity": "functional",
        "systemBoundary": "test",
        "nodes": [
            {
                "nodeId": "node_0000000000000001",
                "name": "Data flow using radio communication for reporting",
                "functionalType": "communication",
                "responsibilities": ["Transmit via radio communication."],
                "satisfiesRequirementIds": ["req_0000000000000001"],
            }
        ],
        "edges": [
            {
                "edgeId": "edge_0000000000000001",
                "fromNodeId": "node_0000000000000001",
                "toNodeId": "node_0000000000000001",
                "flowType": "data",
                "description": "self-edge",
            }
        ],
        "assumptions": [],
        "unresolvedDecisions": [],
        "requirementCoverage": {"coveredRequirementIds": ["req_0000000000000001"]},
    }

    errors = semantic_validate_bundle({"functional_architecture_content": functional_arch})
    tech_warnings = [
        e
        for e in errors
        if e.code == "TECHNOLOGY_LEVEL_TERM_IN_FUNCTIONAL_ARCHITECTURE" and not e.blocking
    ]
    assert tech_warnings, "Expected non-blocking technology-level warning"
    assert not [e for e in errors if e.code == "COMPONENT_SPECIFIC_ARCHITECTURE" and e.blocking]


def test_user_explicit_numeric_claim_requires_user_support() -> None:
    turn_id = "turn_0000000000000001"
    user_turn = _make_user_turn(turn_id, "I want a device that records motion continuously.")
    requirement = _make_user_explicit_requirement(
        "req_0000000000000001", "The device shall operate for 2 hours.", turn_id
    )
    requirement_set = {"requirements": [requirement], "requirementSummary": "test"}

    errors = semantic_validate_bundle(
        {"user_turn": user_turn, "requirement_set_content": requirement_set}
    )
    assert any(e.code == "REQ_USER_EXPLICIT_NUMERIC_UNSUPPORTED" and e.blocking for e in errors)


def test_user_explicit_paraphrase_support_passes() -> None:
    turn_id = "turn_0000000000000002"
    user_turn = _make_user_turn(turn_id, "I want a wrist device that records hand tremors.")
    requirement = _make_user_explicit_requirement(
        "req_0000000000000003",
        "The device shall record motion associated with hand tremors.",
        turn_id,
    )
    requirement_set = {"requirements": [requirement], "requirementSummary": "test"}

    errors = semantic_validate_bundle(
        {"user_turn": user_turn, "requirement_set_content": requirement_set}
    )
    assert not [e for e in errors if e.blocking], (
        f"Expected no blocking provenance errors, got {[e.code for e in errors]}"
    )


def test_user_explicit_implied_claim_fails() -> None:
    turn_id = "turn_0000000000000004"
    user_turn = _make_user_turn(turn_id, "I want a remote greenhouse monitor.")
    requirement = _make_user_explicit_requirement(
        "req_0000000000000005",
        "The node shall use wireless communication.",
        turn_id,
    )
    requirement_set = {"requirements": [requirement], "requirementSummary": "test"}

    errors = semantic_validate_bundle(
        {"user_turn": user_turn, "requirement_set_content": requirement_set}
    )
    assert any(
        e.code in {"REQ_USER_EXPLICIT_UNSUPPORTED", "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT"}
        and e.blocking
        for e in errors
    )


def test_user_explicit_ambiguous_provenance_is_non_blocking_warning() -> None:
    turn_id = "turn_0000000000000006"
    user_turn = _make_user_turn(turn_id, "I want the rover to measure temperature.")
    requirement = _make_user_explicit_requirement(
        "req_0000000000000007",
        "The rover shall provide a map of humidity for later analysis.",
        turn_id,
    )
    requirement_set = {"requirements": [requirement], "requirementSummary": "test"}

    errors = semantic_validate_bundle(
        {"user_turn": user_turn, "requirement_set_content": requirement_set}
    )
    assert any(
        e.code == "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT" and not e.blocking for e in errors
    ), f"Expected non-blocking ambiguous provenance warning, got {[e.code for e in errors]}"


def test_user_explicit_wrong_turn_reference_fails() -> None:
    turn_id = "turn_0000000000000008"
    wrong_turn_id = "turn_0000000000000009"
    user_turn = _make_user_turn(turn_id, "I want the rover to map temperature.")
    requirement = _make_user_explicit_requirement(
        "req_0000000000000010",
        "The rover shall map temperature.",
        wrong_turn_id,
    )
    requirement_set = {"requirements": [requirement], "requirementSummary": "test"}

    errors = semantic_validate_bundle(
        {"user_turn": user_turn, "requirement_set_content": requirement_set}
    )
    assert any(e.code == "REQ_USER_EXPLICIT_REFERENCE_WRONG_TURN" and e.blocking for e in errors), (
        f"Expected wrong-turn provenance error, got {[e.code for e in errors]}"
    )
