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
from nexus_contracts.validation.semantic_validators import semantic_validate_bundle  # noqa: E402


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
) -> tuple[list[str], list[str]]:
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

    schema_errors: list[str] = []
    artifact_envelopes: list[dict[str, Any]] = []
    requirement_set_content: dict[str, Any] | None = None
    functional_architecture_content: dict[str, Any] | None = None
    vera_response: dict[str, Any] | None = None

    for path in sorted(folder.glob("*.json")):
        payload = _load_json(path)
        filename = path.name
        try:
            if filename == "project.json":
                errs = sorted(
                    validators["project"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "user-turn.json":
                errs = sorted(
                    validators["user-turn"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "turn-route.json":
                errs = sorted(
                    validators["turn-route"].iter_errors(payload), key=lambda e: list(e.path)
                )
                if errs:
                    schema_errors.append(f"{filename}: {[e.message for e in errs[:2]]}")
            elif filename == "workflow-run.json":
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
            elif filename == "validation-issues.json":
                assert isinstance(payload, list)
                for item in payload:
                    errs = sorted(
                        validators["validation-issue"].iter_errors(item), key=lambda e: list(e.path)
                    )
                    if errs:
                        schema_errors.append(f"{filename} item: {[e.message for e in errs[:2]]}")
            elif filename == "open-questions.json":
                assert isinstance(payload, list)
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
        except Exception as exc:  # noqa: BLE001
            schema_errors.append(f"{filename}: exception during validation: {exc}")

    semantic_bundle = {
        "artifact_envelopes": artifact_envelopes,
        "requirement_set_content": requirement_set_content,
        "functional_architecture_content": functional_architecture_content,
        "vera_response": vera_response,
    }
    semantic_errors = [f"{e.code}: {e.message}" for e in semantic_validate_bundle(semantic_bundle)]
    return schema_errors, semantic_errors


def test_all_valid_examples_pass(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    valid_dir = EXAMPLES_DIR / "valid"
    assert valid_dir.exists()
    for folder in sorted([p for p in valid_dir.iterdir() if p.is_dir()]):
        schema_errors, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
        assert not schema_errors, f"Expected no schema errors for {folder}: {schema_errors[:5]}"
        assert not semantic_errors, (
            f"Expected no semantic errors for {folder}: {semantic_errors[:5]}"
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
    assert any(e.startswith("REQ_DUPLICATE_DISPLAY_ID:") for e in semantic_errors)

    # Architecture edges referencing missing nodes
    folder = EXAMPLES_DIR / "invalid" / "07-architecture-edges-missing-nodes"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.startswith("ARCH_EDGE_REFERENCES_MISSING_NODE:") for e in semantic_errors)

    # Requirement coverage referencing missing requirements
    folder = EXAMPLES_DIR / "invalid" / "08-requirement-coverage-missing-requirements"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(
        e.startswith("ARCH_REQUIREMENT_COVERAGE_MISSING_REQUIREMENTS:") for e in semantic_errors
    )

    # Component/part identifiers should not be silently introduced at functional maturity.
    folder = EXAMPLES_DIR / "invalid" / "04-component-specific-architecture-functional-maturity"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.startswith("ARCH_COMPONENT_SELECTION_IN_FUNCTIONAL:") for e in semantic_errors)

    # Inferred requirements must not be labeled as user-explicit.
    folder = EXAMPLES_DIR / "invalid" / "05-inferred-requirement-marked-user-explicit"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.startswith("REQ_SOURCE_INFERRED_MISLABELED:") for e in semantic_errors)


def test_vera_response_forbids_hidden_reasoning_fields(
    schemas_by_id: dict[str, dict[str, Any]], store: dict[str, Any]
) -> None:
    folder = EXAMPLES_DIR / "invalid" / "13-vera-response-hidden-reasoning"
    _, semantic_errors = _validate_bundle_assets(folder, schemas_by_id, store)
    assert any(e.startswith("VERA_HIDDEN_REASONING_FORBIDDEN:") for e in semantic_errors)


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
