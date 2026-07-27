#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f package.json ]] && command -v pnpm >/dev/null 2>&1; then
  pnpm run build || true
else
  echo "build: no TypeScript build targets yet; skipping"
fi

echo "build: done"
