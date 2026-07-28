#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNNER="evals/embedded_project_initialization/runners/run_eval.py"

if [[ ! -f "$RUNNER" ]]; then
  echo "eval: no evaluation suites implemented yet; skipping"
  exit 0
fi

if command -v python3.13 >/dev/null 2>&1; then
  PYTHON="python3.13"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="python3.12"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON="python3.11"
else
  PYTHON="python3"
fi

export PYTHONPATH="apps/api/src:agents/embedded-systems/src:packages/contracts/src:packages/contracts/generated/python:packages/model-gateway/src:packages/observability/src"

# `make check` only runs the embedded-project-initialization eval suite in
# fake mode: it exercises the real provider pipeline against a scripted
# `FakeModelGateway` and never requires `NEXUS_MODEL_API_KEY` or a live model.
echo "eval: running embedded-project-initialization suite (provider=fake)"
"$PYTHON" -m evals.embedded_project_initialization.runners.run_eval --provider fake
