---
id: 0005
verdict: PASS
commit: eea62688b7b12d7061b159fb8821a0f7b5063522
score: 82/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-06
---

# Review: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 5 PRE-REVIEW. Round 1 at 7f8f557: CHANGES_REQUESTED 62/100. Round 2 at 50e79c9: verifier VERIFIED; code
     review 84/100 CHANGES_REQUESTED; security FAIL 17/25. Round 3 at d696220: code review 76/100 (BLOCKER, regression);
     security FAIL 14/25 (CRITICAL `ln -s`, regression). Round 4 at 32fc402: code review 80/100 (BLOCKER `\\;`);
     security FAIL 15/25. Round 6 at 4e18711 (this file; rounds 5 and the re-check were fixed without a review.md):
     verifier VERIFIED; code review CHANGES_REQUESTED (2 BLOCKERs, both regressions against main); security FAIL 11/25
     (1 CRITICAL, 2 HIGH). Round 7 at 24c3ca8: verifier VERIFIED; code CHANGES_REQUESTED (BLOCKER: quoted `case`);
     security FAIL 12/25 (CRITICAL, the same). Round 8 at 6ecc5e7 (this file): verifier VERIFIED; code
     CHANGES_REQUESTED (2 BLOCKERs: quoted `';;'`, `>&2 case`); security FAIL 12/25 (CRITICAL: quoted `'a()'`/`'if'`
     before `case`). Round 9 at 8eaebc7 under zoujagger's stop rule (only a regression against main or a CRITICAL
     blocks; other holes go to intent 0006), then three targeted security re-checks (9af94b2, 46f42fd, 7ae94cd), each
     finding one regression from subshell scoping; zoujagger chose to revert the scoping (eea6268). Written from the
     reports. -->

## Summary
Round 9 under zoujagger's stop rule: only a regression against main or a CRITICAL finding blocks the PR; every other
new hole goes to intent 0006 and is listed in docs/architecture.md.

- **Verifier:** VERIFIED at 8eaebc7. Every AC is proved by a passing test; `make check`, `make build` and
  `sdlc validate 0005` pass.
- **Code review:** one regression against main (a `)` inside backticks or `${…}` closed the subshell scope early).
- **Security:** one regression against main (a `(…)#` comment faked a subshell); two HIGH holes that main shares.
- **Three targeted re-checks** of the fixes each found one more regression from the same root, exact subshell
  scoping: symlinks carried across readings (fixed, 46f42fd), assignments leaking out of a subshell (fixed,
  7ae94cd), and an assignment lost at a `)` that bash keeps inside a word (the fourth).
- **Decision (zoujagger): revert the scoping.** Since eea6268 the guard reads subshells exactly as main did: `cd`,
  `pushd` and assignments persist past `)`. An assignment right before `)` is judged both recorded and dropped,
  because main did both. HEAD can't be weaker than main there by construction.

No known regression against main remains. The comment, case and keyword fixes from rounds 6-8 stay, each built as
an extra reading that only adds blocks. The scoping revert itself wasn't independently re-reviewed: it removes code,
so the guard matches main's reading, and `make check` (342 tests) is green.

Verdict: **PASS** under the stop rule.

## Deferred to intent 0006 (not regressions; documented in docs/architecture.md)
- Exact subshell scoping: `(cd src); rm -rf .aiops` is judged in `src`, as on main.
- `)#<<EOF` skips the following lines; `true&&>/dev/null cmd` merges `cmd` into the previous command; `$'…'` in a
  heredoc delimiter.
- Assignments in pipeline members, `&` jobs and conditional branches.
- A `#` and a quote both nested inside `"$(…)"`.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_guards.py:710` `ProtectedTree::test_blocks_in_unlocked_state` (exact id and `Procedure:`); `ReviewRound6` matrices. A `cd` inside a subshell persisting past `)` is main's reading, deferred to 0006 |
| AC-2 | ✅ met | `tests/test_guards.py:720` (in-process check under 0.2 s; whole hook under 2 s, logged) |
| AC-3 | ✅ met | `tests/test_guards.py:677`, `:689`, `:1090` `SafetyPassFuzz` |
| AC-4 | ✅ met | `tests/test_shell_hooks.py:647` `EnvSpellings::test_spellings_are_dumps` |
| AC-5 | ✅ met | `tests/test_guards.py:782` `Incoming::test_archives` (into the repo root, logged) |
| AC-6 | ✅ met | `tests/test_guards.py:806` |
| AC-7 | ✅ met | `tests/test_guards.py:819`; cherry-pick of a main commit `IncomingRound6` |
| AC-8 | ✅ met | `tests/test_guards.py:833`, `:1034` |
| AC-9 | ✅ met | `tests/test_cli.py:141` `Init::test_agent_force_ignores_lock_env` |
| AC-10 | ✅ met | `tests/test_rules.py:190`, `tests/test_shell_hooks.py:615` (`source` refused, logged deviation) |
| AC-11 | ✅ met | `tests/test_rules.py:302` `Stages0005`, `:106` `Coverage` |
| AC-12 | ✅ met | `tests/test_playbook.py:162` walk in states 1, 4, 5 for solo/team/strict, `rm -rf docs` included |
| AC-13 | ✅ met | full suite green (342); no known regression against main after eea6268; new blocks on everyday commands checked against main in rounds 7-9 (none found after the round-7 comment fix) |

## Security
Round 9 (at 8eaebc7) and its re-checks, all resolved or deferred:
- [HIGH, regression] `(…)#` comments faked a subshell; [BLOCKER, regression] a `)` inside backticks or `${…}`
  closed a scope early; [HIGH, regression] links carried across readings; [HIGH, regression] subshell assignments
  leaked out; [HIGH, regression] an assignment was lost at a `)` kept inside a word. The first four were fixed, and
  the fifth is resolved by reverting subshell scoping to main's reading (eea6268).
- [LOW, regression] `$'\UFFFFFFFF'` crashed the tokenizer and the secret scan's fallback skipped the line: fixed
  (7ae94cd).
- [HIGH, not regressions] `)#<<EOF`, `&&>`: deferred to 0006.

Round 8 (at 6ecc5e7):
- [CRITICAL] A quoted `'a()'`, `'if'` or `"time"` puts a real `case` in command position; the subshell read as its
  pattern is dropped from every check, the secret scan and the AC-3 safety pass included (regression against main).
- Code review BLOCKERs of the same class: `>&2 case … >&2 esac` (fd redirections leave `redirs` empty); a quoted
  `';;'` in a real case body moves the parser into a pattern.

Round 7 (at 24c3ca8):
- [CRITICAL] A quoted or escaped `case` (`\case`, `"case"`, `>/dev/null case`) started case parsing; the following
  subshell was dropped (regression against main).
- [HIGH] A `$(…)` in a real case pattern was discarded (regression against main).
- Code review MAJORs: case forms missed (newline before `in`, substitution case word, after a reserved word);
  comment text read as a command blocked everyday commands in the locked states (stricter than main).

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
S1-S9 are implemented. Every review round and re-check is logged in the Deviation log with commit SHAs, including
zoujagger's stop rule and the scoping revert. The accepted false positives from rounds 8-9 are gone with the revert.
No out-of-scope change.

## Test-first evidence
Every step and fix commit (`d97b32e` … `eea6268`) carries `Red:`/`Green:` lines (05f0a2c, 32fc402 and 50e79c9 are
hook/tests/docs-only). S8's red evidence is the planted break, as the plan decided. From round 8 on, the tests cover
the class with generated matrices (`test_case_desync_matrix`, `test_scope_desync_matrix`), and the re-check-3 forms
are tested with the repo unlocked.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | every AC met; subshell scoping deferred to 0006 |
| Security | 25 | 18 | no known regression against main; two HIGH holes main shares deferred |
| Test quality & test-first | 20 | 16 | Red/Green throughout; class matrices only from round 8 |
| Plan conformance | 10 | 9 | thorough Deviation log; review.md lagged in rounds 7-8 |
| Maintainability | 5 | 2 | `shell.py` has several overlapping quote scanners and stacked readings |
| **Total** | 100 | **82 (round 9)** | round 1: 62; 2: 74; 4: 72; 6: 71; 8: 70. PASS under the stop rule |
