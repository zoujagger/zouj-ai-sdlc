---
id: 0003
verdict: CHANGES_REQUESTED
commit: c9c37b067ec06bb0e8348a72726c03e1860670b2
score: 80/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 2

<!-- State 5 PRE-REVIEW, round 2 (after F1-F6). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head c9c37b0). Round 1 (76/100) is in git history. The human decides what happens next. -->

## Summary
F2–F6 are confirmed, and both round-1 MAJORs are fixed. **F1 is incomplete.**
- **Verifier:** VERIFIED. All 15 ACs pass.
  - It put the HEAD tests over the pre-fix tree, and all 8 F-proof tests were red there.
  - `make check` passes (140 tests), and `claude plugin validate .` passes on the reviewers' machines.
  - It checked by hand that the pinned `ref` reaches new repos, sandboxes and merged alpha.1 repos.
- **Code reviewer:** red-before-fix was confirmed for all six fixes. F5 costs nothing for team and solo repos, and the
  marketplace value comparison is stable on reruns.
- **Security reviewer:** F2, F5 and F6 hold.
  - F5 failed closed against spoofed key types, `cert-authority` lines and mixed entries.
  - A swap of the target itself, a symlink between rmdir and rename, and a static symlinked parent are all refused.

The blocker, reproduced independently by the code reviewer (first try) and the security reviewer (4/5 concurrent
races, and deterministically):
- **[BLOCKER/HIGH] The sandbox can still be redirected one level down.**
  - **How:** every step after `mkdtemp` goes through the build directory's *path*. A same-uid agent renames the fresh
    `.sdlc-sandbox-XXXX`, or swaps its parent, and plants a symlink to the calling repo under that name.
  - **Why the check misses it:** the toplevel check compares `Path(top).resolve()` with `build.resolve()`, so both
    resolve to the repo and match.
  - **Effect:** `.aiops/config.json` is merged strict→solo, the Makefile is overwritten, and the explicit-list commit
    lands in the caller as the human.
  - **Docs:** the CHANGELOG and the F1 log overstate the fix.

Verdict: **CHANGES_REQUESTED, 80/100.**
- Verifier: VERIFIED.
- Security reviewer: FAIL (1 HIGH).
- Code reviewer: 1 BLOCKER.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:106`, `:20`; the dry run also prints the owned diffs |
| AC-2 | ✅ met | `tests/test_setup.py:150` (the ref is pinned too) |
| AC-3 | ✅ met | `tests/test_setup.py:178`; the value comparison is stable on reruns |
| AC-4 | ✅ met | `tests/test_setup.py:204`; the `init --force` side route is closed (`tests/test_cli.py:33`) |
| AC-5 | ✅ met | `tests/test_setup.py:217` (the diff comes before `[y/N]`, and appears in the dry run; a pty run confirmed it), `:272` |
| AC-6 | ✅ met | `tests/test_setup.py:120` |
| AC-7 | ✅ met | `tests/test_engine.py:513`, `:392` (the CI audit refuses non-sk signers under `"sk"`; doctor shows ✗). The accept path is shown by fingerprint equality only (logged) |
| AC-8 | ⚠️ partial | `tests/test_playbook.py:123-129`. The FAIL-review case is a deferred alpha.3 known issue |
| AC-9 | ✅ met | `tests/test_cli.py:59` (`ref: v<version>`, filled by `apply_init`) |
| AC-10 | ❌ not met | `tests/test_setup.py:295`, `:331`. Functionally met, but the spec flag "Sandbox path: never write outside the intended place" is still unmitigated (blocker) |
| AC-11 | ✅ met | `tests/test_setup.py:72`, `:256` (invalid JSON gives ✗) |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:255`, `:270`; the docs pin `@v0.2.0-alpha.2` |
| AC-13 | ✅ met | `tests/test_setup.py:365` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:302`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:153`, `tests/test_setup.py:166`. A mixed profile/policy config shows a doctor regression (MINOR) |

## Security
- **[HIGH] Sandbox race through the build directory or its parent** (`setup.py` `sandbox()`/`_build_sandbox()`).
  - Fix:
    - Pin the build directory by handle: open the parent with `O_DIRECTORY|O_NOFOLLOW`, `mkdir` the build directory
      relative to it, `fchdir` into it, and do every write and git call relative to that working directory.
    - Check git's toplevel by inode against the pinned directory, never by `resolve()`.
    - Rename through the parent's handle (`src_dir_fd`/`dst_dir_fd`).
    - Add a test that swaps the build directory or its parent right after `git init`.
    - Correct the CHANGELOG and the log.
- **[LOW]**
  - An agent's `init --force` still resets protected-path files outside `HUMAN_OWNED_RE`, such as
    `governance/managed-settings.example.json` or repo-added protected scaffold files. Derive the list from
    protected-paths.
  - `signer_entries` misreads quoted options that contain spaces. That gives a false ✓ in doctor only; CI fails closed.
  - The pin is a tag, not a commit sha (stated in the trust model).
  - The marketplace merge drops sibling keys under `zouj` (such as `autoUpdate`).

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes**: untouched under the agent; only the two pinned keys; a fork is flagged `!` |
| Profile changes through setup | **no, via the sandbox race**; setup itself and `init --force` are closed |
| `gh auth status` / `claude --version` | **yes** |
| Sandbox path | **no**: build-directory/parent TOCTOU |

## Plan conformance
- F1–F6 are logged, each with its proof test. F6 folds in the round-1 marketplace-values LOW and says so.
- **Inaccurate:** the F1 log and the CHANGELOG claim the sandbox can't be redirected.
- **New MINORs:**
  - The doctor dangling `else`, introduced by F5: `team`+`sk` shows no CODEOWNERS row, and `strict`+`human` prints
    it twice.
  - The settings plan note is always "add …", even when it replaces an old ref or a fork.
  - An explicit `enabledPlugins: false` is re-proposed on every rerun.

## Test-first evidence
- All six fix commits carry `Red:`/`Green:` (135 → 140 tests). Both the code reviewer (on the parents in a worktree)
  and the verifier (on the pre-fix tree) reproduced red for every F-proof test.
- **Gap:** the race test swaps only the target, never the build directory or its parent, which is why the blocker
  slipped through.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 34 | AC-10's security flag unmet; AC-8 partial (deferred) |
| Security | 25 | 16 | 1 HIGH (sandbox race one level down), LOWs |
| Test quality & test-first | 20 | 17 | red confirmed for all fixes; the race test misses the build-directory swap |
| Plan conformance | 10 | 9 | F1 and the CHANGELOG overstate the fix |
| Maintainability | 5 | 4 | the dangling `else` |
| **Total** | 100 | **80** | **CHANGES_REQUESTED**: a BLOCKER/HIGH stands |

### Fixes requested
1. **BLOCKER/HIGH:** a handle-pinned sandbox build, an inode-based toplevel check, a rename through the parent handle,
   a build-directory/parent swap test, and corrected CHANGELOG and log wording.
2. **MINOR:** the doctor dangling `else` (a regression from F5).
3. **LOW:** the alpha.3 known-issues list (protected-path files under `init --force`, quoted signer options, the pin
   being a tag, the `zouj` sibling keys, the settings plan note, `enabledPlugins: false`).
