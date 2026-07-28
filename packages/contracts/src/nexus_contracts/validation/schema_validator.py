"""Shared JSON Schema validation utilities for Nexus contracts.

Runtime services and contract fixture scripts should use this module so schema
loading and Draft 2020-12 validation stay in one place. Fixture discovery and
example-folder orchestration remain in scripts/tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

CONTRACTS_DIR = Path(__file__).resolve().parents[3]
SCHEMA_DIR = CONTRACTS_DIR / "schemas"


@dataclass(frozen=True)
class SchemaValidationError:
    code: str
    message: str
    path: str | None


@lru_cache(maxsize=1)
def load_schemas_by_id() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_DIR.glob("**/*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_id = data.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise ValueError(f"Schema missing/invalid $id: {path}")
        schemas[schema_id] = data
    return schemas


def make_resolver(store: dict[str, Any], base_schema: dict[str, Any]) -> RefResolver:
    return RefResolver.from_schema(base_schema, store=store, cache_remote=False)


def make_validator(
    schema: dict[str, Any], store: dict[str, Any] | None = None
) -> Draft202012Validator:
    resolved_store = dict(store) if store is not None else dict(load_schemas_by_id())
    resolver = make_resolver(resolved_store, schema)
    return Draft202012Validator(schema, resolver=resolver)


def validate_against_schema(
    payload: Any,
    schema: dict[str, Any],
    *,
    store: dict[str, Any] | None = None,
) -> list[SchemaValidationError]:
    validator = make_validator(schema, store=store)
    errors: list[SchemaValidationError] = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) if err.path else None
        errors.append(
            SchemaValidationError(
                code="SCHEMA_VALIDATION_FAILED",
                message=str(err.message),
                path=path,
            )
        )
    return errors


def validate_against_schema_id(
    payload: Any,
    schema_id: str,
) -> list[SchemaValidationError]:
    store = load_schemas_by_id()
    if schema_id not in store:
        raise KeyError(f"Unknown schema id: {schema_id}")
    return validate_against_schema(payload, store[schema_id], store=store)


def format_schema_errors(errors: list[SchemaValidationError]) -> list[str]:
    formatted: list[str] = []
    for err in errors:
        path = err.path or "$"
        formatted.append(f"{path}: {err.message}")
    return formatted
