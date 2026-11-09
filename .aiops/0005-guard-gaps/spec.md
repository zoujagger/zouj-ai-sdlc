---
id: 0005
title: Close the shell-write guard gaps found in the 0004 reviews
status: Approved
risk: medium           # changes guard decisions in every repo (more blocks); no gate semantics change
intent: ./intent.md
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T13:35:17Z
approved-via: cli
approved-sha256: 325039b29e458524d2ec5e9145a2e521cd2a8044d44f279ad5d519b3e6c87e19
---

# Spec: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 2 SPECIFICATION. From the approved intent (six gaps, four interview answers). Code cited as path:line on
     main at 4285a45 (0.2.0-alpha.3). -->

## Summary
The 0004 security reviews found six ways a shell command gets past the guards, or past an allowance. All of them
predate this intent. This spec closes them, and every change makes the guards stricter:
- **Deleting a parent directory.** Deleting or moving a directory that contains `.aiops/`, `.git/`, a protected path
  or a tracked secret is blocked. So are the repo root and anything above it.
- **Repos without `.aiops/`.** Shell writes to the approval toolchain, the installed plugin and secrets outside the
  repo are blocked in every repo.
- **Environment dumps.** Every spelling is caught, including `/usr/bin/env`, `e''nv` and `/proc/*/environ`.
- **Archives and git.** Extracting an archive, `git stash pop|apply`, `git merge|rebase|cherry-pick <ref>` and
  `git pull` can't bring in changes to `.aiops/config*` or protected paths, except from the main branch.
- **`init --force`.** When the agent runs it, it judges the lock without `SDLC_HOOK_PROFILE` / `AIOPS_INTENT`.
- **G-ENV-03 allowances.** They accept only the safe forms.

Every block has a registered id. SDLC gates stay dormant without `.aiops/`. Ships as **0.2.0-alpha.4**.

## Requirements
- **R-1 Deleting a protected tree (gap 1).** In an initialized repo, in every state, the target of a delete or a
  move is blocked if any of these hold:
  - it resolves to the repo root or to a directory that contains the repo (`.`, `./`, `-- .`, `"$PWD"`, an absolute
    repo path, `..`, `~`, `/`)
  - it contains `.aiops/` or `.git/`
  - it contains a path that matches a `protected-paths` glob (the glob begins with `<target>/`, as the git branch
    already checks at `guards.py:760`)
  - it contains a git-tracked file (`git ls-files -- <target>`) that matches `protected-paths` or `secret-paths`

  The commands that count are `rm`, `rmdir`, `unlink`, `shred`, the sources of `mv`, and `find … -delete` roots.
  New rule **G-FILE-05** (gate). Writing *into* a directory (`cp a docs/`, `> docs/x`) is not a delete and is
  unchanged. Untracked files below the target are not walked, so `rm -rf node_modules` stays fast and allowed.
- **R-2 Repos without `.aiops/` (gap 2).** `check_bash` runs a safety pass even when the repo is not initialized. It
  blocks shell writes:
  - outside the repo to `secret-paths` (G-SEC-01)
  - into the installed plugin (G-TOOL-02)
  - to the approval toolchain: PATH directories, shell startup files, global git config (G-TOOL-04)
  - via `git config --global|--system` of the signing, hook and include keys (G-TOOL-05)

  It also follows `bash -c` / `eval` nesting (G-BASH-01). The SDLC gate checks (artifacts, lock, protected paths,
  merge) stay dormant. `hooks/engine.sh` runs `pre-bash` in every repo (today it exits early, `engine.sh:6`).
  Those five rules move to stage `every-repo`.
- **R-3 Environment dumps (gap 3).** In `guard-bash.sh`, `re_dump_env` matches on the unquoted text `$u`, with an
  optional path prefix: `/usr/bin/env`, `e''nv` and `\printenv` all match.
  - New rule **G-ENV-05** (secret, never allowable): reading `/proc/<pid>/environ`, through any command.
- **R-4 Changes brought in from elsewhere (gap 4).** In an initialized repo, in every state, these are blocked with
  new rule **G-FILE-06** (gate) when they would write `.aiops/config*`, `.claude/settings.json` or a
  `protected-paths` match:
  - `tar -x` and `unzip` into the repo: the archive's member list is read with stdlib `tarfile` / `zipfile`; an
    archive that can't be read is refused
  - `git stash pop|apply [<stash>]`: the paths come from `git stash show --name-only --include-untracked <stash>`
  - `git merge|rebase|cherry-pick <ref>`: the paths come from `git diff --name-only HEAD...<ref>`, or from the
    commit for `cherry-pick`

  Exceptions and special cases:
  - A ref that is the main branch or its remote-tracking branch (`config.main_branch`, `origin/<main>`) is exempt:
    its config was merged by a human.
  - Changes to intent folders (`.aiops/NNNN-*`) are allowed: approval commits arrive this way.
  - `git pull` can't be inspected before it fetches, so it is refused in an initialized repo, with the procedure
    "`git fetch`, then `git merge <ref>`". `git pull` of the main branch while on main stays allowed.
- **R-5 `init --force` run by the agent (gap 5).** `cli.init_actions(agent=True)` judges `_agent_blocked` without
  `SDLC_HOOK_PROFILE` / `AIOPS_INTENT`, sharing one helper with `lifecycle.agent_may_write`, and the G-SCAF-01 line
  rule already covers `init`.
- **R-6 G-ENV-03 allowances accept only safe forms (gap 6).** `rules.allowed(…, "G-ENV-03", cmd)` is true only if
  all of these hold:
  - the command has no substitution or redirection characters (`$(`, `` ` ``, `<(`, `>(`, `<`, `>`)
  - every simple command (split on `; & | ( ) { }` and newlines) is either `printenv NAME…` (one or more
    variable-name operands, no options) or one whose command word is in a fixed list of commands that never run
    their arguments: `ls`, `cd`, `cat`, `head`, `tail`, `wc`, `file`, `stat`, `du`, `tree`, `source`, `.`,
    `python`/`python3` with `-m venv`, `virtualenv`
  - no other simple command contains `env` or `printenv` as a word

  `rules.dumps_environment` is replaced by `rules.safe_env_command`. `allowance_problems` reports any other G-ENV-03
  entry.
- **R-7 Ids and docs.**
  - `defaults/rules` and `rules.md` gain G-FILE-05, G-FILE-06 and G-ENV-05, and G-SEC-01, G-TOOL-02, G-TOOL-04,
    G-TOOL-05 and G-BASH-01 move to `every-repo`.
  - `docs/architecture.md` (threat model: `.aiops/` integrity, the always-on safety guards, static parsing),
    README, TROUBLESHOOTING and the CHANGELOG (alpha.4; remove the known issues this fixes).
- **Non-functional:**
  - **Speed:** a Bash call in a repo without `.aiops/` adds one python start (about 40 ms, like the secret scan that
    already runs there). The R-1 and R-4 lookups run only for delete, move, extract, stash and merge commands.
  - **Dependencies:** stdlib only; regexes stay in variables.

## Acceptance criteria
- **AC-1**: Given an initialized repo in state 4 (unlocked), when the agent runs any of `rm -rf ./`, `rm -rf -- .`,
  `rm -rf "$PWD"`, `rm -rf <abs repo path>`, `rm -rf ..`, `rm -rf ~/`, `rm -rf .github/workflows`,
  `mv .github /tmp/x`, `rm -rf .claude`, `rm -rf .aiops`, `rm -rf .git`, or `rm -rf docs` while `docs/CODEOWNERS` is
  protected, then each is blocked with a registered id (G-FILE-05, or the existing `.aiops` id), with a reason and a
  procedure.
- **AC-2**: Given the same repo, when the agent runs `rm -rf build/`, `rm -rf node_modules` (untracked, 10 000 files),
  `rm src/old.py`, `cp a.txt docs/` or `mv src/a.py src/b.py`, then each is allowed. `rm -rf node_modules` decides
  within 200 ms.
- **AC-3**: Given a repo **without** `.aiops/`, when the agent runs `echo x >> ~/.gitconfig`, `echo x >> ~/.bashrc`,
  `echo x >> ~/.ssh/authorized_keys`, `echo x > <plugin>/lib/sdlc_engine/x.py`,
  `git config --global gpg.ssh.program /tmp/x`, or the same nested in `bash -c '…'`, then each is blocked (G-TOOL-04,
  G-SEC-01, G-TOOL-02, G-TOOL-05). `rm -rf src`, `echo x > src/a.py` and `git push origin main` stay allowed: SDLC
  gates are dormant.
- **AC-4**: Given any repo, when the agent runs `/usr/bin/env`, `e''nv`, `"printenv"`, `\env` or
  `cat /proc/self/environ`, then the first four are blocked as G-ENV-03 and the last as G-ENV-05. `ls env`,
  `python -m venv env` and `env FOO=1 make` are still blocked as G-ENV-03, unchanged.
- **AC-5**: Given an initialized repo, when the agent extracts an archive (tar.gz and zip) whose members include
  `.aiops/config/allowed-commands`, `.claude/settings.json` or `.github/workflows/aiops-gates.yml` into the repo, then
  it is blocked (G-FILE-06). An archive with only `src/` members is allowed. An unreadable archive is refused.
- **AC-6**: Given a stash that changes `.aiops/config/protected-paths`, when the agent runs `git stash pop`, then it is
  blocked (G-FILE-06). A stash touching only `src/` is allowed.
- **AC-7**: Given a local branch `x` whose commits change `.aiops/config.json`, when the agent runs `git merge x`,
  `git rebase x` or `git cherry-pick <that commit>`, then each is blocked (G-FILE-06). `git merge main` and
  `git merge origin/main` are allowed. So is a branch whose only `.aiops/` change is an approval commit to
  `.aiops/NNNN-*/plan.md`.
- **AC-8**: Given an initialized repo on a feature branch, when the agent runs `git pull`, then it is blocked
  (G-FILE-06) with the procedure "git fetch, then git merge <ref>". On the main branch, `git pull` is allowed.
- **AC-9**: Given `CLAUDECODE=1` and `SDLC_HOOK_PROFILE=spike` (or `AIOPS_INTENT=…`) in the environment, in a locked
  repo with a modified `Makefile`, when `sdlc init --force` runs, then the Makefile is kept and listed for the human.
- **AC-10**: Given `allowed-commands` entries `G-ENV-03 <cmd>`, then `rules.allowed` and the hook accept only safe
  forms:
  - accepted: `printenv PATH`, `printenv HOME USER`, `ls env`, `cd env`, `source env/bin/activate`,
    `python -m venv env`
  - refused, and reported by `allowance_problems`: `env`, `printenv`, `env FOO=1 make`, `bash -c env`, `env env`,
    `xargs env`, `if true; then env; fi`, `env>/tmp/x`, `echo $(printenv)`, `nice env`, `printenv -0`,
    `cat <(env)`, `watch env`
- **AC-11**: Given `defaults/rules`, then G-FILE-05, G-FILE-06 and G-ENV-05 exist with `rules.md` sections, and
  `sdlc why` shows G-SEC-01, G-TOOL-02, G-TOOL-04, G-TOOL-05 and G-BASH-01 as "in every repo".
  `tests/test_rules.py::Coverage` passes.
- **AC-12**: Given `tests/test_playbook.py` in each profile, then the full walk still passes. Each AC-1 command
  stays blocked in states 1, 4 and 5.
- **AC-13**: Given the 0.2.0-alpha.3 test suite, then every existing test passes, with no new block on a command
  that an existing test expects to be allowed.

## Data model
No data. Registry changes:
- New rules:
  - `G-FILE-05 gate every-stage` (deleting a protected tree)
  - `G-FILE-06 gate every-stage` (changes to protected config brought in by extraction, stash, merge or pull)
  - `G-ENV-05 secret every-repo` (reading `/proc/*/environ`)
- Stage changes to `every-repo`: G-SEC-01, G-TOOL-02, G-TOOL-04, G-TOOL-05, G-BASH-01.

## API contracts
- **CLI and output:** nothing new; the block messages carry the new ids.
- **`hooks/engine.sh`:**
  - `pre-bash` runs the engine in every repo (`session-start`, `prompt` and `pre-edit` keep the early exit).
  - `check_bash(data)` in an uninitialized repo returns only safety blocks.
- **`rules.safe_env_command(cmd) -> bool`** replaces `dumps_environment`, which is kept as an alias for one release.

## Security & data-leak flags
- ⚠️ **False positives on common commands.** R-1 could block `rm -rf build`, and R-4 could block extracting a release
  tarball. → AC-2 lists the commands that must stay allowed. Untracked trees aren't walked, and archives are judged
  by their members. Who decides: zoujagger, at the spec gate.
- ⚠️ **Refusing `git pull` on feature branches** (R-4) changes a common agent habit. → The procedure says fetch and
  merge, which is inspected, and pull on main stays allowed. Decided: refuse (zoujagger, 2026-11-06).
- ⚠️ **One more python start per Bash call in uninitialized repos** (R-2). → About 40 ms, as the secret scan already
  costs. Who decides: zoujagger.
- ⚠️ **Approval commits must still flow** (R-4): a human's approval pushed from a clean clone arrives by merge or
  pull. → Intent folders are exempt; only `.aiops/config*`, settings and protected paths are inspected. With `pull`
  refused on feature branches, the agent fetches and merges, and that merge is inspected and allowed. Who decides:
  none.
- ⚠️ **Static parsing stays incomplete:** interpreter writes, `bsdtar`, `7z` and `git apply` of fetched patches.
  → They stay documented residuals. The key policy and the CI audit remain the hard guarantee.

## Architecture
- **`lib/sdlc_engine/guards.py`:**
  - `check_bash`: before `initialized()`, call `_check_command(…, gates=False)` for the safety pass (R-2).
  - `_check_command(…, gates=True)`: the in-repo checks (aiops, protected, lock, merge, patch, find, git) run only
    when `gates`. The outside-repo and plugin checks and `_git_config_writes_signing` for `--global` / `--system`
    always run.
  - New `_contains_protected(root, rel_or_abs) -> (rule_id, what) | None` (R-1): the repo root and its ancestors,
    `.aiops`, `.git`, protected-glob prefixes, and `git ls-files -z -- <target>` matched against the protected and
    secret globs. It is called for the delete and move targets of `rm|rmdir|unlink|shred|mv` and `find -delete`
    roots.
  - New `_incoming_paths(sub, args, cwd, root) -> [rel] | None` (R-4): reads `tarfile` / `zipfile` members, `git
    stash show`, `git diff --name-only HEAD...<ref>`, `git show --name-only` for cherry-pick. `None` means it can't
    tell, and the command is refused.
- **`hooks/engine.sh`:** the `.aiops` early exit is skipped for `pre-bash`.
- **`hooks/guard-bash.sh`:** `re_dump_env` and the new `re_environ` (G-ENV-05) test `$u`.
- **`lib/sdlc_engine/rules.py`:** `safe_env_command` (R-6).
- **`lib/sdlc_engine/cli.py` / `lifecycle.py`:** a shared `lock_env_stripped()` context, used by `init_actions(agent=True)`
  and `agent_may_write` (R-5).
- **Alternatives considered:**
  - Walking untracked files for R-1: rejected (`node_modules` cost; untracked files aren't the audit trail).
  - Inspecting `git pull` with a dry fetch: rejected (network inside a hook).
  - Running the safety pass in `guard-bash.sh`: rejected (the parser lives in Python).

## Rollout & rollback
- Release **0.2.0-alpha.4**. CHANGELOG under `[Unreleased]` until the release PR.
- **Rollback:** reinstall 0.2.0-alpha.3. Nothing is stored, so there is nothing to migrate.
- **Watch:** false-positive reports quoting G-FILE-05 and G-FILE-06 (issue template `quick-feedback`).

## Open questions
- [x] `git pull` on a feature branch? → **Refuse**, with the procedure "`git fetch`, then `git merge <ref>`", which is
  inspected. Pull on main stays allowed (zoujagger, 2026-11-06)
- [x] Deleting a directory that holds a **tracked** secret? → **Block** (G-FILE-05), like a protected path
  (zoujagger, 2026-11-06)
