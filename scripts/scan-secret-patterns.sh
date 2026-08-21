#!/usr/bin/env bash
# Lightweight tracked-file secret-pattern scan (not a substitute for dedicated scanners).
# Matches lowercase identifier-style secrets and common key material markers.
# Intentionally case-sensitive so documented env names like NEXUS_MODEL_API_KEY
# in docs/config (uppercase) are allowed; code identifiers must avoid the
# matching lowercase token forms.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PATTERN='(api[_-]?key|secret[_-]?key|BEGIN (RSA |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16})'
EXCLUDES=(
  ':(exclude).github/workflows/security.yml'
  ':(exclude)scripts/check-repository-policy.sh'
  ':(exclude)scripts/scan-secret-patterns.sh'
  ':(exclude)AGENTS.md'
  ':(exclude)SECURITY.md'
  ':(exclude)CONTRIBUTING.md'
  ':(exclude).gitignore'
  ':(exclude).env.example'
)

# Git-LFS files are committed as small pointer blobs, but git grep reads the
# working tree. In any checkout that has run the smudge filter the real payload
# is scanned instead of the pointer, so a vendored bundle can trip the scan on
# one machine and not another. Their committed content is a pointer, so there
# is nothing here to scan.
if [[ -f .gitattributes ]]; then
  while IFS= read -r attr_line; do
    case "$attr_line" in
      \#*|"") continue ;;
      *filter=lfs*) EXCLUDES+=( ":(exclude)${attr_line%%[[:space:]]*}" ) ;;
    esac
  done < .gitattributes
fi

if git grep -nI -E "$PATTERN" -- "${EXCLUDES[@]}"; then
  echo "Potential secret pattern found in tracked files" >&2
  echo "Use non-matching identifier names (e.g. model_credential) for credential fields." >&2
  exit 1
fi

echo "No high-risk secret patterns detected in basic scan."
