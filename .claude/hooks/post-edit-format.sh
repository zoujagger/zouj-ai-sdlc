#!/usr/bin/env bash
# PostToolUse(Edit|MultiEdit|Write): run the formatter, then the linter, after every edit.
# Unconfigured targets are skipped. Lint failures are fed back to Claude (exit 2) so it fixes them now.
# Keep `make format` and `make lint` fast: they run on every edit.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
cat >/dev/null  # drain stdin
command -v make >/dev/null 2>&1 || exit 0

configured() { ! make -n "$1" 2>/dev/null | grep -q "not configured"; }

if configured format; then
  make format >/dev/null 2>&1 || echo "post-edit: 'make format' failed (non-blocking)" >&2
fi
if configured lint; then
  if ! out=$(make lint 2>&1); then
    { echo "post-edit: 'make lint' failed after your edit. Fix these before continuing:"; printf '%s\n' "$out" | tail -n 30; } >&2
    exit 2
  fi
fi
exit 0
