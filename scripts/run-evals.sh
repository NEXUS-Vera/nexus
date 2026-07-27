#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Evaluation runners are not implemented yet. Succeed only when no eval runner
# is expected, or when no eval suites claim to be executable.
EVAL_RUNNERS="$(find evals -type f \( -name '*.eval.yaml' -o -name 'run*.py' -o -name 'run*.sh' \) 2>/dev/null | wc -l | tr -d ' ')"

if [[ "$EVAL_RUNNERS" -eq 0 ]]; then
  echo "eval: no evaluation suites implemented yet; skipping"
  exit 0
fi

echo "eval: evaluation files exist but no runner is configured yet" >&2
exit 1
