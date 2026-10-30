#!/usr/bin/env bash
# Hook entry for the state engine: engine.sh <pre-edit|pre-bash|prompt|session-start|post-edit>.
# Dormant (exit 0, no python) without .aiops/. Guards (pre-*) fail closed: if the engine can't even start
# (python3 missing, syntax error, broken schema), exit 2 rather than the non-blocking 1/127.
set -uo pipefail
event=${1:-}
root=${CLAUDE_PROJECT_DIR:-$PWD}
plugin=${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
input=$(cat)

if [[ ! -d "$root/.aiops" ]]; then
  # session-start still announces the plugin so people know how to switch it on.
  [[ "$event" == session-start ]] && echo "zouj-ai-sdlc is installed but this repo is not initialized (no .aiops/), so its gates are off here. To use the AI-native SDLC workflow: /zouj-ai-sdlc:init"
  exit 0
fi

errf=$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/zouj-ai-sdlc-hook.$$")
out=$(printf '%s' "$input" | python3 "$plugin/bin/sdlc" hook "$event" 2>"$errf")
rc=$?
err=$(cat "$errf" 2>/dev/null); rm -f "$errf"
[[ -n "$out" ]] && printf '%s\n' "$out"
[[ -n "$err" ]] && printf '%s\n' "$err" >&2

case "$event:$rc" in
  *:0|*:2) exit "$rc" ;;
  pre-*:*)
    {
      echo "BLOCKED by zouj-ai-sdlc: the state engine failed to run (exit $rc), so the guard fails closed."
      echo "Procedure: tell the human. They can fix the plugin (python3 >= 3.9 required) or run /plugin disable zouj-ai-sdlc."
    } >&2
    exit 2 ;;
  *) exit 0 ;;
esac
