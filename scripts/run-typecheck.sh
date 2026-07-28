#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY_FILES="$(find agents apps packages tools scripts -type f -name '*.py' \
  ! -path '*/generated/*' \
  ! -path '*/.venv/*' \
  ! -path '*/node_modules/*' \
  2>/dev/null | sort || true)"

if [[ -z "${PY_FILES}" ]]; then
  echo "typecheck: no Python sources found; skipping"
else
  if command -v pyright >/dev/null 2>&1; then
    # Limit to existing Python files so empty placeholder packages do not fail.
    # shellcheck disable=SC2086
    pyright $PY_FILES
  elif command -v mypy >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    mypy $PY_FILES
  else
    echo "typecheck: pyright/mypy not installed; skipping Python typecheck"
  fi
fi

if [[ -f package.json ]] && command -v pnpm >/dev/null 2>&1; then
  pnpm run typecheck
fi

echo "typecheck: done"
