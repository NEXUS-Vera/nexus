"""Runtime schema validation helpers for the initialization workflow."""

from __future__ import annotations

from typing import Any

from nexus_contracts.validation.project_package_validator import (
    validate_project_package_bundle,
)
from nexus_contracts.validation.schema_validator import (
    format_schema_errors,
    validate_against_schema_id,
)
from nexus_contracts.validation.semantic_validators import SemanticValidationError

INIT_RESULT_SCHEMA_ID = (
    "https://nexus.local/schemas/responses/project-initialization-result.v1.schema.json"
)


def validate_initialization_result_schema(payload: dict[str, Any]) -> list[str]:
    return format_schema_errors(validate_against_schema_id(payload, INIT_RESULT_SCHEMA_ID))


def validate_initialization_package(
    package_bundle: dict[str, Any],
) -> list[SemanticValidationError]:
    return validate_project_package_bundle(package_bundle)
