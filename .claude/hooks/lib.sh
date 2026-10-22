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

# fail_closed <hook-name>: block when no JSON parser is available rather than silently allowing.
fail_closed() {
  echo "BLOCKED by $1: neither jq nor python3 is installed, so the guardrail cannot inspect this call. Install jq." >&2
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

# is_test_path <path> <root>: true if the path matches .claude/test-paths.
is_test_path() {
  local rel
  rel=$(rel_path "$1" "$2")
  glob_match "$rel" "$2/.claude/test-paths" >/dev/null
}
