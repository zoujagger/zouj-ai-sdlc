---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 9b068a11fe119587e538e97a448f42ca07337c10
score: 91/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 reviewed the removed `Setup Profile` phrase (PASS 86, 88, 92). Round 4 (a693a2f): CHANGES_REQUESTED 89.
     Round 5 (53c90c0): CHANGES_REQUESTED 87. Round 6: fixed in e704354. Round 7: PASS 92, its LOWs and NITs fixed
     in f38003b. Round 8 (f38003b): CHANGES_REQUESTED 92, fixed
     in 93e86fe. Round 9 (93e86fe): CHANGES_REQUESTED 88, fixed
     in 5dc89c5. Round 10 (5dc89c5): CHANGES_REQUESTED 86, fixed
     in 6b25573. Round 11 (6b25573): CHANGES_REQUESTED 92, fixed
     in dd4c768. Round 12 (dd4c768): CHANGES_REQUESTED 89, fixed
     in 4b72255. Round 13 (4b72255): CHANGES_REQUESTED 86, fixed
     in 70dfd3d. Round 14 (70dfd3d): CHANGES_REQUESTED 88, fixed
     in 9b068a1. Round 15 at 9b068a1 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 15 results:
- **Verifier:** VERIFIED (AC-21's live run carried over). `make check` (442), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** CHANGES_REQUESTED, **one MAJOR** (a false positive), three MINOR, one NIT.
- **Security-reviewer:** PASS, 23/25, no CRITICAL, HIGH or MEDIUM, one LOW.

**Verdict: CHANGES_REQUESTED.** The r14 rule "a glob name under a variable directory, any length" applies to every
word a shell is given, so `bash ./lint.sh $SRC/*`, `bash -c "ls $TMPDIR/*"`, `zsh -c "rm -rf $BUILD/*"` and
`bash -c "du -sh ~/.claude/plugins/cache/*"` are refused as G-GATE-07 in every repo, with the wrong reason.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1390`; `tests/test_cli.py:532` |
| AC-2 | ✅ met | `tests/test_playbook.py:344 CommandWalk` (drives `hooks/engine.sh` only, both markers) |
| AC-3 | ✅ met | `tests/test_setup.py:1437`, `:1442`, `:1453`, `:1464`; `tests/test_cli.py:579`; `test_worktree_redirect_is_refused` |
| AC-4 | ✅ met | `tests/test_cli.py:548`, `:565` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691` |
| AC-6 | ✅ met | `tests/test_cli.py:618` |
| AC-7 | ✅ met | `tests/test_cli.py:640` |
| AC-8 | ✅ met | `tests/test_setup.py:1341`, `:1578`, `:1585`, `:1604` |
| AC-9 | ✅ met | `tests/test_cli.py:694` |
| AC-10 | ✅ met | `tests/test_cli.py:741`, `:758`, `:767`, `:798` |
| AC-11 | ✅ met | `tests/test_cli.py:413`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:422`, `:432`, `:437`, `:448`; `tests/test_setup.py:1008` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:770`, `:782` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:716`; `tests/test_cli.py:455`, `:462` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:837`, `:847`, `:854` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:821`; no `defaultMode` in the scaffold settings |
| AC-18 | ✅ met (amended AC) | `tests/test_setup.py:895`; `tests/test_cli.py:833`, `:850`, `:866`, `:877`, `:1009` |
| AC-19 | ✅ met | `plugin.json` `0.2.0-alpha.4`; `tests/test_cli.py:925`; `tests/test_rules.py:326`; `make build` passes |
| AC-20 | ✅ met | `tests/test_cli.py:471`, `:486` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:955`; `evals/README.md:22` |
| AC-22 | ✅ met | `tests/test_setup.py:1077`, `:1184` |
| AC-23 | ✅ met | `tests/test_setup.py:1196`, plus the below-the-top and repo-config refusals |

**AC-21: the run** (plan.md Deviation log S19, 2026-11-13; `--allow-tools Bash Write Edit`, 3 runs per arm):
`profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67
without, Δ +0.33, $0.87. Since that run (`ae31453`) `evals/` and `skills/setup` are unchanged; the verifier could not re-run it (tool scope).

## Security
Closed since round 14: other plugins' literal scripts and directories are allowed again; kept files compared with
what init writes; `ash`/`mksh`/`yash`/`csh`/`tcsh` recognised by the `engine.sh` check.

Round 15 findings:
- [LOW] `guards.py:392-398`: `set -- prompt; . <plugin>/hooks/e* < p.json` (and `cd <plugin>/hooks; …; . ~-/e*`)
  runs the plugin's script with an inherited `$1`; confirmed end to end in a scratch repo. Bounded exactly like the
  accepted `claude -p` residual; not a regression. → Name it in the Known gaps class.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | `no_profile_yet`, `approval_in_history`, session-repo check, `_commit_alone(data=)` |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first` create-only; created and differing kept files listed |
| The agent prompts a session of its own | Accepted residual | Known gaps; the LOW is a second route to the same bounded effect |
| The agent asks the human to type the command | Yes | `PROOF` per profile; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | nothing trusts `AIOps-Profile`/`Set-By`; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only; `feedback` swaps it for `~` |
| A core-only repo lacks the AI review and scheduled scan | Yes | the CI audit is in core |

## Plan conformance
- **Steps:** all 20 are done; r14 is logged, though "another plugin's scripts and directories are not refused" holds
  only partly (globs under the plugins directory).
- **Open:** the manual `make dev` check; `pr.md` is stale (the removed phrase, the renamed ADR, round 3's score).

## Test-first evidence
Every step and review fix records its red run (S14-S20, r4-r14). The r14 must-allow list has no glob or
variable-directory argument, which is how the MAJOR slipped through.

## Fixes requested
1. **[MAJOR] `lib/sdlc_engine/guards.py:392-399`**: apply "variable or plugin directory, any length" only at the
   script position (the first non-option word a shell or `source` is given, option arguments skipped); later words
   by the four-literal rule. Must-allow tests for `bash ./lint.sh $SRC/*`, `bash -c "ls $TMPDIR/*"` and
   `bash -c "du -sh ~/.claude/plugins/cache/*"`, red first.

## Other findings (non-blocking)
- [MINOR] `setup.py` `_differs` re-implements `cli.apply_init`'s placeholder rendering. → One helper.
- [MINOR] `docs/architecture.md:123`: a 169-column line. → Rewrap.
- [NIT] `SHELL_C`, `SHELL_FED_RE` and `SHELLS` still list the older shells only. → One shell list.
- [LOW] the sourced-glob example (Security above).
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; the TUI check is still manual |
| Security | 25 | 23 | One LOW of the documented class |
| Test quality & test-first | 20 | 17 | No glob or variable-directory must-allow case |
| Plan conformance | 10 | 9 | The r14 row claims more than the code does |
| Maintainability | 5 | 4 | A duplicated rendering; shell lists out of step |
| **Total** | 100 | **91** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MAJOR (false positive in every repo) blocks |
