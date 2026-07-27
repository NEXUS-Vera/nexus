#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

rm -rf \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  .coverage \
  htmlcov \
  coverage \
  dist \
  build \
  **/__pycache__ \
  2>/dev/null || true

find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find . -type d -name '.pytest_cache' -prune -exec rm -rf {} + 2>/dev/null || true

echo "clean: done"
