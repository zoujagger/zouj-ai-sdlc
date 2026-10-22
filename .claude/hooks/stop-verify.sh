#!/usr/bin/env bash
# Stop: enforce the definition of done (CLAUDE.md). If the working tree changed, `make check` must pass.
# Exit 2 sends the failure back to Claude so it keeps working. A second consecutive stop is allowed through.
# When make check is green, the /fix test lock is released.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
[[ "$(json_get stop_hook_active <<<"$input" 2>/dev/null)" == "true" ]] && exit 0
[[ "${SKIP_STOP_VERIFY:-0}" == "1" ]] && exit 0
command -v make >/dev/null 2>&1 || { echo "stop-verify: make not installed, skipping definition-of-done check" >&2; exit 0; }

lock=.claude/state/test-lock

# Nothing changed → nothing to verify.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [[ -z "$(git status --porcelain -- . ':!.claude/state' 2>/dev/null)" ]] && [[ ! -f "$lock" ]]; then
    exit 0
  fi
fi

if ! out=$(make check 2>&1); then
  {
    echo "Definition of done not met: 'make check' failed. Fix the issues below before finishing."
    [[ -f "$lock" ]] && echo "Tests are locked (/fix): change production code only."
    echo "---"
    printf '%s\n' "$out" | tail -n 60
  } >&2
  exit 2
fi

if [[ -f "$lock" ]]; then
  rm -f "$lock"
  echo "stop-verify: make check is green, test lock released." >&2
fi
exit 0
