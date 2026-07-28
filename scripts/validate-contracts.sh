#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d "packages/contracts/schemas" ]]; then
  echo "contracts: missing schema directory" >&2
  exit 1
fi

python3 "packages/contracts/scripts/validate_contract_fixtures.py"

echo "contracts: done"
