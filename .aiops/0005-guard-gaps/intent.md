---
id: 0005
title: Close two shell-write guard gaps (parent directories, uninitialized repos)
status: Draft
owner: zoujagger
initiator: zoujagger
source: security review of intent 0004 PR 1 (2026-11-06); recorded in .aiops/0004-safe-lifecycle/plan.md Deviation log
created: 2026-11-06
---

# Intent: Close two shell-write guard gaps (parent directories, uninitialized repos)

<!-- State 1 BRAINSTORMING. Written from the 0004 security reviews. Both gaps predate 0004 (they are on main as of
     0.2.0-alpha.2) and were deferred here by zoujagger on 2026-11-06. Unknowns go in Open questions. -->

## Problem
The fresh-context security review of 0004 PR 1 (#11) drove the real hooks and found two gaps in the engine's
shell-write check (`guards.check_bash` / `_check_command`). Both are already on main:

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

**Backstop today:** the key policy (a human per signature) and the CI signer audit stop such tampering from opening a
gate silently. Approval isolation level 1 (a separate OS user) is unaffected. The local guards are the deterrent
that's missing.

## Desired outcome
- In every state, a shell command whose target **contains** `.aiops/`, `.git/`, a protected path or a secret path is
  blocked, the same as a command naming that path directly. That includes the repo root itself and any path above it.
- In **every** repo, initialized or not, shell writes to secrets outside the repo, the installed plugin, the approval
  toolchain (PATH directories, shell startup files, global git config) and `git config --global|--system` of signing
  keys are blocked, as Edit/Write already are.
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

## Out of scope
- Interpreter writes (`python -c`, `node -e`) and other forms the static parser can't see. They stay a documented
  residual.
- Install-state rows in `sdlc doctor`. That is a lifecycle follow-up, not a guard gap.
- Rule ids for `post-edit-format.sh` feedback (0004 review, LOW).

## Open questions
- [ ] Should a parent-directory delete of a **non-protected** tree that merely contains a protected file (for example
  `rm -rf docs/` when `docs/CODEOWNERS` is protected) block, or only warn? (zoujagger)
- [ ] For uninitialized repos: block toolchain and secret shell writes outright, or only when the plugin is enabled
  user-wide? Today, any repo where the plugin's hooks run. (zoujagger)
- [ ] Ship with 0.2.0-alpha.3 alongside 0004, or as 0.2.0-alpha.4? (zoujagger)
