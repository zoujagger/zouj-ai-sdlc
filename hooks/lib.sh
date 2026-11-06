#!/usr/bin/env bash
# Shared helpers for hooks. Sourced, not executed.

# json_get <dotted.path>: read hook JSON on stdin and print the value at path ("" if missing).
# Uses jq when available, else python3. Returns 127 if neither exists so guards can fail closed.
json_get() {
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg p "$1" 'getpath($p | split(".")) // "" | if type == "string" then . else tojson end'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, sys
v = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    v = v.get(k) if isinstance(v, dict) else None
print("" if v is None else v if isinstance(v, str) else json.dumps(v))' "$1"
  else
    return 127
  fi
}

# hook_profile: strict | standard (default) | spike, from SDLC_HOOK_PROFILE.
# Only the inner-loop hooks (post-edit-format, stop-verify) read it. The safety guards (guard-bash, guard-files,
# guard-tests, guard-deploy) never do: production, test-lock, secrets and force-push rules hold in every profile.
hook_profile() {
  case "${SDLC_HOOK_PROFILE:-standard}" in
    strict|spike) printf '%s' "$SDLC_HOOK_PROFILE" ;;
    *) printf 'standard' ;;
  esac
}

# fail_closed <hook-name>: block when no JSON parser is available rather than silently allowing.
fail_closed() {
  echo "BLOCKED [G-FAIL-02] by $1: neither jq nor python3 is installed, so the guardrail cannot inspect this call." >&2
  echo "Procedure: install jq (or python3). (details: \`sdlc why G-FAIL-02\`)" >&2
  exit 2
}

# rel_path <path> <root>: path relative to the project root.
rel_path() {
  local p=$1 root=$2
  p=${p#"$root"/}
  p=${p#./}
  printf '%s' "$p"
}

# glob_match <rel-path> <patterns-file>: print the first matching line ("<glob> <reason...>"), exit 0 on match.
glob_match() {
  local rel=$1 file=$2 glob rest
  [[ -f "$file" ]] || return 1
  while read -r glob rest; do
    [[ -z "$glob" || "$glob" == \#* ]] && continue
    # shellcheck disable=SC2053  # unquoted RHS = glob match on purpose
    if [[ "$rel" == $glob ]]; then
      printf '%s %s\n' "$glob" "$rest"
      return 0
    fi
  done < "$file"
  return 1
}

# Plugin root (hooks run with CLAUDE_PLUGIN_ROOT set; fall back to this file's location for tests).
PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}

# aiops_enabled <root>: the SDLC rules act only in repos initialized with `sdlc init`: .aiops/ on disk, or tracked in
# git (so deleting the folder can't switch them off). Safety rules (secrets, force-push, prod deploy) never check this.
aiops_enabled() {
  [[ -d "$1/.aiops" ]] || [[ -n "$(git -C "$1" ls-files -- .aiops 2>/dev/null | head -n1)" ]]
}

# secret_template <rel>: .env.example / .sample / .template are documentation, not secrets.
secret_template() {
  case "$1" in
    .env.example|*/.env.example|.env.sample|*/.env.sample|.env.template|*/.env.template) return 0 ;;
    *.pub) return 0 ;;   # public keys are not secret
  esac
  return 1
}

# config_match <rel-path> <root> <name>: glob_match against the plugin default list and .aiops/config/<name>.
config_match() {
  glob_match "$1" "$PLUGIN_ROOT/defaults/$3" || glob_match "$1" "$2/.aiops/config/$3"
}

# test_lock <root>: path of the /fix test lock.
test_lock() { printf '%s/.aiops/state/test-lock' "$1"; }

# is_test_path <path> <root>: true if the path matches the test-paths lists.
is_test_path() {
  local rel
  rel=$(rel_path "$1" "$2")
  config_match "$rel" "$2" test-paths >/dev/null
}

# secret_scan <hook-json>: the shell/search secret-read scan (lib/sdlc_engine/secret_scan.py). Returns 0 (allow) or
# 1 after printing the block to stderr; fails closed if python3 can't run it. -I: no cwd, PYTHONPATH or user site.
secret_scan() {
  local rc=0
  local py=/usr/bin/python3; [[ -x "$py" ]] || py=python3   # not the first python3 on PATH
  printf '%s' "$1" | "$py" -I -c 'import sys; sys.path.insert(0, sys.argv[1])
from sdlc_engine.secret_scan import main; sys.exit(main())' "$PLUGIN_ROOT/lib" || rc=$?
  case $rc in
    0) return 0 ;;
    2) return 1 ;;
    *) echo "BLOCKED [G-FAIL-03] by zouj-ai-sdlc: the secret-read scan failed to run (exit $rc), so it fails closed." >&2
       echo "Procedure: install python3 >= 3.9, or tell the human. (details: \`sdlc why G-FAIL-03\`)" >&2
       return 1 ;;
  esac
}

# allowance <root> <rule-id> <command>: true if the human listed this exact command for this heuristic rule in
# <root>/.aiops/config/allowed-commands. One definition of "exact" (lib/sdlc_engine/rules.py allowed()); called only
# on the block path. Any failure (no python3, a broken file) means no allowance: the command stays blocked.
allowance() {
  local py=/usr/bin/python3; [[ -x "$py" ]] || py=python3
  printf '%s' "$3" | "$py" -I -c 'import sys; sys.path.insert(0, sys.argv[1])
from sdlc_engine.rules import allowed; sys.exit(0 if allowed(sys.argv[2], sys.argv[3], sys.stdin.read()) else 1)' \
    "$PLUGIN_ROOT/lib" "$1" "$2" 2>/dev/null
}
