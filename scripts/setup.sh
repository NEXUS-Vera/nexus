#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "setup: preparing Nexus workspace (foundation)"

PYTHON="${PYTHON:-$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3 || true)}"
if [[ -z "$PYTHON" ]]; then
  echo "setup: Python 3.11+ is required" >&2
  exit 1
fi
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "setup: Python 3.11+ is required")'

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$PYTHON" -m venv "$ROOT/.venv"
fi
echo "setup: installing Python dev dependencies into .venv"
"$ROOT/.venv/bin/python" -m pip install '.[dev]'

if command -v pnpm >/dev/null 2>&1; then
  echo "setup: pnpm $(pnpm --version 2>&1)"
elif command -v npm >/dev/null 2>&1; then
  echo "setup: pnpm not found; npm available ($(npm --version))"
else
  echo "setup: Node/pnpm not found (optional for foundation)"
fi

chmod +x scripts/*.sh 2>/dev/null || true
echo "setup: complete"
