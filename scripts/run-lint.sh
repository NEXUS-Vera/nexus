#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

has_python_sources() {
  find agents packages tools scripts -type f -name '*.py' -print -quit 2>/dev/null | grep -q .
}

if has_python_sources; then
  if command -v ruff >/dev/null 2>&1; then
    ruff check agents packages tools scripts
  elif python3 -c "import ruff" >/dev/null 2>&1; then
    python3 -m ruff check agents packages tools scripts
  else
    echo "lint: ruff not installed; skipping Python lint"
  fi
else
  echo "lint: no Python sources found; skipping"
fi

# Validate JSON / YAML syntax for foundational configs
python3 - <<'PY'
import json
import sys
from pathlib import Path

errors = 0
root = Path(".")

for path in root.rglob("*.json"):
    if any(part in {".git", "node_modules", ".venv"} for part in path.parts):
        continue
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"lint: invalid JSON: {path}: {exc}", file=sys.stderr)
        errors += 1

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

if yaml is not None:
    for path in list(root.rglob("*.yml")) + list(root.rglob("*.yaml")):
        if any(part in {".git", "node_modules", ".venv"} for part in path.parts):
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"lint: invalid YAML: {path}: {exc}", file=sys.stderr)
            errors += 1
else:
    print("lint: PyYAML not installed; skipping YAML parse validation")

sys.exit(1 if errors else 0)
PY

if [[ -f package.json ]] && command -v pnpm >/dev/null 2>&1; then
  pnpm run lint || true
fi

echo "lint: done"
