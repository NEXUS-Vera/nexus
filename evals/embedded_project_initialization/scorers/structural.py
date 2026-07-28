"""Schema- and semantic-validity scoring for a generated initialization package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus_contracts.validation.project_package_validator import (
    validate_project_package_bundle,
)
from nexus_embedded_systems.workflows.project_initialization.materializer import (
    initialization_dict_to_package_bundle,
)
from nexus_embedded_systems.workflows.project_initialization.validation import (
    validate_initialization_result_schema,
)


@dataclass(frozen=True)
class StructuralScore:
    """Whether a generated `ProjectInitializationResult` is structurally valid."""

    passed: bool
    schema_errors: tuple[str, ...] = field(default_factory=tuple)
    blocking_semantic_codes: tuple[str, ...] = field(default_factory=tuple)


def score_structural(result: dict[str, Any]) -> StructuralScore:
    """Validate `result` against the contract schema and package semantics."""

    schema_errors = validate_initialization_result_schema(result)
    bundle = initialization_dict_to_package_bundle(result)
    semantic_errors = validate_project_package_bundle(bundle)
    blocking = sorted({e.code for e in semantic_errors if getattr(e, "blocking", True)})
    return StructuralScore(
        passed=not schema_errors and not blocking,
        schema_errors=tuple(schema_errors),
        blocking_semantic_codes=tuple(blocking),
    )
