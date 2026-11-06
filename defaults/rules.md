# zouj-ai-sdlc rules

What `sdlc why <id>` prints for each rule in `defaults/rules`. Each section has a `Why:` line (the reason) and an
`Instead:` line (the safe alternative). Keep one section per id.

## G-GATE-01
Why: the stages run in order. A spec needs an approved intent, a plan an approved spec, a review an approved plan.
Instead: finish the upstream artifact and ask the human to type its approval phrase (e.g. `Intent Approved 0001`).

## G-GATE-02
Why: only a human approval moves an artifact past Draft, so a new one can't start approved.
Instead: write it as `status: Draft`; the human approves it by typing the phrase or running `sdlc approve`.

## G-GATE-03
Why: `approved-*` fields are the record of a human decision; the agent can never stamp them.
Instead: leave them out; `sdlc approve` (or the typed phrase) stamps them.

## G-GATE-04
Why: `approved-*` fields are the record of a human decision; changing them would forge or move an approval.
Instead: leave approval fields untouched. To reopen work, set `status: Draft`; the human approves again.

## G-GATE-05
Why: opening a gate is the human's decision. The agent may only close one (set Draft).
Instead: stop and ask the human to type the approval phrase (e.g. `Plan Approved 0001`).

## G-GATE-06
Why: an approval commit (trailer `AIOps-Approval:`) is the proof CI audits; only the human's approval creates one.
Instead: ask the human to approve in the prompt or in their own terminal (`sdlc approve NNNN intent|spec|plan`).

## G-GATE-07
Why: `approve`, `close`, `unlock`, `hook` and `legacy-approvals` decide gates, and a real `uninstall` removes the
workflow's files; they are run by the human (or by Claude Code's hooks), never by the agent.
Instead: ask the human: they type `Intent|Spec|Plan Approved NNNN`, or run the command in their own terminal.

## G-ENV-02
Why: the engine refuses human-only commands when it sees `CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION`; changing or
clearing them would let the agent pass as the human.
Instead: leave the environment alone; human-only steps are run by the human.

## G-LOCK-01
Why: states 1-3 are read-only. Code changes only after the human types `Plan Approved NNNN`.
Instead: finish the current artifact (intent, spec or plan) and ask for its approval; `sdlc status` shows which.

## G-LOCK-02
Why: states 1-3 are read-only, and shell writes (redirects, `sed -i`, `cp`, `rm`, ...) count as edits.
Instead: finish the current artifact and ask for its approval; read-only commands stay allowed.

## G-LOCK-03
Why: states 1-3 are read-only; `git restore`, `stash`, `reset`, `merge`, ... change code in the working tree.
Instead: wait for `Plan Approved NNNN`; `git status`, `log` and `diff` stay allowed.

## G-LOCK-04
Why: staging code in states 1-3 prepares a change the plan hasn't approved.
Instead: stage only `.aiops/` and docs until `Plan Approved NNNN`.

## G-LOCK-05
Why: committing code in states 1-3 lands a change the plan hasn't approved.
Instead: commit only `.aiops/` and docs until `Plan Approved NNNN`.

## G-LOCK-06
Why: installing or removing dependencies changes the code base; states 1-3 are read-only.
Instead: put the dependency change in plan.md; it runs in state 4.

## G-LOCK-07
Why: `make format|fix|generate|migrate|...` rewrite code; states 1-3 are read-only.
Instead: run the read-only targets (`make check`, `make test`); rewriting targets run in state 4.

## G-LOCK-08
Why: `patch`, `unzip` and `tar -x` write files; states 1-3 are read-only.
Instead: wait for `Plan Approved NNNN`, or extract outside the repo.

## G-ART-01
Why: `.aiops/config*` is human-owned (signers, guard lists, key policy) and `.aiops/state/` is engine state.
Instead: propose the change in chat; a human edits `.aiops/config`. State changes go through `sdlc`.

## G-ART-02
Why: a gate opens only for the folder it was approved in; a mismatched `id` could reuse another intent's approval.
Instead: keep `id` equal to the folder number.

## G-ART-03
Why: `id` binds an artifact to its folder and its approvals; it never changes.
Instead: keep `id` equal to the folder number; start a new intent for new work.

## G-ART-04
Why: `find -delete` / `-exec` on `.aiops/` would remove artifacts outside the gate guard.
Instead: narrow it (e.g. `-not -path './.aiops/*'`), or ask the human to remove artifacts.

## G-ART-05
Why: artifacts are checked by the Edit/Write guard (status and approval fields); shell writes would skip it.
Instead: edit artifacts with the Edit/Write tools; engine state changes go through `sdlc`.

## G-ART-06
Why: a patch can rewrite artifacts outside the gate guard, and a piped patch can't be inspected.
Instead: edit artifacts with the Edit/Write tools, or pass the patch file by name (`-i` or `<`).

## G-ART-07
Why: `git apply` / `git am` can rewrite artifacts outside the gate guard, and stdin can't be inspected.
Instead: edit artifacts with the Edit/Write tools, or apply a patch file by name.

## G-ART-08
Why: `git rm|mv|checkout|restore|...` on an artifact deletes or rewrites it outside the gate guard.
Instead: edit artifacts with the Edit/Write tools; ask the human to remove one.

## G-ART-09
Why: an artifact must validate against its schema (front matter, sections, AC ids) before anyone approves it.
Instead: fix the listed errors; `sdlc validate NNNN` shows them.

## G-FILE-01
Why: protected paths (`.claude/settings.json`, the CI audit and deploy workflows, lockfiles, `governance/`, the
repo's own `protected-paths`) are human-owned in every state; shell writes count too.
Instead: propose the change in chat; a human edits protected files.

## G-FILE-02
Why: checking out the whole tree from another revision would rewrite protected files and artifacts at once.
Instead: name the paths you need (outside protected paths and `.aiops/`).

## G-FILE-03
Why: a git command restoring or removing a protected path rewrites human-owned files.
Instead: propose the change in chat; a human edits protected files.

## G-FILE-04
Why: protected paths are human-owned in every state (`defaults/protected-paths` plus the repo's own list).
Instead: propose the change in chat; a human edits protected files.

## G-MERGE-01
Why: merging is the final human gate (state 5); the GitHub API is the same merge by another route.
Instead: leave the PR for a CODEOWNER to review and merge.

## G-MERGE-02
Why: merging into the main branch is the human's decision.
Instead: leave the branch for the human to review and merge (`/zouj-ai-sdlc:pr`).

## G-MERGE-03
Why: main changes only through a reviewed PR; a direct push skips review and the gate audit.
Instead: push a feature branch and open a PR (`/zouj-ai-sdlc:pr`).

## G-MERGE-04
Why: merging, approving a PR, and deleting releases or repos are human decisions.
Instead: a CODEOWNER approves and merges the PR; the agent never approves its own work.

## G-DEPLOY-01
Why: production is a human gate; the agent stops at staging.
Instead: run `/zouj-ai-sdlc:deploy` for the handoff note; a named approver approves the `production` environment
in the `deploy` workflow, or runs `make deploy ENV=prod` themselves.

## G-DEPLOY-02
Why: production is a human gate, whatever tool reaches it.
Instead: run `/zouj-ai-sdlc:deploy` for the handoff note; a named approver deploys.

## G-TEST-01
Why: the /fix test lock is released only by a green `make check` (the Stop hook) or by the human.
Instead: fix the code until `make check` passes.

## G-TEST-02
Why: during /fix the approved failing test defines done; changing it would hide the bug.
Instead: change production code only. If the test itself is wrong, stop and ask the human to re-approve it.

## G-STOP-01
Why: the definition of done is a green `make check`; the session can't finish red.
Instead: fix the failures shown, then finish.

## G-SCAF-01
Why: the agent's `sdlc init|setup|upgrade|repair|uninstall` may act only on this session's repo, from there.
Instead: run it from the project as a command of its own; another repo is set up by the human in their terminal.

## G-SEC-01
Why: secret material outside the repo (`~/.ssh`, `~/.aws`, ...) is never written by the agent.
Instead: ask the human to change credentials themselves.

## G-SEC-02
Why: secret material in the repo (`.env`, keys) is never written by the agent; shell writes count too.
Instead: use `.env.example` for names; ask the human to change real secrets.

## G-SEC-03
Why: real secrets never enter the session, through a shell command or a search.
Instead: use `.env.example` or the docs for variable names.

## G-SEC-04
Why: secret material is never written by the agent.
Instead: use environment variables or the secret manager; document names in `.env.example`.

## G-SEC-05
Why: the content looks like a credential (a private key, cloud key or token); it must not be committed.
Instead: use environment variables or the secret manager instead.

## G-SEC-06
Why: real secrets never enter the session.
Instead: use `.env.example` or the docs for variable names.

## G-ENV-04
Why: `echo $GITHUB_TOKEN` (any variable named ...KEY, TOKEN, SECRET or PASSWORD) prints a credential into the session.
Instead: check that it's set without printing it (`[ -n "$GITHUB_TOKEN" ]`).

## G-ENV-01
Why: printing a token (`gh auth token`, `git credential fill`, ...) puts the credential into the session.
Instead: use the tool's own auth (gh, git, aws) without printing the token.

## G-TOOL-01
Why: the installed plugin is what the human runs to approve; changing it could forge approvals.
Instead: change the plugin through its own repo.

## G-TOOL-02
Why: the installed plugin is what the human runs to approve; shell writes into it count too.
Instead: change the plugin through its own repo.

## G-TOOL-03
Why: `.git/` holds config and hooks that run inside the human's approval; writing there could hijack signing.
Instead: use git commands; ask the human for config or hook changes.

## G-TOOL-04
Why: PATH directories, shell startup files, git config and installed plugins run when the human approves.
Instead: ask the human to change it themselves.

## G-TOOL-05
Why: git signing, hook, fsmonitor, filter, include, alias and diff settings decide who signs approvals and what
runs inside one.
Instead: ask the human to change git config themselves (globally).

## G-BASH-03
Why: a force push rewrites shared history and can drop approval commits.
Instead: create a new commit (or `git revert`) and push normally.

## G-BASH-04
Why: `reset --hard`, `clean -f` and history rewrites destroy work and audit history.
Instead: use `git revert` or `git stash`; ask the human if history must change.

## G-BASH-05
Why: `--no-verify`, `core.hooksPath`, `SKIP_STOP_VERIFY=1` and skipped permissions switch the guards off.
Instead: fix what the hook reports; ask the human if a hook is wrong.

## G-FAIL-01
Why: a guard that crashes must never silently allow.
Instead: tell the human; they fix the plugin or run `/plugin disable zouj-ai-sdlc`.

## G-FAIL-02
Why: without jq or python3 the hook can't read the call, so it blocks rather than allow blindly.
Instead: install jq (or python3).

## G-FAIL-03
Why: the secret-read scan couldn't run, so it blocks rather than allow blindly.
Instead: install python3 >= 3.9; tell the human if it is installed.

## G-FAIL-04
Why: the state engine couldn't run, so the gate guard blocks rather than allow blindly.
Instead: tell the human; they fix the plugin (python3 >= 3.9) or run `/plugin disable zouj-ai-sdlc`.

## G-BASH-01
Why: shells nested more than three deep can't be inspected, so the guard can't tell what they write.
Instead: run the inner command directly.

## G-BASH-02
Why: `rm -r` of `/`, `~`, `$HOME`, `.` or `*` can wipe the repo or the home directory.
Instead: name the paths to remove.

## G-BASH-06
Why: a downloaded script piped into a shell runs code no one has read.
Instead: download the script, show it for review, then run it.

## G-BASH-07
Why: `sudo`, `mkfs`, `dd if=` and `chmod -R 777` change the system or permissions beyond the repo. The toolchain
guard checks only PATH directories you can write, so a command run with `sudo` can also replace root-owned
programs that approvals run (`/usr/local/bin/git`); allow one only if you've read exactly what it writes.
Instead: explain why it's needed and ask the human to run it themselves.

## G-ENV-03
Why: dumping the environment (`env`, `printenv`) can print secrets into the session. The pattern also catches
`env` as a plain word (`ls env`, `python -m venv env`).
Instead: read the one variable you need by a name that isn't secret, or check that it's set (`[ -n "$VAR" ]`).
