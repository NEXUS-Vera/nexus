#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FORMAT_CHECK="${FORMAT_CHECK:-0}"

has_python_sources() {
  find agents packages tools scripts -type f -name '*.py' 2>/dev/null | grep -q .
}

if has_python_sources; then
  if command -v ruff >/dev/null 2>&1; then
    if [[ "$FORMAT_CHECK" == "1" ]]; then
      ruff format --check agents packages tools scripts
    else
      ruff format agents packages tools scripts
    fi
  elif python3 -c "import ruff" >/dev/null 2>&1; then
    if [[ "$FORMAT_CHECK" == "1" ]]; then
      python3 -m ruff format --check agents packages tools scripts
    else
      python3 -m ruff format agents packages tools scripts
    fi
  else
    echo "format: ruff not installed; skipping Python format"
  fi
else
  echo "format: no Python sources found; skipping"
fi

if [[ -f package.json ]] && command -v pnpm >/dev/null 2>&1; then
  if [[ "$FORMAT_CHECK" == "1" ]]; then
    echo "format: TypeScript format check deferred to package scripts when present"
  else
    pnpm run format || true
  fi
else
  echo "format: no TypeScript format tooling available; skipping"
fi

echo "format: done"
