---
id: 0005
title: Close the shell-write guard gaps found in the 0004 reviews
status: Approved
owner: zoujagger
initiator: zoujagger
source: security reviews of intent 0004 (PR 1 #11, PR 2 #12, 2026-11-06); .aiops/0004-safe-lifecycle/plan.md Deviation log; interview with zoujagger 2026-11-06
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T13:30:22Z
approved-via: cli
approved-sha256: 5fc2ef1d0a5d6901c8a385ce583a4a801f82b166663065431657569eb828f31c
---

# Intent: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 1 BRAINSTORMING. Written from the 0004 security reviews; zoujagger deferred these gaps here on 2026-11-06
     and answered the open questions the same day. Gaps 1-4 predate 0004 (on main as of 0.2.0-alpha.2). -->

## Problem
The fresh-context security reviews of 0004 drove the real hooks and found gaps in the engine's shell-write check
(`guards.check_bash` / `_check_command`) and the env-dump rule. The first two came from PR 1 (#11):

1. **A parent directory of a protected path is not protected.** In states 4-5, when the read-only lock is off, these
   all pass both `guard-bash.sh` and `sdlc hook pre-bash`:
   - `rm -rf ./`, `rm -rf -- .`, `rm -rf "$PWD"`, `rm -rf <absolute repo path>`, `rm -rf ..`, `rm -rf ~/`
   - `rm -rf .github/workflows`, `mv .github /tmp/x`, `rm -rf .claude`

   Shell-write targets are compared with `protected-paths` globs **exactly**, never as a parent directory. The
   git-command branch already has a parent-directory check; the shell-write branch doesn't. The effect: the agent can
   delete the whole worktree, including `.aiops/` and `.git/`, or the CI audit workflow (`aiops-gates.yml`). The
   threat model says `.aiops` can never be a shell target in any state. `re_rm_root` (G-BASH-02) catches only a bare
   `.`, `*`, `/`, `~` or `$HOME`.
2. **Shell writes to the approval toolchain and secrets aren't checked in a repo without `.aiops/`.**
   `check_bash` returns early in an uninitialized repo. So these pass in any repo where `sdlc init` hasn't run:
   - `echo x >> ~/.gitconfig`, `echo x >> ~/.bashrc`, `echo x >> ~/.ssh/authorized_keys`
   - `echo x > <plugin>/lib/sdlc_engine/x.py`
   - `git config --global gpg.ssh.program /tmp/x`

   The approval toolchain is global (the plugin cache, global git config, shell startup), so an agent working in an
   unrelated repo can tamper with what the human's next approval runs in an initialized one. Edit/Write to the same
   paths *is* blocked everywhere (`guard-files.sh`). Rules G-SEC-01, G-TOOL-02/03/05 and the shell half of G-TOOL-04
   are labelled `initialized-repo` for this reason.

Found later in the 0004 PR 2 reviews, same class (shell forms the parser misses):
3. **`re_dump_env` (G-ENV-03) doesn't match `/usr/bin/env` or a quoted `e''nv`**, so those environment dumps were
   never blocked.
4. **Archive extraction into the working directory, `git stash pop` and `git pull` can write `.aiops/config/*`**,
   including `allowed-commands`, `protected-paths` and `readonly-exempt`.
5. **`sdlc init --force` run by the agent can overwrite a modified CLAUDE.md or Makefile in states 1-3** when an
   inline `SDLC_HOOK_PROFILE=` / `AIOPS_INTENT=` lifts the lock for that run (0004 closed this for
   upgrade/repair only).

6. **G-ENV-03's whole-environment check (`rules.dumps_environment`) works from a list of known forms**: `bash -c env`,
   `env env`, `xargs env`, `if …; then env; fi` and `env>/tmp/x` pass it. A human must still write the exact line
   into `allowed-commands`. Replace the list with a rule that recognises only the safe forms, or check nested
   commands again.

**Backstop today:** the key policy (a human per signature) and the CI signer audit stop such tampering from opening a
gate silently. Approval isolation level 1 (a separate OS user) is unaffected. The local guards are the deterrent
that's missing.

## Desired outcome
- In every state, a shell command whose target **contains** `.aiops/`, `.git/`, a protected path or a secret path is
  blocked, the same as a command naming that path directly. That includes the repo root itself and any path above it.
- In **every** repo, initialized or not, shell writes to secrets outside the repo, the installed plugin, the approval
  toolchain (PATH directories, shell startup files, global git config) and `git config --global|--system` of signing
  keys are blocked, as Edit/Write already are.
- `/usr/bin/env`, `e''nv` and other spellings of an environment dump are blocked like `env` (gap 3).
- Archive extraction into the working directory, `git stash pop` and `git pull` can't write `.aiops/config/*` (gap 4).
- Run by the agent, `sdlc init --force` judges the read-only lock without `SDLC_HOOK_PROFILE` / `AIOPS_INTENT`,
  as upgrade and repair do (gap 5).
- A G-ENV-03 allowance is accepted only for the safe forms: `printenv NAME…`, or a command in which `env`/`printenv`
  isn't run at all (`ls env`, `python -m venv env`). Everything else is refused, with no list of known dumps to
  outgrow (gap 6).
- Each block carries a registered rule id (`defaults/rules`) with an accurate stage. `G-TOOL-04` and the others no
  longer need an `initialized-repo` caveat, or the split is explicit.
- `docs/architecture.md`, the README and the CHANGELOG known issues no longer list these gaps.
- Tests reproduce every command above as blocked, and the existing `make check` suite stays green with no new false
  positives on the commands agents normally run (`rm -rf build/`, `rm -rf node_modules`, `git clean` in a subdirectory).

## Users & systems affected
- **Users:** every team relying on the local guards in states 4-5. Developers who run Claude Code in repos without
  `.aiops/` while also approving in initialized ones.
- **Systems:** `lib/sdlc_engine/guards.py` (`check_bash`, `_check_command`, `_toolchain_path`), `hooks/guard-bash.sh`
  (`re_rm_root`), `defaults/rules` and `rules.md`, `tests/test_guards.py` and `tests/test_shell_hooks.py`,
  `docs/architecture.md`, README, CHANGELOG.

## Constraints
- **The playbook workflow is non-negotiable** (`docs/roadmap.md`): no gate weakens, and SDLC gate hooks stay dormant
  without `.aiops/` (CLAUDE.md rule 3). Only the safety checks (secrets, toolchain, plugin) become always-on.
- **Guards are test-first**, and every block states its reason, its procedure and its rule id (CLAUDE.md rule 2).
- **Stdlib only.** Hook regexes stay in variables, and the hook must stay fast on every tool call.
- **No new allowable rules:** the fixes are `safety`, `secret` or `toolchain` class (ADR 0002).
- **Ships as 0.2.0-alpha.4,** a guard-hardening release of its own (zoujagger, 2026-11-06).

## Out of scope
- Interpreter writes (`python -c`, `node -e`) and other forms the static parser can't see. They stay a documented
  residual.
- Install-state rows in `sdlc doctor`. That is a lifecycle follow-up, not a guard gap.
- Rule ids for `post-edit-format.sh` feedback (0004 review, LOW).

## Open questions
- [x] A delete of an ordinary directory that contains a protected file (`rm -rf docs/` with `docs/CODEOWNERS`
  protected)? → **Block**, like naming the path directly. The agent names narrower paths (zoujagger, 2026-11-06)
- [x] In repos without `.aiops/`? → **Block** toolchain, plugin and secret shell writes in every repo where the hooks
  run, as Edit/Write already are. SDLC gates stay dormant (zoujagger, 2026-11-06)
- [x] Release? → **0.2.0-alpha.4**, on its own (zoujagger, 2026-11-06)
- [x] G-ENV-03 dump check? → **Only the safe forms are allowable** (`printenv NAME…`, env/printenv not run at all);
  no list of known dumps (zoujagger, 2026-11-06)
