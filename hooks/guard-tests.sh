#!/usr/bin/env bash
# PreToolUse(Edit|MultiEdit|Write): while .aiops/state/test-lock exists (set by `sdlc lock` in /fix after a human
# approved the failing test), test files matching the test-paths lists are read-only.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

root=${CLAUDE_PROJECT_DIR:-$PWD}
input=$(cat)
[[ -f "$(test_lock "$root")" ]] || exit 0

path=$(json_get tool_input.file_path <<<"$input") || fail_closed guard-tests
rel=$(rel_path "$path" "$root")

if [[ "$rel" == ".aiops/state/test-lock" ]]; then
  echo "BLOCKED by guard-tests: the test lock can only be released by the Stop hook (make check green) or a human." >&2
  exit 2
fi
if is_test_path "$path" "$root"; then
  {
    echo "BLOCKED by guard-tests: '$rel' is a test file and tests are locked during this fix."
    echo "Reason: the approved failing test defines done; changing it would hide the bug."
    echo "Procedure: change production code only. If the test itself is wrong, stop and ask the human to re-approve it."
  } >&2
  exit 2
fi
exit 0
