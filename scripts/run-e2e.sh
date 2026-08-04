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

# Every route is behind the session token, `/healthz` included - it reports the
# storage backend and the initialization provider, so it is not public. This
# stack therefore mints its own token rather than relying on the published
# development fallback, and hands the same value to the browser client through
# `VITE_API_SESSION_TOKEN` so the page authenticates the way the shipped
# renderer does.
export NEXUS_API_SESSION_TOKEN="${NEXUS_API_SESSION_TOKEN:-$("$PYTHON" -c 'import secrets; print(secrets.token_hex(32))')}"
export VITE_API_SESSION_TOKEN="$NEXUS_API_SESSION_TOKEN"

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
  if curl -sf -H "Authorization: Bearer ${NEXUS_API_SESSION_TOKEN}" \
      http://127.0.0.1:8000/healthz >/dev/null &&
    curl -sf http://127.0.0.1:5173 >/dev/null; then
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

# The shell suite launches a real Electron process, so it needs a display. It
# also needs no API: it spawns its own fixture sidecar.
run_desktop_e2e() {
  local runner=(pnpm --filter @nexus/desktop test:e2e)
  if [[ "$(uname -s)" == "Linux" ]]; then
    if ! command -v xvfb-run >/dev/null 2>&1; then
      echo "xvfb-run is required to run the Electron shell suite on Linux (apt-get install xvfb)" >&2
      return 1
    fi
    runner=(xvfb-run --auto-servernum "${runner[@]}")
  fi

  "${runner[@]}"
}

pnpm --filter @nexus/web exec playwright install chromium
set +e
pnpm --filter @nexus/web test:e2e
WEB_EXIT_CODE=$?
set -e

# Run regardless of how the web suite went, and combine the results afterwards.
# The two suites share no state, so letting a web failure - a flaky assertion
# against the live stack is enough - stand the shell suite down would drop the
# preload-bridge surface, the sqlite backend and the data directory from the
# run's coverage while the log said only that the web suite failed.
set +e
run_desktop_e2e
DESKTOP_EXIT_CODE=$?
set -e

if [[ "$WEB_EXIT_CODE" -ne 0 ]]; then
  echo "e2e: web suite failed (exit ${WEB_EXIT_CODE})" >&2
fi
if [[ "$DESKTOP_EXIT_CODE" -ne 0 ]]; then
  echo "e2e: desktop shell suite failed (exit ${DESKTOP_EXIT_CODE})" >&2
fi

if [[ "$WEB_EXIT_CODE" -ne 0 ]]; then
  EXIT_CODE="$WEB_EXIT_CODE"
else
  EXIT_CODE="$DESKTOP_EXIT_CODE"
fi

exit "$EXIT_CODE"
