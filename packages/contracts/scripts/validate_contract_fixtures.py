from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
SCHEMA_DIR = CONTRACTS_DIR / "schemas"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"

SEMANTIC_SRC = CONTRACTS_DIR / "src"
sys.path.insert(0, str(SEMANTIC_SRC))

from nexus_contracts.validation.schema_validator import (  # noqa: E402
    SchemaValidationError,
    load_schemas_by_id,
    make_resolver,
)

# Fixture filenames validated against a single root schema, without expansion into the
# cross-record semantic bundle.
RECORD_SCHEMA_IDS_BY_FILENAME: dict[str, str] = {
    "firmware-patch-proposal.json": (
        "https://nexus.local/schemas/workspaces/firmware-patch-proposal.v1.schema.json"
    ),
    "workspace-file.json": "https://nexus.local/schemas/workspaces/workspace-file.v1.schema.json",
    "execution-command-spec.json": "https://nexus.local/schemas/executions/execution-command-spec.v1.schema.json",
    "execution-job.json": "https://nexus.local/schemas/executions/execution-job.v1.schema.json",
    "execution-log-chunk.json": "https://nexus.local/schemas/executions/execution-log-chunk.v1.schema.json",
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

# Package wrappers that carry a full project package inline and are therefore also
# expanded into the semantic bundle.
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


def _load_schemas() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    schemas_by_id = dict(load_schemas_by_id())
    schemas_by_filename: dict[str, Any] = {}
    for path in _iter_schema_files():
        data = _load_json(path)
        schemas_by_filename[path.name] = data
    return schemas_by_id, schemas_by_filename


def _validate_schema_definitions(schemas_by_id: dict[str, dict[str, Any]]) -> None:
    for _schema_id, schema in sorted(schemas_by_id.items(), key=lambda x: x[0]):
        Draft202012Validator.check_schema(schema)


def _semantic_validate_bundle(bundle: dict[str, Any]) -> list[Any]:
    # Local import to keep module import order stable for linters.
    from nexus_contracts.validation.semantic_validators import semantic_validate_bundle as _impl

    return _impl(bundle)


def _make_resolver(store: dict[str, Any], base_schema: dict[str, Any]) -> Any:
    return make_resolver(store, base_schema)


def _validate_json_against_schema(
    validator: Draft202012Validator, payload: Any
) -> list[SchemaValidationError]:
    errors: list[SchemaValidationError] = []
    for e in sorted(validator.iter_errors(payload), key=lambda err: list(err.path)):
        path = ".".join([str(p) for p in e.path]) if e.path else None
        errors.append(
            SchemaValidationError(
                code="SCHEMA_VALIDATION_FAILED",
                message=str(e.message),
                path=path,
            )
        )
    return errors


def _artifact_content_and_type(
    artifact_envelope: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(artifact_envelope, dict):
        return None, None
    artifact_type = artifact_envelope.get("artifactType")
    content = artifact_envelope.get("content")
    if isinstance(content, dict):
        return artifact_type, content
    return artifact_type, None


def _validate_fixture_folder(folder: Path, expect_valid: bool) -> None:
    schemas_by_id, _ = _load_schemas()
    store = dict(schemas_by_id)

    # Root schemas used for this phase.
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

    root_validators: dict[str, Draft202012Validator] = {}

    def v(schema_name: str, schema: dict[str, Any]) -> Draft202012Validator:
        if schema_name not in root_validators:
            resolver = _make_resolver(store=store, base_schema=schema)
            root_validators[schema_name] = Draft202012Validator(schema, resolver=resolver)
        return root_validators[schema_name]

    # Validate every known file in the fixture folder.
    schema_errors: list[str] = []

    artifact_envelopes: list[dict[str, Any]] = []
    requirement_set_content: dict[str, Any] | None = None
    functional_architecture_content: dict[str, Any] | None = None
    next_action_content: dict[str, Any] | None = None
    project: dict[str, Any] | None = None
    user_turn: dict[str, Any] | None = None
    turn_route: dict[str, Any] | None = None
    workflow_run: dict[str, Any] | None = None
    validation_issues: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []
    vera_response: dict[str, Any] | None = None

    for file_path in sorted(folder.glob("*.json")):
        filename = file_path.name
        payload = _load_json(file_path)

        try:
            if filename in PACKAGE_WRAPPER_SCHEMA_IDS_BY_FILENAME:
                if not isinstance(payload, dict):
                    raise TypeError(f"{filename} must be an object")
                wrapper_schema_id = PACKAGE_WRAPPER_SCHEMA_IDS_BY_FILENAME[filename]
                errors = _validate_json_against_schema(
                    v(filename, schemas_by_id[wrapper_schema_id]),
                    payload,
                )
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
                # Expand wrapper into package fields for semantic checks when present.
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
                        artifact_type, content = _artifact_content_and_type(art)
                        if artifact_type == "requirement-set" and content is not None:
                            requirement_set_content = content
                        if artifact_type == "functional-architecture" and content is not None:
                            functional_architecture_content = content
                        if artifact_type == "next-action" and content is not None:
                            next_action_content = content
            elif filename == "project.json":
                if not isinstance(payload, dict):
                    raise TypeError("project.json must be an object")
                project = payload
                errors = _validate_json_against_schema(v("project", project_schema), payload)
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            elif filename == "user-turn.json":
                if not isinstance(payload, dict):
                    raise TypeError("user-turn.json must be an object")
                user_turn = payload
                errors = _validate_json_against_schema(v("user-turn", user_turn_schema), payload)
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            elif filename == "turn-route.json":
                if not isinstance(payload, dict):
                    raise TypeError("turn-route.json must be an object")
                turn_route = payload
                errors = _validate_json_against_schema(v("turn-route", turn_route_schema), payload)
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            elif filename == "workflow-run.json":
                if not isinstance(payload, dict):
                    raise TypeError("workflow-run.json must be an object")
                workflow_run = payload
                errors = _validate_json_against_schema(
                    v("workflow-run", workflow_run_schema), payload
                )
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            elif filename.endswith("-artifact.json"):
                if not isinstance(payload, dict):
                    raise TypeError(f"Expected object for artifact: {filename}")
                artifact_envelopes.append(payload)
                errors = _validate_json_against_schema(
                    v("artifact", artifact_union_schema), payload
                )
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
                artifact_type, content = _artifact_content_and_type(payload)
                if artifact_type == "requirement-set" and content is not None:
                    requirement_set_content = content
                if artifact_type == "functional-architecture" and content is not None:
                    functional_architecture_content = content
                if artifact_type == "next-action" and content is not None:
                    next_action_content = content
            elif filename == "validation-issues.json":
                if not isinstance(payload, list):
                    raise TypeError("validation-issues.json must be an array")
                validation_issues = payload
                for i, item in enumerate(payload):
                    errors = _validate_json_against_schema(
                        v(f"validation-issue[{i}]", validation_issue_schema), item
                    )
                    if errors:
                        message_snippet = [e.message for e in errors[:2]]
                        schema_errors.append(
                            f"{filename}[{i}]: {len(errors)} errors: {message_snippet}"
                        )
            elif filename == "open-questions.json":
                if not isinstance(payload, list):
                    raise TypeError("open-questions.json must be an array")
                open_questions = payload
                for i, item in enumerate(payload):
                    errors = _validate_json_against_schema(
                        v(f"open-question[{i}]", open_question_schema), item
                    )
                    if errors:
                        message_snippet = [e.message for e in errors[:2]]
                        schema_errors.append(
                            f"{filename}[{i}]: {len(errors)} errors: {message_snippet}"
                        )
            elif filename == "vera-response.json":
                if not isinstance(payload, dict):
                    raise TypeError("vera-response.json must be an object")
                vera_response = payload
                errors = _validate_json_against_schema(
                    v("vera-response", vera_response_schema), payload
                )
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            elif filename in RECORD_SCHEMA_IDS_BY_FILENAME:
                if not isinstance(payload, dict):
                    raise TypeError(f"{filename} must be an object")
                record_schema_id = RECORD_SCHEMA_IDS_BY_FILENAME[filename]
                errors = _validate_json_against_schema(
                    v(filename, schemas_by_id[record_schema_id]), payload
                )
                if errors:
                    schema_errors.append(
                        f"{filename}: {len(errors)} errors: {[e.message for e in errors[:2]]}"
                    )
            else:
                # Ignore unrelated JSON files.
                continue
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
    semantic_errors_items = _semantic_validate_bundle(semantic_bundle)
    allowed_non_blocking_warning_codes = {
        "TECHNOLOGY_LEVEL_TERM_IN_FUNCTIONAL_ARCHITECTURE",
        "REQ_USER_EXPLICIT_AMBIGUOUS_SUPPORT",
    }

    blocking_semantic_errors: list[str] = []
    nonblocking_semantic_errors: list[str] = []
    unexpected_nonblocking_semantic_errors: list[str] = []
    for err in semantic_errors_items:
        rendered = f"{err.code}: {err.message}"
        if getattr(err, "blocking", True):
            blocking_semantic_errors.append(rendered)
        else:
            if err.code in allowed_non_blocking_warning_codes:
                nonblocking_semantic_errors.append(rendered)
            else:
                unexpected_nonblocking_semantic_errors.append(rendered)

    if expect_valid:
        if schema_errors or blocking_semantic_errors or unexpected_nonblocking_semantic_errors:
            raise AssertionError(
                f"Expected valid fixture but found errors in {folder}.\n"
                f"Schema errors: {schema_errors[:5]}\n"
                f"Semantic blocking errors: {blocking_semantic_errors[:5]}\n"
                f"Semantic unexpected warnings: {unexpected_nonblocking_semantic_errors[:5]}"
            )
    else:
        if not schema_errors and not semantic_errors_items:
            raise AssertionError(
                "Expected invalid fixture to fail but it passed schema+semantic validation: "
                f"{folder}"
            )


def main() -> None:
    schemas_by_id, _ = _load_schemas()
    _validate_schema_definitions(schemas_by_id)

    valid_dir = EXAMPLES_DIR / "valid"
    invalid_dir = EXAMPLES_DIR / "invalid"

    if not valid_dir.exists():
        raise SystemExit(f"Missing valid fixtures directory: {valid_dir}")
    if not invalid_dir.exists():
        raise SystemExit(f"Missing invalid fixtures directory: {invalid_dir}")

    valid_folders = sorted([p for p in valid_dir.iterdir() if p.is_dir()])
    invalid_folders = sorted([p for p in invalid_dir.iterdir() if p.is_dir()])

    for folder in valid_folders:
        _validate_fixture_folder(folder, expect_valid=True)

    for folder in invalid_folders:
        _validate_fixture_folder(folder, expect_valid=False)

    print("contracts: ok")


if __name__ == "__main__":
    main()
