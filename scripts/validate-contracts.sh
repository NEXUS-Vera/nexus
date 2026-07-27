#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCHEMA_DIR="packages/contracts/schemas"
EXAMPLES_DIR="packages/contracts/examples"

if [[ ! -d "$SCHEMA_DIR" ]]; then
  echo "contracts: missing schema directory" >&2
  exit 1
fi

python3 - <<'PY'
"""Validate contract schemas and example payloads."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(".")
SCHEMA_DIR = ROOT / "packages" / "contracts" / "schemas"
EXAMPLES_DIR = ROOT / "packages" / "contracts" / "examples"

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("contracts: jsonschema not installed; validating JSON syntax only")
    errors = 0
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            print(f"contracts: schema ok (syntax): {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"contracts: invalid schema JSON {path}: {exc}", file=sys.stderr)
            errors += 1
    if EXAMPLES_DIR.exists():
        for path in sorted(EXAMPLES_DIR.glob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
                print(f"contracts: example ok (syntax): {path}")
            except Exception as exc:  # noqa: BLE001
                print(f"contracts: invalid example JSON {path}: {exc}", file=sys.stderr)
                errors += 1
    sys.exit(1 if errors else 0)

errors = 0
schemas: dict[str, dict] = {}

for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        print(f"contracts: schema ok: {path}")
    except Exception as exc:  # noqa: BLE001
        print(f"contracts: schema validation failed for {path}: {exc}", file=sys.stderr)
        errors += 1

# Map example filename prefixes to schemas
mapping = {
    "task-contract": "task-contract.v1.schema.json",
    "agent-result": "agent-result.v1.schema.json",
    "board-update": "board-update.v1.schema.json",
    "evidence-record": "evidence-record.v1.schema.json",
}

if EXAMPLES_DIR.exists():
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"contracts: invalid example JSON {path}: {exc}", file=sys.stderr)
            errors += 1
            continue

        schema_name = None
        for prefix, name in mapping.items():
            if path.name.startswith(prefix):
                schema_name = name
                break
        if schema_name is None or schema_name not in schemas:
            print(f"contracts: no schema mapping for example {path}", file=sys.stderr)
            errors += 1
            continue

        validator = Draft202012Validator(schemas[schema_name])
        issues = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if issues:
            for issue in issues:
                print(f"contracts: example {path} failed: {issue.message}", file=sys.stderr)
            errors += 1
        else:
            print(f"contracts: example ok: {path}")

sys.exit(1 if errors else 0)
PY

# Run pytest contract tests when available
if [[ -f packages/contracts/tests/test_schema_examples.py ]]; then
  if command -v pytest >/dev/null 2>&1; then
    pytest packages/contracts/tests/test_schema_examples.py
  elif python3 -c "import pytest" >/dev/null 2>&1; then
    python3 -m pytest packages/contracts/tests/test_schema_examples.py
  else
    echo "contracts: pytest not installed; schema script validation is sufficient for foundation"
  fi
fi

echo "contracts: done"
