"""Schema round-trip tests for ArtifactEntityReference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, RefResolver, ValidationError

CONTRACTS_DIR = Path(__file__).resolve().parents[1]
SCHEMA_DIR = CONTRACTS_DIR / "schemas"


def _load_schemas_by_id() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for path in SCHEMA_DIR.glob("**/*.schema.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data
    return store


def _validator(schema_id: str) -> Draft202012Validator:
    store = _load_schemas_by_id()
    schema = store[schema_id]
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def test_artifact_entity_reference_round_trip() -> None:
    validator = _validator(
        "https://nexus.local/schemas/common/artifact-entity-reference.v1.schema.json"
    )
    payload = {
        "schemaVersion": "1.0.0",
        "artifactId": "art_03GREENHOUSEELEC0000000000000001",
        "artifactType": "electrical-architecture",
        "entityType": "electrical-node",
        "entityId": "enode_03GREENHOUSEMCU00000000000001",
        "displayLabel": "Greenhouse MCU",
    }
    validator.validate(payload)


def test_artifact_entity_reference_requires_core_fields() -> None:
    validator = _validator(
        "https://nexus.local/schemas/common/artifact-entity-reference.v1.schema.json"
    )
    with pytest.raises(ValidationError):
        validator.validate(
            {
                "schemaVersion": "1.0.0",
                "artifactId": "art_03GREENHOUSEELEC0000000000000001",
                "artifactType": "electrical-architecture",
            }
        )


def test_derived_fact_provenance_round_trip() -> None:
    validator = _validator(
        "https://nexus.local/schemas/common/derived-fact-provenance.v1.schema.json"
    )
    payload = {
        "schemaVersion": "1.0.0",
        "sourceType": "fixture",
        "derivedFromIds": ["cand_03GREENHOUSEMCU000000000001"],
        "sourceReference": "fixture:greenhouse-mcu",
        "notes": "Derived from fixture candidate specifications.",
    }
    validator.validate(payload)


def test_derived_fact_provenance_accepts_evidence_reference() -> None:
    validator = _validator(
        "https://nexus.local/schemas/common/derived-fact-provenance.v1.schema.json"
    )
    payload = {
        "schemaVersion": "1.0.0",
        "sourceType": "manufacturer-datasheet",
        "sourceReference": {
            "schemaVersion": "1.0.0",
            "evidenceId": "ev_datasheet_bme280",
            "sourceType": "document",
            "sourceId": "doc_bme280",
            "evidenceStrength": "direct",
        },
    }
    validator.validate(payload)
