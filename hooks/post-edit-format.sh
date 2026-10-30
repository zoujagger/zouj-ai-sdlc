#!/usr/bin/env bash
# PostToolUse(Edit|MultiEdit|Write): run the formatter, then the linter, after every edit.
# Unconfigured targets are skipped. Lint failures are fed back to Claude (exit 2) so it fixes them now.
# Keep `make format` and `make lint` fast: they run on every edit.
# SDLC_HOOK_PROFILE: strict = format failures block too · spike = lint failures are reported but don't block.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
cat >/dev/null  # drain stdin
aiops_enabled . || exit 0
profile=$(hook_profile)
command -v make >/dev/null 2>&1 || exit 0

configured() { ! make -n "$1" 2>/dev/null | grep -q "not configured"; }

if configured format; then
  if ! out=$(make format 2>&1); then
    if [[ "$profile" == strict ]]; then
      { echo "post-edit: 'make format' failed (strict profile). Fix before continuing:"; printf '%s\n' "$out" | tail -n 30; } >&2
      exit 2
    fi
    echo "post-edit: 'make format' failed (non-blocking)" >&2
  fi
fi
if configured lint; then
  if ! out=$(make lint 2>&1); then
    if [[ "$profile" == spike ]]; then
      echo "post-edit: 'make lint' failed (spike profile: not blocking; fix before leaving spike mode)" >&2
      exit 0
    fi
    { echo "post-edit: 'make lint' failed after your edit. Fix these before continuing:"; printf '%s\n' "$out" | tail -n 30; } >&2
    exit 2
  fi
fi
exit 0
