#!/usr/bin/env bash
set -euo pipefail

# Find a reasonable base to diff against (main if available; otherwise first commit)
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  BASE="$(git merge-base HEAD origin/main)"
else
  BASE="$(git rev-list --max-parents=0 HEAD | tail -n1)"
fi

mapfile -t PY_CHANGED < <(git diff --name-only --diff-filter=ACMRT "${BASE}"...HEAD | grep -E '\.py$' || true)

if [[ ${#PY_CHANGED[@]} -eq 0 ]]; then
  echo "No Python changes; skipping QA."
  exit 0
fi

echo "Changed Python files:"
printf ' - %s\n' "${PY_CHANGED[@]}"

# Lint
ruff check "${PY_CHANGED[@]}"

# Format check
black --check "${PY_CHANGED[@]}"

# Types (lightweight defaults)
mypy --pretty "${PY_CHANGED[@]}"