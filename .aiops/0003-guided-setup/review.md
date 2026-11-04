---
id: 0003
verdict: CHANGES_REQUESTED
commit: 8d91993029c6e4d26650c494cf23d35f054fe24f
score: 78/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 3

<!-- State 5 PRE-REVIEW, round 3 (after G1, G2). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head 8d91993). Rounds 1 (76) and 2 (80) are in git history. The human decides what happens next. -->

## Summary
Everything outside `setup --sandbox` is done and holds.
- **Verifier:** VERIFIED. All 15 ACs pass, all 25 proof tests pass, and G1/G2 are red on their parents.
- **Checks:** `make check` passes (142 tests), and so do `claude plugin validate .` and `validate --all --ci --base main`.
- **Holding:** the round-1/2 fixes (agent `init --force`, the `"sk"` CI audit, the pinned marketplace, diff before
  confirmation, invalid JSON) were re-checked. G2 (the doctor row) is fixed.
- **G1:** fixes exactly what round 2 reported. Swapping the target, the build directory or its parent is refused,
  or the sandbox lands at the original place.

The sandbox is still not safe from the agent. G1 pins the *directory*, but git still finds its repository by name and
reads the caller's environment:
- **[HIGH] `GIT_DIR` in the environment, with no race.**
  - **How:** `GIT_DIR=$PWD/.git sdlc setup --sandbox /tmp/x` is allowed by the guards. The sandbox's git calls inherit
    it, and the toplevel check passes, because git reports the current directory.
  - **Effect:** the commit lands on the caller's branch, as the human:
    - `.aiops/config.json` goes strict→solo
    - `.claude/settings.json`, CODEOWNERS and the workflows are replaced

    "Sandbox ready … nothing outside it was touched" is still printed.
- **[HIGH/BLOCKER] `.git` swapped for a symlink or a `gitdir:` file**, planted before `git init` or swapped after it.
  The commit goes into the caller's repo. The security reviewer won 5/5 concurrent races, and the code reviewer
  reproduced it deterministically, including after the toplevel check. A planted `.git/hooks/pre-commit` or
  `core.worktree` are related routes.

Verdict: **CHANGES_REQUESTED, 78/100.**
- Verifier: VERIFIED.
- Code reviewer: 1 BLOCKER.
- Security reviewer: FAIL (2 HIGH, 1 MEDIUM).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:106`, `:20` |
| AC-2 | ✅ met | `tests/test_setup.py:150` |
| AC-3 | ✅ met | `tests/test_setup.py:178` |
| AC-4 | ✅ met | `tests/test_setup.py:204`, `tests/test_cli.py:33` |
| AC-5 | ✅ met | `tests/test_setup.py:217`, `:272` |
| AC-6 | ✅ met | `tests/test_setup.py:120` |
| AC-7 | ✅ met | `tests/test_engine.py:513`, `:392` (accept path by fingerprint equality, logged) |
| AC-8 | ⚠️ partial | `tests/test_playbook.py:123-129`; the FAIL-review case is a deferred alpha.3 known issue |
| AC-9 | ✅ met | `tests/test_cli.py:59` |
| AC-10 | ❌ not met | `tests/test_setup.py:295`, `:330`, `:355`, `:390`, `:399`: functionally met, but the spec's security flag "Sandbox path: never write outside the intended place" is not mitigated (the HIGHs above) |
| AC-11 | ✅ met | `tests/test_setup.py:72`, `:256` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:255`, `:270` |
| AC-13 | ✅ met | `tests/test_setup.py:413` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:302`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:153`; the round-2 MINOR is fixed (the row appears once in all four mixes) |

## Security
- **[HIGH] The caller's `GIT_*` environment reaches the sandbox's git** (`setup.py` `_build_sandbox`).
  - Fix: run every sandbox git call with every `GIT_*` variable removed.
  - Add a test with `GIT_DIR` set to the caller's repo.
- **[HIGH] `.git` is looked up by name.**
  - Fix:
    - After `git init`, pin `.git` by handle (`O_DIRECTORY|O_NOFOLLOW`, relative to the build directory's handle).
    - Run git with `GIT_DIR`/`GIT_WORK_TREE` pointing at the pinned handles (`/proc/self/fd/N`, `/dev/fd/N`; refuse
      when that isn't available).
    - Set `core.hooksPath` to an empty private directory.
    - Add tests for a symlink `.git` and a `gitdir:` file, before init and after the check.
- **[MEDIUM] Writes follow symlinks or hard links planted inside the build directory**
  (`copytree(dirs_exist_ok)`, `apply_init`, `config.json`, `_wire_stack`). The caller's working-tree config can be
  downgraded; nothing is committed, and CI reads the base config.
  - Fix: create every directory with `mkdir(dir_fd=)` and every file with `O_CREAT|O_EXCL|O_NOFOLLOW` through handles,
    and fail if a name already exists.
- **[LOW]**
  - An ancestor of the parent can be swapped before the parent is opened. The result is an untracked nested repo in
    the caller's tree, with no commit.
  - The parent and `.` are opened outside the `try` (traceback, fd leak).
  - A non-OSError (KeyboardInterrupt, or `NotImplementedError` on platforms without `dir_fd`) leaves a partial build.
  - The tests leave their side directories in `/tmp`.
  - `test_parent_swapped_for_a_symlink` doesn't check the outcome.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes for setup itself**; the sandbox routes above commit a replacement into the caller |
| Profile changes through setup | **no**: through the sandbox (`GIT_DIR`, the `.git` swap, the working-tree links) |
| `gh auth status` / `claude --version` | **yes** |
| Sandbox path | **no** |

## Plan conformance
- G1 and G2 are logged with their proof tests and the human decision, and match the code.
- **Overstated again:** the G1 log and the CHANGELOG ("can't redirect the build into another repo") are accurate for
  paths, not for git's repository lookup or the build directory's contents.

## Test-first evidence
- G1's `SandboxRaceDeeper` tests and G2's `test_strict_requires_codeowners` are red on their parents (both reviewers
  reproduced it).
- **Gaps:**
  - no test for `GIT_DIR`, a `.git` swap, or links planted inside the build directory
  - the parent-swap test doesn't check the outcome
  - the side directories leak into `/tmp`

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 34 | AC-10's security flag unmet; AC-8 partial (deferred) |
| Security | 25 | 14 | 2 HIGH (`GIT_DIR`, `.git` lookup), 1 MEDIUM (links inside the build) |
| Test quality & test-first | 20 | 17 | red confirmed; the new routes are untested; temp leaks |
| Plan conformance | 10 | 9 | the overstated sandbox claim |
| Maintainability | 5 | 4 | fds opened outside the `try` |
| **Total** | 100 | **78** | **CHANGES_REQUESTED** |

### Fixes requested
The sandbox needs git and the scaffold writes to be pinned like its directories:
- a clean `GIT_*` environment
- `.git` pinned by handle, and git run on the handles, with no hooks
- `O_EXCL`/`O_NOFOLLOW` writes through directory handles
- the ancestor check after the open
- fds opened inside the `try`, and `BaseException`-safe cleanup
- tests for each route, and the side directories cleaned up

Alternatively, a scope decision by the human (see the next step).
