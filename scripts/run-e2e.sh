#!/usr/bin/env bash
# Runs Playwright E2E against a local fixture-mode API + web stack.
# Does not require a model API key.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)}"
PYTHON_PATH="apps/api/src:agents/embedded-systems/src:packages/contracts/src:packages/contracts/generated/python:packages/model-gateway/src:packages/observability/src:packages/persistence/src:packages/board/src"

export NEXUS_STORAGE_BACKEND="${NEXUS_STORAGE_BACKEND:-memory}"
export NEXUS_INITIALIZATION_PROVIDER="${NEXUS_INITIALIZATION_PROVIDER:-fixture}"
export NEXUS_API_CORS_ORIGINS="${NEXUS_API_CORS_ORIGINS:-http://127.0.0.1:5173,http://localhost:5173}"
export NEXUS_E2E=1
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8000}"
export NEXUS_WEB_BASE_URL="${NEXUS_WEB_BASE_URL:-http://127.0.0.1:5173}"

EXIT_CODE=0

cleanup() {
  local code="${EXIT_CODE}"
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${WEB_PID:-}" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
  wait "$API_PID" 2>/dev/null || true
  wait "$WEB_PID" 2>/dev/null || true
  exit "$code"
}
trap cleanup EXIT INT TERM

PYTHONPATH="$PYTHON_PATH" "$PYTHON" -m uvicorn nexus_api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
pnpm --filter @nexus/web exec vite --host 127.0.0.1 --port 5173 &
WEB_PID=$!

ready=0
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/healthz >/dev/null && curl -sf http://127.0.0.1:5173 >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "API or web failed to become ready within 60s" >&2
  EXIT_CODE=1
  exit 1
fi

pnpm --filter @nexus/web exec playwright install chromium
set +e
pnpm --filter @nexus/web test:e2e
EXIT_CODE=$?
set -e
exit "$EXIT_CODE"
