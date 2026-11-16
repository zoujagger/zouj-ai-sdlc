---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 6b25573bac1d1d1604cd1ebc03fcac2f18d2e113
score: 92/100
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
     in 6b25573. Round 11 at 6b25573 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 11 results:
- **Verifier:** VERIFIED (AC-21's live run carried over). `make check` (435), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** PASS, 71/75 on its four areas, no BLOCKER or MAJOR, two MINOR.
- **Security-reviewer:** PASS, 21/25, no CRITICAL or HIGH, **one MEDIUM**, one LOW.

**Verdict: CHANGES_REQUESTED.** The total is 92 and every AC is met, but the r10 fail-closed check doesn't see a
glob or variable inside the script's name (`…/hooks/engine.s?`, `…/e*.sh`, `engine.sh$IFS…`), so the docs' claim
that globs fail closed is false and under `solo` the agent can still feed the prompt hook. As in rounds 5-10, a
MEDIUM blocks PASS.

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
Closed since round 10: `cd`/`pushd` options, `popd`, `cd -`, an unknown home and a missing directory (all refused),
the escaped refusal `systemMessage`, the session repo named in the `core.worktree` refusal.

Round 11 findings:
- [MEDIUM] `lib/sdlc_engine/guards.py:306-309`, `:337-340`: `ENGINE_SH_RE` needs the literal name `engine.sh`, so
  `UNREADABLE_PATH_RE` never sees a glob or variable inside the name. Allowed in both repo kinds:
  `bash $CLAUDE_PLUGIN_ROOT/hooks/engine.s? prompt`, `…/engin?.sh`, `…/engine.s[h]`, `…/e*.sh`,
  `bash …/engine.sh$IFS'prompt'`, and `busybox sh …`/`fish …` (not in the shell list). The `sdlc` form has the same
  blind spot on main: `python3 -I …/bin/sdl? hook prompt`. → Walk the command words: a word whose name holds a glob
  or `$` and could match `engine.sh` (or `sdlc`) counts as the plugin's; `$` as a terminator; `busybox sh`, `fish`.
- [LOW] `lib/sdlc_engine/setup.py:839`: a multi-line `user.name` (allowed repo-local, set while the gates are
  dormant) adds trailer lines (`AIOps-Profile: strict`, a fake `AIOps-Approval:`) to the profile commit; `Approved-By`
  in approvals has the same pattern. Nothing trusts them; the record misleads. → Refuse an identity with a newline or
  non-printable character, in `set_first_profile` and `approve`.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo and `core.worktree` checks, `no_profile_yet`, `_commit_alone(data=)`; trailer injection LOW |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first`: `scaffold_root_problem`, Preflight, create-only `write_file`, `cwd == root` |
| The agent prompts a session of its own | Accepted residual | Known gaps; the glob forms are a further, unlisted path to the same `solo` outcome (MEDIUM) |
| The agent asks the human to type the command | Yes | skill text; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | preview and `list-installed` name the parts left out |
| `systemMessage` integrity (r9/r10) | Yes | `setup.Reply`, escaped line by line, `test_refusal_is_escaped_for_the_human` |

## Plan conformance
- **Steps:** all 20 are done and match the diff; the r10 row matches `6b25573` item by item.
- **Scope:** nothing ships outside it.
- **Stale link:** `pr.md:16` names `docs/adr/0003-first-profile-by-typed-phrase.md` (renamed); regenerate pr.md.
- **Open:** the manual `make dev` check of the typed command.

## Test-first evidence
Every step and review fix records its red run: S1-S20, r1, r2, r4-r10 (`6b25573`: 4 tests). Tests and code share
each fix commit, so the red runs are recorded in text.

## Fixes requested
1. **[MEDIUM] globs and variables in the script's name** (Security above).
2. **[LOW] a multi-line approver identity** (Security above).

## Other findings (non-blocking)
- [MINOR] `guards.py:334-366`: `env -C <plugin root> ./hooks/engine.sh`, `env --chdir=…`, and `CDPATH=<plugin root>
  cd hooks && ./engine.sh` (inline or exported) run the plugin's script behind a decoy at the same relative path.
  No worse than the documented copy-under-another-name gap. → Refuse them, or name them in Known gaps.
- [MINOR] `cli.py:959`: a 153-column line. → Wrap.
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | Every AC met; the TUI check is still manual |
| Security | 25 | 21 | Globs and variables in the script's name; the approver trailer injection |
| Test quality & test-first | 20 | 18 | Red runs recorded; `env -C`/`CDPATH` and the glob forms untested |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 4 | A long line; `_plugin_engine_sh` is getting dense |
| **Total** | 100 | **92** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MEDIUM blocks, as in rounds 5-10 |
