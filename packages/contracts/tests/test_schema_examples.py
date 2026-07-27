"""Contract example validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
EXAMPLES_DIR = ROOT / "examples"

MAPPING = {
    "task-contract": "task-contract.v1.schema.json",
    "agent-result": "agent-result.v1.schema.json",
    "board-update": "board-update.v1.schema.json",
    "evidence-record": "evidence-record.v1.schema.json",
}


def _load(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected object in {path}")
    return data


def test_schemas_are_valid_json() -> None:
    schemas = list(SCHEMA_DIR.glob("*.schema.json"))
    assert schemas, "expected placeholder schemas"
    for path in schemas:
        data = _load(path)
        required = data.get("required", [])
        assert isinstance(required, list)
        assert "schemaVersion" in required or "properties" in data


def test_examples_conform_to_schemas() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    Draft202012Validator = jsonschema.Draft202012Validator

    schemas = {path.name: _load(path) for path in SCHEMA_DIR.glob("*.schema.json")}
    examples = list(EXAMPLES_DIR.glob("*.json"))
    assert examples, "expected contract examples"

    for example_path in examples:
        schema_name = None
        for prefix, name in MAPPING.items():
            if example_path.name.startswith(prefix):
                schema_name = name
                break
        assert schema_name is not None, f"unmapped example: {example_path.name}"
        validator = Draft202012Validator(schemas[schema_name])
        errors = sorted(validator.iter_errors(_load(example_path)), key=lambda e: list(e.path))
        assert not errors, f"{example_path.name}: {[e.message for e in errors]}"
