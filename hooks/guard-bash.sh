#!/usr/bin/env bash
# PreToolUse(Bash): block destructive, exfiltrating, or guardrail-bypassing commands.
# Exit 2 = block; stderr is shown to Claude. Every block states the reason and the procedure.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

input=$(cat)
cmd=$(json_get tool_input.command <<<"$input") || fail_closed guard-bash
root=${CLAUDE_PROJECT_DIR:-$PWD}
enabled=0; aiops_enabled "$root" && enabled=1   # SDLC rules below only apply in initialized repos

# block <rule-id> <reason> [procedure]: the id is in defaults/rules (`sdlc why <id>` explains it).
block() {
  echo "BLOCKED [$1] by guard-bash: $2" >&2
  echo "Procedure: ${3:-explain why this is needed and ask the human to run it themselves.} (details: \`sdlc why $1\`)" >&2
  exit 2
}

# Normalise whitespace for matching; u is the same with quotes and backslashes removed ('+main', "--force").
# heuristic <rule-id> <reason> [procedure]: a heuristic rule (defaults/rules class `heuristic`) blocks unless the
# human allowed this exact command for it in .aiops/config/allowed-commands; then only this rule is skipped and the
# checks below still run. Only initialized repos have that file.
heuristic() {
  (( enabled )) && allowance "$root" "$1" "$cmd" && return 0
  block "$@"
}

c=$(printf '%s' "$cmd" | tr -s '[:space:]' ' ')
u=${c//\"/}; u=${u//\'/}; u=${u//\\/}

# Regexes live in variables: inside [[ =~ ]] bash would otherwise parse ; & | as shell syntax.
S='(^|[ ;&|(])'   # start of a command word
E='([ ;&|)]|$)'   # end of a token

re_rm_root="${S}rm -[a-zA-Z]*r[a-zA-Z]* (/|~|\\\$HOME|\\.|\\*)${E}"
re_force_push="git push[^;&|]*( --force| -[a-zA-Z]*f[a-zA-Z]*${E}| --mirror${E}| [+][^ ;&|])"   # -fu, +refspec
re_push_main="git push[^;&|]*( |:)(main|master)${E}"
re_history="git (reset --hard|clean -[a-z]*f|filter-branch|filter-repo)"
re_bypass="(--no-verify|core\\.hooksPath|SKIP_STOP_VERIFY=1|--dangerously-skip-permissions)"
re_pipe_sh="(curl|wget)[^|]*\\| ?(sudo )?(ba|z)?sh${E}"
re_cred_print="(gh auth token|gh auth status[^;&|]*(-t|--show-token)|git( -[cC] [^ ;&|]+)* credential(-[a-z]+)? (fill|get)|aws configure (get [^;&|]*(secret|token)|export-credentials)|gcloud auth [^;&|]*print-[a-z-]*token|az account get-access-token|kubectl config view[^;&|]*--raw|docker-credential-[a-z0-9-]+ get|${S}op read)"
re_dump_env="(${S}printenv|${S}env${E})"                         # as a word, quotes kept: `grep "env" f` isn't one
re_dump_env_cmd="(^|[;&|(\`]) ?([^ ;&|]*/)?(printenv|env)${E}"   # in command position, quotes stripped: e''nv, ./env
re_environ="/proc/[^ ;&|]*/(env|e[^ ;&|/]*[*?[]|[*?[])"           # /proc/<pid>/environ, also as a glob
re_environ_word="(^|[ /])environ${E}"
re_environ_path="/environ${E}"                                     # any path ending in /environ: /dev/fd/../environ
re_proc_ctx="(/proc(/|$|[ ;&|])|(^|[ ])proc/|/p[^ /]*[*?[{][^ /]*/|/dev/fd(/|$|[ ;&|]))"   # a /proc or /dev/fd path
re_env_glob="(^|[ /])[^ ;&|/]*[*?[{]"                             # any glob or brace word in that context
re_ansi="[$]'"                                                     # $'…' (matched on $c: $u has no quotes)
re_proc_dump="(grep +-[a-zA-Z]*[rR]|tar +[^;&|]*c|xargs|rsync|cp +-[a-zA-Z]*[rRa])"   # directory dumps there
re_echo_secret="echo .*\\\$[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD)"
re_system="${S}(sudo|mkfs|dd if=|chmod -R 777)${E}"
re_gate="gh (pr merge|pr review [^;&|]*--approve|release delete|repo delete)"
re_lock="\\.aiops/state/test-lock"
re_write_op="(>|${S}(sed -i|tee|mv|cp|rm|truncate|perl -pi)${E})"

[[ "$c" =~ $re_rm_root ]]    && block G-BASH-02 "recursive delete of root/home/cwd" "name the paths to remove."
[[ "$u" =~ $re_force_push ]] && block G-BASH-03 "force push" "create a new commit (or git revert) and push normally."
(( enabled )) && [[ "$u" =~ $re_push_main ]] && block G-MERGE-03 "direct push to main/master" "push a feature branch and open a PR (/zouj-ai-sdlc:pr)."
[[ "$c" =~ $re_history ]]    && block G-BASH-04 "history/worktree destruction" "use git revert or git stash; ask the human if history must change."
[[ "$c" =~ $re_bypass ]]     && block G-BASH-05 "attempt to bypass hooks or permissions" "fix what the hook reports; ask the human if a hook is wrong."
[[ "$c" =~ $re_pipe_sh ]]    && block G-BASH-06 "piping remote script to shell" "download the script, show it for review, then run it."
# Secret reads: every word of every command (substitutions included; heredoc bodies, message values and grep patterns
# excluded), after ~/$HOME/glob expansion and with `cd` tracked, against defaults/secret-paths + .aiops/config/secret-paths.
# One python pass (lib/sdlc_engine/secret_scan.py) instead of a subshell per word.
secret_scan "$input" || exit 2
[[ "$u" =~ $re_cred_print ]] && block G-ENV-01 "printing credentials into the session" "use the tool's own auth (gh, git, aws) without printing the token; never read real secrets."
# the secret rule first: a command matching both reports the id that can never be allowed
[[ "$c" =~ $re_echo_secret ]] && block G-ENV-04 "echoing a secret-named variable prints a credential" "check that it's set without printing it ([ -n \"\$VAR\" ])."
{ [[ "$u" =~ $re_environ ]] || [[ "$u" =~ $re_environ_path ]] || { [[ "$u" =~ $re_proc_ctx ]] && { [[ "$u" =~ $re_environ_word ]] || [[ "$u" =~ $re_env_glob ]] || [[ "$u" =~ $re_proc_dump ]] || [[ "$c" =~ $re_ansi ]]; }; }; } && block G-ENV-05 "reading a process environment prints every secret in it" "read the one variable you need by a name that isn't secret, or check that it's set ([ -n \"\$VAR\" ])."
{ [[ "$c" =~ $re_dump_env ]] || [[ "$u" =~ $re_dump_env_cmd ]]; } && heuristic G-ENV-03 "dumping the environment can print secrets" "read the one variable you need by a name that isn't secret, or check that it's set ([ -n \"\$VAR\" ])."
[[ "$c" =~ $re_system ]]     && heuristic G-BASH-07 "privileged or dangerous system command"
(( enabled )) && [[ "$c" =~ $re_gate ]] && block G-MERGE-04 "merging/approving/deleting is a human gate" "a CODEOWNER approves and merges the PR (state 5 is the human's decision); the agent never approves its own work."

(( enabled )) || exit 0

# Test lock: the lock may only be released by the Stop hook (make check green) or a human.
if [[ "$c" =~ $re_lock ]] && [[ "$c" =~ $re_write_op ]]; then
  block G-TEST-01 "modifying the test lock" "fix the code until make check passes; the Stop hook releases the lock."
fi
if [[ -f "$(test_lock "$root")" ]] && [[ "$c" =~ $re_write_op ]]; then
  read -ra toks <<<"$c"   # split without glob expansion
  for tok in "${toks[@]}"; do
    tok=${tok#\'}; tok=${tok%\'}; tok=${tok#\"}; tok=${tok%\"}; tok=${tok#>}
    if [[ -n "$tok" ]] && is_test_path "$tok" "$root"; then
      block G-TEST-02 "test files are locked during /zouj-ai-sdlc:fix ($tok)" "change production code only; the approved failing test defines done."
    fi
  done
fi

exit 0
