"""Runtime schema validation helpers shared by the initialization workflow."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from nexus_contracts.validation.project_package_validator import (
    validate_project_package_bundle,
)
from nexus_contracts.validation.semantic_validators import SemanticValidationError

ROOT = Path(__file__).resolve().parents[6]
SCHEMA_DIR = ROOT / "packages" / "contracts" / "schemas"
INIT_RESULT_SCHEMA_ID = (
    "https://nexus.local/schemas/responses/project-initialization-result.v1.schema.json"
)


@lru_cache(maxsize=1)
def _schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for path in sorted(SCHEMA_DIR.glob("**/*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data
    return store


def validate_initialization_result_schema(payload: dict[str, Any]) -> list[str]:
    store = _schema_store()
    schema = store[INIT_RESULT_SCHEMA_ID]
    resolver = RefResolver.from_schema(schema, store=store, cache_remote=False)
    validator = Draft202012Validator(schema, resolver=resolver)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) if err.path else "$"
        errors.append(f"{path}: {err.message}")
    return errors


def validate_initialization_package(
    package_bundle: dict[str, Any],
) -> list[SemanticValidationError]:
    return validate_project_package_bundle(package_bundle)
