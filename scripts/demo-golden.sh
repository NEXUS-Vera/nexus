#!/usr/bin/env bash
# Developer demo: fixture generation, kernel execution and deterministic evidence.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="${PYTHONPATH-apps/api/src:agents/embedded-systems/src:packages/board/src:packages/circuit-simulation/src:packages/contracts/src:packages/contracts/generated/python:packages/model-gateway/src:packages/observability/src:packages/persistence/src:packages/board/tests}"
export NEXUS_INITIALIZATION_PROVIDER=fixture
unset NEXUS_MODEL_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
export NEXUS_EXECUTION_RUNTIME=process
export NEXUS_DEMO_LIVE_COMPILE=1
export NEXUS_FIRMWARE_USE_STUB=1 NEXUS_ANALYSIS_USE_STUB=0
DEMO_DIR="$(mktemp -d /tmp/nexus-demo-golden.XXXXXX)"
echo "Fixture/fake gates: initialization and firmware stub (no live build evidence)."
echo "Real deterministic gate: Python RMS analysis on synthetic CSV, accepted evidence."
echo "Live Wokwi: GAP — not executed by this no-key demo."
echo "Demo artifacts and build logs: $DEMO_DIR"
"${PYTHON:-python3}" -m pytest packages/board/tests/test_phase16i_golden_e2e.py \
  -k 'g1_fixture_full_system or local_platformio or golden_prompt or telemetry_parses' \
  -q -s --basetemp="$DEMO_DIR"
echo "Demo assertions passed. Live gaps above remain gaps, not passes."
