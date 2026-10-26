#!/usr/bin/env bash
# Isolated real FastAPI/SQLite browser acceptance probe; no model key required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHON="${PYTHON:-$(if [[ -x "$ROOT/.venv/bin/python" ]]; then echo "$ROOT/.venv/bin/python"; else command -v python3; fi)}"
export PYTHONPATH="$ROOT/apps/api/src:$ROOT/agents/embedded-systems/src:$ROOT/packages/contracts/src:$ROOT/packages/contracts/generated/python:$ROOT/packages/model-gateway/src:$ROOT/packages/observability/src:$ROOT/packages/persistence/src:$ROOT/packages/board/src:$ROOT/packages/circuit-simulation/src"
RUN_DIR="$(mktemp -d /tmp/nexus-w8-e2e.XXXXXX)"
export NEXUS_STORAGE_BACKEND=sqlite
export NEXUS_DATABASE_URL="sqlite:///$RUN_DIR/nexus.db"
export NEXUS_FILE_STORE_ROOT="$RUN_DIR/files"
export NEXUS_INITIALIZATION_PROVIDER=fixture
export NEXUS_ANALYSIS_USE_STUB=0
export NEXUS_API_CORS_ORIGINS=http://127.0.0.1:15173
export VITE_API_BASE_URL=http://127.0.0.1:18000
export NEXUS_WEB_BASE_URL=http://127.0.0.1:15173
export NEXUS_W8_E2E=1
cleanup() {
  kill "${WEB_PID:-}" 2>/dev/null || true
  wait "${WEB_PID:-}" 2>/dev/null || true
  rm -rf "$RUN_DIR"
}
trap cleanup EXIT
(cd "$ROOT/apps/web"; exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15173 --strictPort) >"$RUN_DIR/web.log" 2>&1 &
WEB_PID=$!
for _ in $(seq 1 60); do
  if curl -sf "$NEXUS_WEB_BASE_URL" >/dev/null; then break; fi
  if ! kill -0 "$WEB_PID" 2>/dev/null; then cat "$RUN_DIR/web.log"; exit 1; fi
  sleep 1
done
curl -sf "$NEXUS_WEB_BASE_URL" >/dev/null
pnpm --filter @nexus/web exec playwright install chromium
pnpm --filter @nexus/web exec playwright test e2e/w8-golden-journey.spec.ts --retries=0 --output="$RUN_DIR/playwright"
