---
id: 0005
verdict: CHANGES_REQUESTED
commit: 4e18711a165a211a46f8ab0b7f89a2dfa2385ec9
score: 71/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-06
---

# Review: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 5 PRE-REVIEW. Round 1 at 7f8f557: CHANGES_REQUESTED 62/100. Round 2 at 50e79c9: verifier VERIFIED; code
     review 84/100 CHANGES_REQUESTED; security FAIL 17/25. Round 3 at d696220: code review 76/100 (BLOCKER, regression);
     security FAIL 14/25 (CRITICAL `ln -s`, regression). Round 4 at 32fc402: code review 80/100 (BLOCKER `\\;`);
     security FAIL 15/25. Round 6 at 4e18711 (this file; rounds 5 and the re-check were fixed without a review.md):
     verifier VERIFIED; code review CHANGES_REQUESTED (2 BLOCKERs, both regressions against main); security FAIL 11/25
     (1 CRITICAL, 2 HIGH). Written from the reports. -->

## Summary
Round 6 checks 4e18711 (the comment- and heredoc-aware pre-pass, the `)>` split and the scoped subshell `cd`).
`make check` (330 tests) and `make build` pass, `sdlc validate 0005` is clean, and the verifier found every AC
proved by a test. But both other reviewers, comparing HEAD against main through the real hooks, found that the
newest tokenizer code reopens regressions against main:
- **`shell._prescan` reads `#` after `)` as a comment.** In bash, `#` after `$(…)`, `$((…))`, `<(…)` or `a=(…)` is
  literal, and inside backticks or quotes nested in `"$(…)"` it is quoted. The rest of the line is dropped from every
  tokenizer consumer, including the always-on secret scan: `echo $(true)#; cat ~/.aws/credentials` is allowed in
  every repo (main: G-SEC-03). Gate, lock and toolchain checks are hidden the same way. Confirmed independently.
- **`time -p` loses command position**, so `time -p { rm -rf .aiops; }` and `time -p ! git config --global
  gpg.ssh.program …` are allowed (main blocks them).
- **A `case` pattern's `)` pops the subshell scope**, so a `cd` inside the subshell leaks or is lost:
  `( cd .github && case a in a) true;; esac && rm -rf workflows )` bypasses G-FILE-05 (AC-1).
- An undocumented hole already on main: heredoc delimiters other than `\w+` (`<<E-O`, `<<'E'OF`, `<<EOF"x"`) or a
  `<<` inside `$[…]` / nested quotes hide every following line.

Verdict: **CHANGES_REQUESTED**.

## Required fixes (round 6)
1. `shell.py:117`: drop `)` from the comment-start set (or count `)#` only after a plain `(…)` group); track
   `$(`/`${`/backtick nesting inside `"…"`; defence in depth: when a comment was dropped, also judge the line with
   it kept and block if either blocks. Tests for `$(…)#`, `$((…))#`, `<(…)#`, `` `…#` ``, `"$(echo " #")"`, through
   both the gate guard and `secret_scan`.
2. `shell.py:8,254,282`: keep command position after `time` and `-p`/`--`; add `!` and `{` to `guards.PREFIXES`.
3. `guards.py:1356-1362`, `shell.scoped_segments`: pop a scope only for a `)` paired with a reported `(`; ignore
   `case` pattern `)`; fall back conservatively if unbalanced.
4. `shell.py:6`: parse the heredoc delimiter as a bash word with quote removal, add `$[` as arithmetic, and fail
   closed when the delimiter line is never found (or log as a residual for 0006).
5. MINOR: have `segments()` call `scoped_segments()`; fill the Deviation log's placeholder commit references
   (d696220, 123c2d1, f33c90f, b698d39, 4e18711); fix the CHANGELOG `[Unreleased]` Security bullet that still lists
   `source env/bin/activate` as safe, and add entries for the r5/re-check tokenizer changes; add `rm -rf docs` to the
   AC-12 playbook walk; decide on `git cherry-pick main~1` (G-FILE-06 false positive for a main ancestor).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ⚠️ partial | `tests/test_guards.py:710` `ProtectedTree::test_blocks_in_unlocked_state` (asserts id and `Procedure:`). Bypassed by the `case`-in-subshell and `$(…)#` forms |
| AC-2 | ✅ met | `tests/test_guards.py:720` (in-process check under 0.2 s; whole hook under 2 s, logged) |
| AC-3 | ✅ met | `tests/test_guards.py:677` `Uninitialized::test_safety_pass_blocks`, `:689`, `:1090` `SafetyPassFuzz` |
| AC-4 | ✅ met | `tests/test_shell_hooks.py:624` `EnvSpellings::test_spellings_are_dumps` |
| AC-5 | ✅ met | `tests/test_guards.py:782` `Incoming::test_archives` |
| AC-6 | ✅ met | `tests/test_guards.py:806`, `:1067` |
| AC-7 | ✅ met | `tests/test_guards.py:819` `Incoming::test_merge_rebase_cherry_pick` |
| AC-8 | ✅ met | `tests/test_guards.py:833`, `:1034` |
| AC-9 | ✅ met | `tests/test_cli.py:141` `Init::test_agent_force_ignores_lock_env` |
| AC-10 | ✅ met | `tests/test_rules.py:190`, `tests/test_shell_hooks.py:592` (`source` refused, logged deviation) |
| AC-11 | ✅ met | `tests/test_rules.py:301` `Stages0005`, `:106` `Coverage` |
| AC-12 | ⚠️ partial | `tests/test_playbook.py:161` walk in states 1, 4, 5 for solo/team/strict; omits `rm -rf docs` |
| AC-13 | ❌ not met | suite green, but regressions against main: `$(…)#`/backtick `#` hide the gate checks and the always-on G-SEC-03 secret scan; `time -p {`/`!`; `case` `)` pops the subshell scope |

## Security
Round 6 (at 4e18711):
- [CRITICAL] `shell._prescan` comment handling hides the rest of the line, secret reads included, in every repo
  (regression against main). `echo $(true)#; cat ~/.aws/credentials`, `echo $((1))#; sed -i … src/app.py`,
  `echo "$(echo " #")"; rm -rf .aiops`, `cat <(true)#; …`, `x=(a)#; …`.
- [HIGH] `time -p` drops command position for `!`/`{` (regression against main).
- [HIGH] Heredoc delimiter regex `\w+` and `$[…]` arithmetic hide every following line (already on main,
  undocumented).
- [MEDIUM] `case` pattern `)` closes the subshell scope early (the new scoping is incomplete; code review rates the
  AC-1 bypass a BLOCKER).
- Spec flag "static parsing stays incomplete": **not mitigated** — HEAD opens parse holes main doesn't have.

Round 4 (at 32fc402), still open:
- [CRITICAL] `\\;` (an escaped backslash, then `;`) hid the rest of the line (a regression against main).
- [HIGH] `function f { … }` bodies were hidden (a regression against main).
- [MEDIUM] G-ENV-05 false positives on `/processing/` and `/dev/stdout`.
- [HIGH] git keys and variables that run commands; remote-name downloads; `cp -al` of a directory and `link`.
- [MEDIUM] `find -exec` writers; `${@}`/`for`/`shift`; `runuser`; `--`; `TAR_OPTIONS`; `~` in links; arbitrary earlier
  commands; braces and `$'…'` in `/proc`.

Round 3 (at d696220), still open:
- [CRITICAL] `ln -s <src> <protected>` was no longer checked (a regression against main).
- [BLOCKER] `if ! rm -rf .aiops`, `then { … }`, `f(){ … }` got past the guard (a regression against main).
- [HIGH] The committed tree lacked the G-ENV-05 hook change.
- [HIGH] Escaped `\(` `\)` `\;` ended a `find` command in the tokenizer (already on main).
- [HIGH] Directory-name tests with `-exec rm -rf`.
- [HIGH] Nested forms: `$0`, `trap --`, `flock --command=`, `coproc NAME`, parallel's options, `script -c`, `su -c`,
  stuck `-x`.
- [HIGH] Hard links to protected files (already on main).
- MEDIUM and LOW: chained or relative links and `ln -t`; tar abbreviations; more same-command time-of-check forms;
  `-nm2`; git editor, pager, `bisect run` and `submodule foreach`; clone value options; `GIT_WORK_TREE`; downloads
  into the current directory; `/proc` globs; `PWD`/`CONN`/`PROXY` names; `--remove-sent-files`.

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
Round 6: S1-S9 are implemented, and review rounds 1-5 and the re-check are logged in the Deviation log with their
reasons (scope widened by the human's decision). No unlogged out-of-scope change. Gap: the r2-r5 and re-check rows
name their commits by description ("tokenizer commit") instead of SHA.

Round 1 (historical): S5 and S6 deviations were logged; six other changes were not (all logged since).

## Test-first evidence
Every step and fix commit (`d97b32e` … `4e18711`) carries a `Red:` line naming the failing test and a `Green:` line.
S8's red evidence is the planted `_contains_protected → None` run, as the plan decided. The round-6 tests
(`TokenizerRecheck`) don't cover `#` after a substitution, backticks, `time -p`, or `case` inside a subshell, which is
how the regressions passed green.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 32 | AC-13 not met; AC-1 and AC-12 partial |
| Security | 25 | 11 | 1 CRITICAL and 1 HIGH regression against main; 1 HIGH already on main |
| Test quality & test-first | 20 | 16 | Red/Green throughout; new prescan/scope tests miss the bash-divergent cases |
| Plan conformance | 10 | 9 | placeholder commit references in the Deviation log |
| Maintainability | 5 | 3 | `scoped_segments` duplicates `segments`; `guards.py` is 1644 lines |
| **Total** | 100 | **71 (round 6)** | round 1: 62; round 2: 74; round 3: 76 code / 14 sec; round 4: 72. CHANGES_REQUESTED |
