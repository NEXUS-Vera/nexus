#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d "packages/contracts/schemas" ]]; then
  echo "contracts: missing schema directory" >&2
  exit 1
fi

python3 "packages/contracts/scripts/validate_contract_fixtures.py"

# Prefer a modern Python for generation check when available.
PYTHON_BIN="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)"
"$PYTHON_BIN" "packages/contracts/scripts/generate_contract_types.py" --check

echo "contracts: done"
