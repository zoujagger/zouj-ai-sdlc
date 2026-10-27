#!/usr/bin/env bash
# SessionStart: stdout is added to Claude's context. Keep it short.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
cat >/dev/null

status_of() { awk -F': *' '/^status:/{sub(/ *#.*/,"",$2); print $2; exit}' "$1" 2>/dev/null; }

echo "## Session context (AI-native SDLC: Intent → Plan → Design → Build → Test → Deploy → Maintain)"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git branch --show-current 2>/dev/null)
  echo "- Branch: ${branch:-detached} · uncommitted files: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$branch" =~ ([0-9]{4}) ]]; then
    dir=$(find docs/intents -maxdepth 1 -type d -name "${BASH_REMATCH[1]}-*" 2>/dev/null | head -n1)
    if [[ -n "$dir" ]]; then
      line="- Active intent: $dir"
      for f in intent spec plan; do
        [[ -f "$dir/$f.md" ]] && line+=" · $f: $(status_of "$dir/$f.md")"
      done
      echo "$line"
      if [[ -f "$dir/plan.md" ]]; then
        next=$(grep -m1 -E '^- \[( |~)\]' "$dir/plan.md" || true)
        [[ -n "$next" ]] && echo "- Next plan task: ${next#- }"
      fi
    fi
  fi
fi
if command -v make >/dev/null 2>&1 && make -n check 2>/dev/null | grep -q "not configured"; then
  echo "- ⚠️ Makefile contract not wired: make check verifies nothing yet. Tell the user to run make doctor (or bootstrap --stack)."
fi
case "${SDLC_HOOK_PROFILE:-standard}" in
  spike) echo "- ⚠️ Hook profile: spike. make check is not enforced and lint does not block. Not for work headed to a PR." ;;
  strict) echo "- Hook profile: strict (format failures block too)." ;;
esac
[[ -f .claude/state/test-lock ]] && echo "- ⚠️ Test lock active (/fix): test files are read-only until make check is green."
echo "- Intents in repo: $(find docs/intents -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ') (/sdlc for status, /intent to start)"
echo "- Done = make check green + plan.md synced + /verify VERIFIED. The agent stops at the production gate."
exit 0
