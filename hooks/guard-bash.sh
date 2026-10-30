#!/usr/bin/env bash
# PreToolUse(Bash): block destructive, exfiltrating, or guardrail-bypassing commands.
# Exit 2 = block; stderr is shown to Claude. Every block states the reason and the procedure.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

cmd=$(json_get tool_input.command) || fail_closed guard-bash
root=${CLAUDE_PROJECT_DIR:-$PWD}
aiops_enabled "$root" || exit 0

block() {
  echo "BLOCKED by guard-bash: $1" >&2
  echo "Procedure: ${2:-explain why this is needed and ask the human to run it themselves.}" >&2
  exit 2
}

# Normalise whitespace for matching.
c=$(printf '%s' "$cmd" | tr -s '[:space:]' ' ')

# Regexes live in variables: inside [[ =~ ]] bash would otherwise parse ; & | as shell syntax.
S='(^|[ ;&|(])'   # start of a command word
E='([ ;&|)]|$)'   # end of a token

re_rm_root="${S}rm -[a-zA-Z]*r[a-zA-Z]* (/|~|\\\$HOME|\\.|\\*)${E}"
re_force_push="git push.*( --force| -f${E}|--force-with-lease)"
re_push_main="git push.*( |:)(main|master)${E}"
re_history="git (reset --hard|clean -[a-z]*f|filter-branch|filter-repo)"
re_bypass="(--no-verify|core\\.hooksPath|SKIP_STOP_VERIFY=1|--dangerously-skip-permissions)"
re_pipe_sh="(curl|wget)[^|]*\\| ?(sudo )?(ba|z)?sh${E}"
re_read_env="${S}(cat|less|more|head|tail|bat|grep|source|\\.) [^|;&]*\\.env(\\.[a-z]+)?${E}"
re_env_example="\\.env\\.(example|sample|template)${E}"
re_dump_env="(${S}printenv|${S}env${E}|echo .*\\\$[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD))"
re_system="${S}(sudo|mkfs|dd if=|chmod -R 777)${E}"
re_gate="gh (pr merge|pr review [^;&|]*--approve|release delete|repo delete)"
re_lock="\\.aiops/state/test-lock"
re_write_op="(>|${S}(sed -i|tee|mv|cp|rm|truncate|perl -pi)${E})"

[[ "$c" =~ $re_rm_root ]]    && block "recursive delete of root/home/cwd"
[[ "$c" =~ $re_force_push ]] && block "force push" "create a new commit (or git revert) and push normally."
[[ "$c" =~ $re_push_main ]]  && block "direct push to main/master" "push a feature branch and open a PR (/zouj-ai-sdlc:pr)."
[[ "$c" =~ $re_history ]]    && block "history/worktree destruction" "use git revert or git stash; ask the human if history must change."
[[ "$c" =~ $re_bypass ]]     && block "attempt to bypass hooks or permissions"
[[ "$c" =~ $re_pipe_sh ]]    && block "piping remote script to shell" "download the script, show it for review, then run it."
if [[ "$c" =~ $re_read_env ]] && ! [[ "$c" =~ $re_env_example ]]; then
  block "reading .env secrets" "use .env.example for variable names; never read real secrets."
fi
[[ "$c" =~ $re_dump_env ]]   && block "dumping environment secrets"
[[ "$c" =~ $re_system ]]     && block "privileged or dangerous system command"
[[ "$c" =~ $re_gate ]]       && block "merging/approving/deleting is a human gate" "a CODEOWNER approves and merges the PR (state 5 is the human's decision); the agent never approves its own work."

# Test lock: the lock may only be released by the Stop hook (make check green) or a human.
if [[ "$c" =~ $re_lock ]] && [[ "$c" =~ $re_write_op ]]; then
  block "modifying the test lock" "fix the code until make check passes; the Stop hook releases the lock."
fi
if [[ -f "$(test_lock "$root")" ]] && [[ "$c" =~ $re_write_op ]]; then
  read -ra toks <<<"$c"   # split without glob expansion
  for tok in "${toks[@]}"; do
    tok=${tok#\'}; tok=${tok%\'}; tok=${tok#\"}; tok=${tok%\"}; tok=${tok#>}
    if [[ -n "$tok" ]] && is_test_path "$tok" "$root"; then
      block "test files are locked during /zouj-ai-sdlc:fix ($tok)" "change production code only; the approved failing test defines done."
    fi
  done
fi

exit 0
