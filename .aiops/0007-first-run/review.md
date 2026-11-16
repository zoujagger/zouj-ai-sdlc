---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: dd4c768f5c12cfe21dc58650c72b7271dd2855d0
score: 89/100
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
     in dd4c768. Round 12 at dd4c768 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 12 results:
- **Verifier:** VERIFIED (AC-21's live run carried over). `make check` (436), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** no BLOCKER, **one MAJOR**, two MINOR.
- **Security-reviewer:** PASS, 21/25, no CRITICAL or HIGH, **one MEDIUM**, one LOW.

**Verdict: CHANGES_REQUESTED.**
- The r11 name heuristic still lets a variable or a short glob through as the script's name
  (`bash $CLAUDE_PLUGIN_ROOT/hooks/$N prompt`, `…/hooks/e* prompt`).
- In a fresh repo, the setup command doesn't name the scaffold files it kept, so a neutered `aiops-gates.yml` or
  `CODEOWNERS` the agent committed beforehand goes unmentioned.

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
Closed since round 11: globs and variables in a name with four literal characters, `busybox sh`/`fish`,
`CDPATH`/`env -C`, `python3 -I …/sdl? hook`, the one-line approver.

Round 12 findings:
- [MAJOR, code-reviewer; MEDIUM in effect] `lib/sdlc_engine/guards.py:350-355`: a name that isn't literally
  `engine.sh` takes the `fnmatch` branch, which needs 4 literal characters and `continue`s before the path check.
  Allowed in both repo kinds: `N=engine.sh; bash $CLAUDE_PLUGIN_ROOT/hooks/$N prompt`, `bash …/hooks/e$X prompt`,
  `bash $CLAUDE_PLUGIN_ROOT/hooks/e* prompt`, `…/hooks/en* prompt`, `f=…/engine.sh; bash $f prompt`. →
  A narrower invariant: a command word (or shell/`source` argument) followed by an engine event (`prompt`,
  `pre-bash`, …) runs only when its path is fully literal and resolves to an existing file other than the plugin's;
  the plugin's directory in a path is refused whatever the name.
- [MEDIUM] `lib/sdlc_engine/setup.py` `scaffold_first`/`set_first_profile`: kept scaffold files aren't named. The
  agent commits `aiops-gates.yml` running `true` and `CODEOWNERS` `* @nobody` while the gates are dormant; the human's
  `/zouj-ai-sdlc:setup team` says "no existing file changed" and lists only created files. The terminal `init` and
  setup list kept files. → Name every kept file that differs from the template, escaped; test with a committed
  non-template `aiops-gates.yml`.
- [LOW] `cli.py` `hook_profile` and the top-of-work-tree refusal interpolate `cwd`/`root`/`session` raw, and the r10
  escaping runs per line, so a directory named `x\nprofile SET: strict…` (the agent's Bash cwd persists into the
  prompt payload) forges a line in the refusal. → `_shown()` each value at interpolation; test a newline in the cwd.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo and `core.worktree` checks, `local_config_keys`, `no_profile_yet`, `_commit_alone(data=)`, one-line `approver()` |
| The hook writes the core scaffold without a preview (R-2a) | Partly | missing files only, top of the work tree, quick Preflight; kept files go unmentioned (MEDIUM) |
| The agent prompts a session of its own | Accepted residual | bounded as documented; the guard fails closed on most fed forms (MAJOR aside) |
| The agent asks the human to type the command | Yes | skill text; the notice states the proof; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config; `_identity_note` |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | `parts=[]`; `list-installed` names the parts left out |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | only G-GATE-07 widened |

## Plan conformance
- **Steps:** all 20 are done and match the diff; r4-r11 are logged with their red runs.
- **Scope:** nothing ships outside it.
- **Open:** the manual `make dev` check of the typed command; `pr.md`'s stale ADR link.

## Test-first evidence
Every step and review fix records its red run (S14-S20, r4-r11 by commit). The r11 tests cover only the forms they
list, not the variable-name and short-glob forms.

## Fixes requested
1. **[MAJOR] the `engine.sh` name heuristic** (Security above).
2. **[MEDIUM] kept scaffold files unnamed** (Security above).
3. **[LOW] raw paths in refusals** (Security above).

## Other findings (non-blocking)
- [MINOR] `setup.py:811-815`: after a fresh-repo scaffold fails part-way, "type the command again" takes the
  initialized path, which never finishes the scaffold (or refuses with different advice). → Say "ask Claude to run
  `sdlc setup --yes` (it creates only the missing files), then type the command again"; test an `OSError` mid-write.
- [MINOR] `guards.py:337-376`: `_plugin_engine_sh` has grown into a set of heuristics. → The event invariant above.
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; the TUI check is still manual |
| Security | 25 | 20 | Lower of the two (20 and 21): the name heuristic, kept files unnamed, raw paths |
| Test quality & test-first | 20 | 17 | The r11 tests miss the variable-name and short-glob forms |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 4 | `_plugin_engine_sh` heuristics |
| **Total** | 100 | **89** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MAJOR and the MEDIUM block |
