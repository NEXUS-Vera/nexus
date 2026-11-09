#!/usr/bin/env bash
# Paid opt-in LIVE journey. Do not enable shell tracing: credentials stay in env.
set +x
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHON="${PYTHON:-$(if [[ -x "$ROOT/.venv/bin/python" ]]; then echo "$ROOT/.venv/bin/python"; else command -v python3; fi)}"
export PYTHONPATH="$ROOT/apps/api/src:$ROOT/agents/embedded-systems/src:$ROOT/packages/contracts/src:$ROOT/packages/contracts/generated/python:$ROOT/packages/model-gateway/src:$ROOT/packages/observability/src:$ROOT/packages/persistence/src:$ROOT/packages/board/src:$ROOT/packages/circuit-simulation/src"
# Preflight before starting processes or creating evidence directories.
export NEXUS_MODEL_API_KEY="${NEXUS_MODEL_API_KEY:-${ANTHROPIC_API_KEY:-}}"
[[ -n "$NEXUS_MODEL_API_KEY" ]] || { echo "Missing NEXUS_MODEL_API_KEY or ANTHROPIC_API_KEY" >&2; exit 1; }
command -v pio >/dev/null || command -v platformio >/dev/null || { echo "Missing PlatformIO (pio/platformio)" >&2; exit 1; }
command -v "${NEXUS_WOKWI_CLI:-wokwi-cli}" >/dev/null || { echo "Missing Wokwi CLI (NEXUS_WOKWI_CLI or wokwi-cli)" >&2; exit 1; }
[[ -n "${WOKWI_CLI_TOKEN:-}" ]] || { echo "Missing WOKWI_CLI_TOKEN" >&2; exit 1; }
export NEXUS_MODEL_PROVIDER="${NEXUS_MODEL_PROVIDER:-anthropic}"
export NEXUS_MODEL_NAME="${NEXUS_MODEL_NAME:-claude-sonnet-4-6}"
export NEXUS_MODEL_BASE_URL="${NEXUS_MODEL_BASE_URL:-https://api.anthropic.com}"
export NEXUS_MODEL_TIMEOUT_SECONDS=240
export NEXUS_FIRMWARE_USE_STUB=0
umask 077
RUN_DIR="$(mktemp -d /tmp/nexus-w8-live-e2e.XXXXXX)"
export NEXUS_STORAGE_BACKEND=sqlite
export NEXUS_DATABASE_URL="sqlite:///$RUN_DIR/nexus.db"
export NEXUS_FILE_STORE_ROOT="$RUN_DIR/files"
export NEXUS_INITIALIZATION_PROVIDER=llm
export NEXUS_ANALYSIS_USE_STUB=0
export NEXUS_API_CORS_ORIGINS=http://127.0.0.1:15173
export VITE_API_BASE_URL=http://127.0.0.1:18000
export NEXUS_WEB_BASE_URL=http://127.0.0.1:15173
export NEXUS_W8_LIVE_E2E=1
cleanup() {
  result=$?
  kill "${WEB_PID:-}" 2>/dev/null || true
  wait "${WEB_PID:-}" 2>/dev/null || true
  if [[ "$result" == 0 && -z "${KEEP_RUN_DIR+x}" ]]; then
    rm -rf "$RUN_DIR"
  else
    echo "W8 live evidence retained: $RUN_DIR"
  fi
  exit "$result"
}
trap cleanup EXIT
(cd "$ROOT/apps/web"; exec env -u NEXUS_MODEL_API_KEY -u ANTHROPIC_API_KEY -u WOKWI_CLI_TOKEN node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15173 --strictPort) >"$RUN_DIR/web.log" 2>&1 &
WEB_PID=$!
for _ in $(seq 1 60); do
  if curl -sf "$NEXUS_WEB_BASE_URL" >/dev/null; then break; fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then cat "$RUN_DIR/web.log"; exit 1; fi
  sleep 1
done
curl -sf "$NEXUS_WEB_BASE_URL" >/dev/null
pnpm --filter @nexus/web exec playwright install chromium
pnpm --filter @nexus/web exec playwright test e2e/w8-live-journey.spec.ts --retries=0 --output="$RUN_DIR/playwright"
