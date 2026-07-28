#!/usr/bin/env bash
# Enforce Nexus repository content policy.
# Portable for standard Linux CI shells (bash 3.2+ / macOS).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MAX_FILE_BYTES="${NEXUS_MAX_FILE_BYTES:-1048576}" # 1 MiB
FAILURES=0

fail() {
  echo "POLICY FAIL: $*" >&2
  FAILURES=$((FAILURES + 1))
}

info() {
  echo "POLICY: $*"
}

collect_files() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git ls-files
  else
    find . -type f       ! -path './.git/*'       ! -path './.mypy_cache/*'       ! -path './.ruff_cache/*'       ! -path './.pytest_cache/*'       ! -path './.venv/*'       ! -path './node_modules/*'       ! -path './.pnpm-store/*'       ! -path './__pycache__/*'       ! -path '*/__pycache__/*'       | sed 's|^\./||'
  fi
}

is_allowed_root_md() {
  case "$1" in
    README.md|AGENTS.md|CLAUDE.md|CONTRIBUTING.md|SECURITY.md|CODE_OF_CONDUCT.md|CHANGELOG.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_prohibited_summary_name() {
  local base
  base="$(basename "$1")"
  case "$base" in
    IMPLEMENTATION_SUMMARY.md|PHASE_1_COMPLETE.md|CURRENT_STATUS.md|FINAL_NOTES.md|ARCHITECTURE_NEW.md|FIXES_DONE.md|CLAUDE_SUMMARY.md|PROJECT_PLAN.md|TODO_NOTES.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_allowed_markdown_path() {
  local path="$1"
  local base
  base="$(basename "$path")"

  if [[ "$path" == *.md ]] && [[ "$path" != */* ]]; then
    is_allowed_root_md "$path"
    return $?
  fi

  if [[ "$path" == docs/* ]] && [[ "$path" == *.md ]]; then
    return 0
  fi

  if [[ "$base" == "README.md" ]]; then
    return 0
  fi

  if [[ "$path" == .github/* ]] && [[ "$path" == *.md ]]; then
    return 0
  fi

  return 1
}

FORBIDDEN_DIRS_REGEX='(^|/)(logs|outputs|results|tmp|coverage|dist|build|vector-store|embeddings|model-cache|uploads|generated-notebooks)(/|$)'
SECRET_NAME_REGEX='(^|/)\.env($|\.)|(^|/)(id_rsa|id_dsa|id_ecdsa|id_ed25519)($|\.)|(^|/)(credentials|service-account.*)\.json$|(^|/).*(\.pem|\.p12|\.pfx)$'

FILE_COUNT="$(collect_files | wc -l | tr -d " ")"
info "checking ${FILE_COUNT} files (max size ${MAX_FILE_BYTES} bytes)"

while IFS= read -r path; do
  [[ -n "$path" ]] || continue

  if echo "$path" | grep -Eq "$FORBIDDEN_DIRS_REGEX"; then
    fail "forbidden generated-artifact path tracked: $path"
  fi

  if echo "$path" | grep -Eq '(^|/)\.env($|\..*)'; then
    if [[ "$(basename "$path")" != ".env.example" ]]; then
      fail "tracked env file not allowed: $path"
    fi
  fi

  if echo "$path" | grep -Eq "$SECRET_NAME_REGEX"; then
    if [[ "$(basename "$path")" != ".env.example" ]]; then
      fail "suspicious secret filename tracked: $path"
    fi
  fi

  if is_prohibited_summary_name "$path"; then
    fail "prohibited summary/completion filename: $path"
  fi

  if [[ "$path" == *.md ]]; then
    if ! is_allowed_markdown_path "$path"; then
      fail "markdown file outside approved locations: $path"
    fi
    if [[ "$path" != */* ]] && ! is_allowed_root_md "$path"; then
      fail "unapproved root markdown file: $path"
    fi
  fi

  if [[ -f "$path" ]]; then
    size="$(wc -c < "$path" | tr -d " ")"
    if [[ "$size" -gt "$MAX_FILE_BYTES" ]]; then
      fail "file exceeds size threshold (${size} > ${MAX_FILE_BYTES}): $path"
    fi
  fi
done < <(collect_files)

INDEX="docs/index.md"
if [[ ! -f "$INDEX" ]]; then
  fail "missing documentation index: $INDEX"
else
  while IFS= read -r doc; do
    [[ -n "$doc" ]] || continue
    rel="${doc#docs/}"
    base="$(basename "$doc")"
    if ! grep -Eq "$rel|$doc|$base" "$INDEX"; then
      fail "durable doc not listed in docs/index.md: $doc"
    fi
  done < <(find docs -type f -name "*.md" ! -path "docs/index.md" | sort)
fi

if [[ "$FAILURES" -gt 0 ]]; then
  echo "Repository policy check failed with $FAILURES issue(s)." >&2
  exit 1
fi

# Also run the shared secret-pattern scan so local `make policy` catches
# the same identifier-style false positives as the Security workflow.
chmod +x scripts/scan-secret-patterns.sh
./scripts/scan-secret-patterns.sh

echo "Repository policy check passed."
