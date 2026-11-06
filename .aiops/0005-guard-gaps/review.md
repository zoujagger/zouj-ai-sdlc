---
id: 0005
verdict: CHANGES_REQUESTED
commit: 50e79c9e4a4246821f7de1551e535fe608a05a8e
score: 74/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-06
---

# Review: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 5 PRE-REVIEW. Round 1 at 7f8f557: CHANGES_REQUESTED 62/100. Round 2 at 50e79c9 (this file): verifier
     VERIFIED; code review 84/100 CHANGES_REQUESTED (3 new false positives); security FAIL 17/25 (4 HIGH classes).
     Written from the three fresh-context personas' reports. -->

## Summary
Round 2 checks the round-1 fixes (3e31fff, a252209, 50e79c9). Every round-1 form is fixed and tested, and nothing is
weaker than main: the security reviewer compared about 140 probes across main, round 1 and HEAD. But the fixes
closed the reported forms, not their classes. Four HIGH classes still have simple bypasses:
- **wrapper and nested forms:** `trap`, `coproc`, `watch`, `parallel`, `flock -c`, `find -exec sh -c`, rebase
  `--exec`, git aliases
- **negated `find` tests**
- **symlinks made in the same command:** any path under the link
- **`git config --fil` / `-f<path>`, and `/proc` spellings** (`/dev/fd/../environ`, `/p*`, `cd /proc && cat env*`)

The round-1 fixes also introduced three false positives on everyday commands: `find . -type d -empty -delete`, copies
into the repo root while a venv is on PATH, and archives with symlink members extracted into subdirectories.
Verdict: **CHANGES_REQUESTED**.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ⚠️ partial | `tests/test_guards.py::ProtectedTree::test_blocks_in_unlocked_state` (the id isn't asserted). Bypasses: a filtered `find .github -type f -delete`, `ln -s .github q && rm -rf q/`, `pushd .github && rm -rf workflows`, `rsync --delete`, wrapper prefixes (`nice rm -rf .github`) |
| AC-2 | ✅ met | `::test_allows_ordinary_deletes` (the check is timed under 0.2 s; the whole hook call under 2 s) |
| AC-3 | ❌ not met | `tests/test_guards.py::Uninitialized::*` pass. But with the session at `$HOME`, `~/.bashrc` counts as inside the repo and is allowed. `git config -f ~/.gitconfig …`, `--glob` and `GIT_CONFIG=` are allowed. So are `cp -r x/. ~/` and `tar -C ~` |
| AC-4 | ❌ not met | `tests/test_shell_hooks.py::EnvSpellings`. False positives on quoted `env` (`grep "env" f`). Bypasses: `/proc/self/env*`, `cd /proc/self && cat environ`, `/opt/homebrew/bin/env`, `` `which printenv` `` |
| AC-5 | ⚠️ partial | `::Incoming::test_archives`. Bypasses: `--strip-components`, `--transform`, symlink members, an existing in-repo symlink, `busybox tar` |
| AC-6 | ✅ met | `::Incoming::test_stash` (`git stash branch` not inspected) |
| AC-7 | ❌ not met | `::Incoming::test_merge_rebase_cherry_pick`. Bypasses: octopus `git merge main x`, `git rebase main x`, `git rebase --onto main x`, `git cherry-pick ^HEAD x`. False positives: `git merge -m msg x`, `-X`, `-s`, `cherry-pick -m 1` |
| AC-8 | ⚠️ partial | `::Incoming::test_pull`. On main, any `git pull <remote> <ref>` is exempt (the spec exempts only a pull of main) |
| AC-9 | ✅ met | `tests/test_cli.py::Init::test_agent_force_ignores_lock_env` |
| AC-10 | ⚠️ partial | `tests/test_rules.py::Allowance::test_only_safe_env_forms`. `source env` runs its argument; `ls env; export -p` and `printenv GITHUB_TOKEN` are accepted |
| AC-11 | ✅ met | `tests/test_rules.py::Stages0005`, `::Coverage` |
| AC-12 | ⚠️ partial | `tests/test_playbook.py` walks 8 of the 12 AC-1 commands |
| AC-13 | ❌ not met | the suite is green, but there are new blocks on everyday commands (quoted `env`, `git merge -m`, `tar xfz`, `rm <symlink-to-dir>`) |

## Security
Round 2 (at 50e79c9), still open:
- [HIGH] More wrapper and nested forms: `trap`, `coproc`, `watch`, `parallel`, `flock -c`, `find -exec sh -c` and
  wrapped `-exec`, `git rebase --exec`/`-x`, and `git -c alias.*='!…'`.
- [HIGH] A negated or alternative `find` test (`-not`, `!`, `-o`) is read as a positive name filter.
- [HIGH] A symlink made in the same command is honoured only for `q/`, not for `q/…`, `q/*`, mv sources or extract
  directories.
- [HIGH] `git config --fil`, `--fil=…` and stuck `-f<path>` (already on main for initialized repos), and an exported
  `GIT_CONFIG`.
- [HIGH] More G-ENV-05 spellings: `/dev/fd/../environ`, `/p*`, `/pr?c`, a variable path, `cd / && cat
  proc/self/environ`, `cd /proc/self && cat env*`.
- [MEDIUM] `rsync --del`, a destination that isn't the last word, `--remove-source-files`; `tar --one-top-level`;
  checks that read the archive or ref before an earlier segment of the same command replaces it (`cp evil good &&
  tar x good`, `git branch -f`); cherry-pick `-m2` and `--stdin`; `git pull` on main with `-c branch.*`/`remote.*`
  or after `branch -u`; writes into home via `git clone`, `--work-tree`, `wget -P`, `curl --output-dir`.
- [LOW] Safe forms: `printenv *_URL`/`*_DSN`; assignment prefixes (`LD_PRELOAD=…`).
- False positives (code review, MAJOR): `find . -type d -empty -delete`; copies into the repo root with an in-repo
  venv on PATH; archives with link members extracted into subdirectories. MINOR: `git config -f <toolchain>` from a
  `$HOME` root; `git stash pop` with no stash; no fail-closed test for the safety pass.

Round 1 (at 7f8f557):
- [HIGH] `lib/sdlc_engine/guards.py:143,251` (already on main): a wrapper prefix (`nice`, `timeout 5`, `stdbuf`,
  `setsid`, `ionice`, `command -p`, `sudo -u`) skips every shell-write check, including the read-only lock. →
  `_strip_prefix` should strip `WRAPPER_WORDS` and their operands.
- [HIGH] `guards.py:800-841`: G-FILE-05 is bypassed by a filtered `find`, a symlink created earlier in the same
  command, `pushd`, or `rsync --delete`. → Inspect the tracked files a filtered `find` would reach, track
  `pushd`/`popd`, refuse a delete through a trailing-slash path that doesn't exist yet, and count the
  `rsync --delete` destination as deleted.
- [HIGH] `guards.py:634-656`: G-FILE-06 archives are bypassed by `--strip-components`, `--transform`, symlink members,
  an in-repo symlink, or `busybox`. → Apply the strip count to member names, refuse `--transform`, `-P` and archives
  with link members, and resolve where each member lands.
- [HIGH] `guards.py:161,659-700`: G-FILE-06 git is bypassed by plumbing (`update-index`/`checkout-index`/`read-tree`;
  already on main), by checking only the first operand (octopus merges, `rebase main x`), by cherry-pick ranges, and
  by `switch`/`checkout <branch>`/`reset`/`revert`/`stash branch`. → Inspect every operand, parse options that take
  a value, and add the missing commands.
- [HIGH] `guards.py:905,945`: the safety pass is skipped when the session root is `$HOME`. `git config --glob`/`-f`
  and `GIT_CONFIG=` are allowed, and so are copies and extractions into home. → Run the toolchain, secret and plugin
  checks before the "inside the repo" skip, match option prefixes, and treat a destination directory above a
  toolchain path as a hit.
- [HIGH] `hooks/guard-bash.sh:43-44`: G-ENV-05 is bypassed by globs or a `cd` (`/proc/self/env*`), and dumps outside
  G-ENV-03's patterns (`export -p`, `declare -x`, `set`, `ps eww`) aren't covered. → Widen the patterns.
- [MEDIUM] `guards.py:667`: `git pull` on main is exempt whatever its source. → Exempt only a pull of main itself.
- [MEDIUM] Case-insensitive filesystems (macOS): `.AIOPS` and `.GitHub` don't match. → Normalise case.
- [MEDIUM] `guards.py:415`: repos without `.aiops/` skip G-ENV-02 and G-GATE-06/07 (`unset CLAUDECODE; sdlc close`
  from another repo). → Run those text checks in the safety pass too.
- [LOW] `rules.py`: `source`/`.` in `SAFE_ENV_COMMANDS`; only commands that mention env are checked;
  `printenv <secret name>` is accepted.
- [LOW] Fail-closed false positives: `tar xfz`, `git merge -m msg x`, `rm <link-to-dir>`, `find -atime -delete`
  (misleading message). Git output is split on spaces.

## Plan conformance
S1-S9 match the plan. Logged deviations: S5 (home, unfiltered find) and S6 (unreadable archive). Not logged:
- the `-f <outside>` part of S4
- `.aiops/install-state.json` in the incoming guard
- the test renamed to `Stages0005`
- the changed `env FOO=1 make` expectation
- R-3's prefix narrowed to bin directories
- the 0.2.0-alpha.3 known issues not marked fixed in the CHANGELOG

## Test-first evidence
Every step commit (`d97b32e` … `7f8f557`) carries a `Red:` line naming the failing test and a `Green:` line. S8's red
evidence is the planted `_contains_protected → None` run, as the plan decided.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 26 | AC-3, AC-4, AC-7, AC-13 not met; AC-1, AC-5, AC-8, AC-10, AC-12 partial |
| Security | 25 | 13 | six HIGH bypasses (one already on main) |
| Test quality & test-first | 20 | 14 | Red/Green present; tests cover only the simplest forms |
| Plan conformance | 10 | 6 | six changes not logged |
| Maintainability | 5 | 3 | `out.split()`, dead `is_symlink`, garbled docstring |
| **Total** | 100 | **62 (round 1)** | round 2: 74 (code 84, security 17/25), CHANGES_REQUESTED |
