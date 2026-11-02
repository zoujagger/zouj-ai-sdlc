#!/usr/bin/env bash
# PreToolUse(Read|Grep|Glob): secret material (defaults/secret-paths + .aiops/config/secret-paths) is never read into
# the session, in every repo where the plugin is installed. .env.example / .sample / .template stay readable.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
root=${CLAUDE_PROJECT_DIR:-$PWD}
tool=$(json_get tool_name <<<"$input") || fail_closed guard-read

block() {
  echo "BLOCKED by guard-read: $1" >&2
  echo "Procedure: use .env.example or the docs for variable names; real secrets never enter the session." >&2
  exit 2
}

# Path-like inputs: Read/Grep file_path|path, Grep glob, Glob pattern (Grep's pattern is a regex, not a path).
fields="tool_input.file_path tool_input.path tool_input.glob"
[[ "$tool" == Glob ]] && fields+=" tool_input.pattern"
for field in $fields; do
  v=$(json_get "$field" <<<"$input") || fail_closed guard-read
  [[ -z "$v" ]] && continue
  v=${v/#\~/$HOME}
  # Check the path as given AND its symlink-resolved target (a docs/x.md -> ../.env link is still .env).
  real=$( (cd "$root" 2>/dev/null && realpath -m -- "$v") 2>/dev/null || printf '%s' "$v")
  for candidate in "$v" "$real"; do
    rel=$(rel_path "$candidate" "$root")
    rel=${rel#\*\*/}   # **/.env → .env
    secret_template "$rel" && continue
    if hit=$(config_match "$rel" "$root" secret-paths); then
      block "'$v' is secret material (${hit#* })"
    fi
  done
done
exit 0
