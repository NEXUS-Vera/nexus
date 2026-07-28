#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-all}"

TEST_LIST="$(find agents apps packages tools -type f -name "test_*.py" 2>/dev/null | sort || true)"

if [[ -z "${TEST_LIST}" ]]; then
  echo "test (${MODE}): no Python tests found; skipping"
  exit 0
fi

if ! command -v pytest >/dev/null 2>&1 && ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "test (${MODE}): pytest not installed; cannot run existing tests" >&2
  exit 1
fi

run_pytest() {
  # Prefer Python 3.11+ when available.
  if command -v python3.13 >/dev/null 2>&1; then
    python3.13 -m pytest "$@"
  elif command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m pytest "$@"
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m pytest "$@"
  elif command -v pytest >/dev/null 2>&1; then
    pytest "$@"
  else
    python3 -m pytest "$@"
  fi
}

case "$MODE" in
  unit)
    UNIT_LIST="$(echo "$TEST_LIST" | grep -v "/integration/" | grep -v "/tests/integration/" || true)"
    if [[ -z "${UNIT_LIST}" ]]; then
      echo "test (unit): no unit tests found; skipping"
      exit 0
    fi
    # shellcheck disable=SC2086
    run_pytest $UNIT_LIST
    ;;
  integration)
    INT_LIST="$(echo "$TEST_LIST" | grep -E "/(tests/)?integration/" || true)"
    if [[ -z "${INT_LIST}" ]]; then
      echo "test (integration): no integration tests found; skipping"
      exit 0
    fi
    # shellcheck disable=SC2086
    run_pytest $INT_LIST
    ;;
  *)
    # shellcheck disable=SC2086
    run_pytest $TEST_LIST
    ;;
esac

echo "test (${MODE}): done"
