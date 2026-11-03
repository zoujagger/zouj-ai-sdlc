#!/usr/bin/env bash
# PreToolUse(Edit|MultiEdit|Write): in every repo, block secret paths (defaults/secret-paths) and credential-looking
# content. In initialized repos also protect defaults/protected-paths + .aiops/config/protected-paths.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
path=$(json_get tool_input.file_path <<<"$input") || fail_closed guard-files
root=${CLAUDE_PROJECT_DIR:-$PWD}
rel=$(rel_path "$path" "$root")

block() { echo "BLOCKED by guard-files: $1" >&2; exit 2; }

if ! secret_template "$rel"; then
  if hit=$(config_match "$rel" "$root" secret-paths); then
    block "'$rel' is secret material (${hit#* }); use env vars / the secret manager"
  fi
  if aiops_enabled "$root" && hit=$(config_match "$rel" "$root" protected-paths); then
    block "'$rel' is protected (${hit#* })"
  fi
fi

# The installed plugin is the code the human runs to approve: never edited from a session in another repo.
plugin_real=$(realpath -m -- "$PLUGIN_ROOT"); root_real=$(realpath -m -- "$root")
path_real=$( (cd "$root" 2>/dev/null && realpath -m -- "$path") || printf '%s' "$path")
if [[ "$plugin_real" != "$root_real" && "$path_real/" == "$plugin_real/"* ]]; then
  block "'$path' is inside the installed plugin, which the human runs to approve; change it through its own repo"
fi

# Credential patterns: scan the raw payload so content, new_string, and MultiEdit edits are all covered.
if grep -qE -- '-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}' <<<"$input"; then
  block "content looks like a credential; use env vars / the secret manager instead"
fi

exit 0
