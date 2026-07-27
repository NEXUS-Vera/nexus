#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "setup: preparing Nexus workspace (foundation)"

if command -v python3 >/dev/null 2>&1; then
  echo "setup: python3 $(python3 --version 2>&1)"
else
  echo "setup: python3 not found (optional for foundation)"
fi

if command -v pnpm >/dev/null 2>&1; then
  echo "setup: pnpm $(pnpm --version 2>&1)"
elif command -v npm >/dev/null 2>&1; then
  echo "setup: pnpm not found; npm available ($(npm --version))"
else
  echo "setup: Node/pnpm not found (optional for foundation)"
fi

chmod +x scripts/*.sh 2>/dev/null || true
echo "setup: complete"
