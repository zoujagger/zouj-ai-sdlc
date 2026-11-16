---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 5dc89c54d2f2eb8c757b3322df5c48567afcb4a0
score: 86/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 reviewed the removed `Setup Profile` phrase (PASS 86, 88, 92). Round 4 (a693a2f): CHANGES_REQUESTED 89.
     Round 5 (53c90c0): CHANGES_REQUESTED 87. Round 6: fixed in e704354. Round 7: PASS 92, its LOWs and NITs fixed
     in f38003b. Round 8 (f38003b): CHANGES_REQUESTED 92, fixed
     in 93e86fe. Round 9 (93e86fe): CHANGES_REQUESTED 88, fixed
     in 5dc89c5. Round 10 at 5dc89c5 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 10 results:
- **Verifier:** VERIFIED. All 23 ACs have passing tests. `make check` (434), `make build` (2 old warnings) and
  `sdlc validate 0007` pass.
- **Code-reviewer:** CHANGES_REQUESTED 86, **one MAJOR** (a regression of the r8 MEDIUM), four MINOR.
- **Security-reviewer:** PASS, 22/25, no CRITICAL, HIGH or MEDIUM, one LOW.

**Verdict: CHANGES_REQUESTED.** The r9 path check in `_plugin_engine_sh` reads the first word after `cd` as the
directory, so `cd -P <plugin>/hooks && ./engine.sh prompt` and `pushd $CLAUDE_PLUGIN_ROOT/hooks && ./engine.sh`
are allowed again: under `solo` the agent can feed `Plan Approved NNNN` to the prompt hook (confirmed against
`guards.check_bash` in both repo kinds).

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
without, Δ +0.33, $0.87. Since that run (`ae31453`) `evals/` and `skills/setup` are unchanged.

## Security
Closed since round 9: the `systemMessage` built apart from the steps (`setup.Reply`) with the approver and review
list escaped, the `core.worktree` redirect.

Round 10 findings:
- [MAJOR, from the code-reviewer] `lib/sdlc_engine/guards.py:309`, `:342-348`: `CD_RE` takes an option as the
  directory and ignores `pushd`, so `cd -P ~/.claude/plugins/…/hooks && ./engine.sh prompt`, `cd -- $CLAUDE_PLUGIN_ROOT/hooks && …`,
  `cd -L "$CLAUDE_PLUGIN_ROOT"/hooks; ./engine.sh prompt` and `pushd $CLAUDE_PLUGIN_ROOT/hooks && …` pass. → Fail
  closed: refuse any `engine.sh` run unless it resolves to an existing file that isn't the plugin's; a `cd`/`pushd`
  target that is an option or unreadable counts as unreadable. Add the four forms to `ENGINE_SH_FORMS`.
- [LOW] `setup.py` `approval_in_history` puts a commit subject (agent-made in a fresh repo) raw into the refusal,
  and refusals are sent whole as the `systemMessage`. → Escape the whole notice in `hook_profile` (newlines kept);
  test with an ESC in a trailer commit's subject.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo and `core.worktree` checks; `no_profile_yet`; `_commit_alone(data=)` |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first`: create-only `write_file`, `scaffold_root_problem`, Preflight, `cwd == root` |
| The agent prompts a session of its own | Accepted residual | Known gaps (R-22) |
| The agent asks the human to type the command | Yes | skill text; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | preview and `list-installed` name the parts left out |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | untouched |

## Plan conformance
- **Steps:** all 20 are done and match the diff; every round has its Deviation log row (r9 included).
- **Scope:** nothing ships outside it.
- **Open:** the manual `make dev` check of the typed command.

## Test-first evidence
Every step and review fix records its red run: S1-S20, r1, r2, r4-r9 (`5dc89c5`: 5 tests). Gap: no test covered
`cd`/`pushd` with options, which is how the MAJOR slipped through.

## Fixes requested
1. **[MAJOR] the `engine.sh` path check** (Security above).
2. **[LOW] the unescaped refusal** (Security above).

## Other findings (non-blocking)
- [MINOR] `guards.py:306-308`: `bash -o posix ./engine.sh`, `./engine.sh<p.json` and globs/braces (`./eng*.sh`)
  aren't matched. → Handle option arguments and `<`; name globs in Known gaps.
- [MINOR] `guards.py:347-348`: `cd ~nosuchuser && ./engine.sh` raises in `expanduser`, so `engine.sh` fails closed
  as G-FAIL-04 with the wrong reason. → Catch it; refuse as G-GATE-07.
- [MINOR] `guards.py:310`: a `$` in an earlier `cd` makes a project's script count as the plugin's
  (`cd $HOME/proj && ./engine.sh build` refused). Fails safe. → Document it.
- [MINOR] `tests/test_cli.py:600-616`: the `mkdtemp` beside the fixture is never removed. → `addCleanup`.
- [NIT, verifier] the `core.worktree` refusal names the redirected directory, not the session's repo.
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; the TUI check is still manual |
| Security | 25 | 19 | Lower of the two reviewers' scores (19 and 22): the r8 MEDIUM reopened by `cd -P`/`pushd`; the refusal LOW |
| Test quality & test-first | 20 | 16 | No `cd`/`pushd` option forms in the guard tests |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 3 | A second, weaker `cd` tracker beside the parser's own |
| **Total** | 100 | **86** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MAJOR blocks |
