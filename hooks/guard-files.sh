#!/usr/bin/env bash
# PreToolUse(Edit|MultiEdit|Write): protect paths in defaults/protected-paths + .aiops/config/protected-paths, and stop
# credentials being written.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
path=$(json_get tool_input.file_path <<<"$input") || fail_closed guard-files
root=${CLAUDE_PROJECT_DIR:-$PWD}
aiops_enabled "$root" || exit 0
rel=$(rel_path "$path" "$root")

block() { echo "BLOCKED by guard-files: $1" >&2; exit 2; }

case "$rel" in
  .env.example|*/.env.example|.env.sample|*/.env.sample) ;;   # templates are fine
  *)
    if hit=$(config_match "$rel" "$root" protected-paths); then
      block "'$rel' is protected (${hit#* })"
    fi ;;
esac

# Credential patterns: scan the raw payload so content, new_string, and MultiEdit edits are all covered.
if grep -qE -- '-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}' <<<"$input"; then
  block "content looks like a credential; use env vars / the secret manager instead"
fi

exit 0
