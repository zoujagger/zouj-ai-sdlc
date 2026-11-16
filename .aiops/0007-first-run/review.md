---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 4b72255e9d1fc2230307c9e2f8060638455f23c1
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
     in 5dc89c5. Round 10 (5dc89c5): CHANGES_REQUESTED 86, fixed
     in 6b25573. Round 11 (6b25573): CHANGES_REQUESTED 92, fixed
     in dd4c768. Round 12 (dd4c768): CHANGES_REQUESTED 89, fixed
     in 4b72255. Round 13 at 4b72255 (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 13 results:
- **Verifier:** VERIFIED (AC-21's live run carried over). `make check` (439), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** CHANGES_REQUESTED, **one MAJOR** (HIGH-class for security), three MINOR.
- **Security-reviewer:** PASS, 22/25, no CRITICAL, HIGH or MEDIUM, two LOW.

**Verdict: CHANGES_REQUESTED.** A shell option that takes a separate argument (`bash -O extglob`, `+O`, `--rcfile f`,
`--init-file f`) hides even the plugin's literal `hooks/engine.sh` from both guard regexes, so under `solo` a fed
`Plan Approved NNNN` opens a gate. It is a literal form, not one of the documented dynamic gaps.

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
Closed since round 12: variables and short globs as the script's name (the engine-event invariant), kept scaffold
files named, escaped paths in the session and top-of-tree refusals, the part-way failure advice.

Round 13 findings:
- [MAJOR, code-reviewer; HIGH-class] `lib/sdlc_engine/guards.py:307` `SHELL_PREFIX` skips only `-o <arg>` and
  one-word options, so `bash -O extglob $CLAUDE_PLUGIN_ROOT/hooks/engine.sh prompt`, `bash +O extglob …`,
  `bash --rcfile /dev/null …`, `bash --init-file /dev/null …` and `bash -O extglob -c "…/engine.sh prompt"` are
  allowed in both repo kinds. → When the command word is a shell or `source`/`.`, check every later word of that
  command: the plugin's directory, an `engine.sh`-like name, or a file resolving to the plugin's script is ours.
- [LOW] The remaining fed-payload forms (a non-literal event, a copied `engine.sh`, a script file the agent wrote)
  are the accepted `claude -p` residual in effect. → Say so as a class in Known gaps; stop adding name heuristics.
- [LOW] `guards.py:375` reads any named file in full before comparing. → Compare sizes first.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo and `core.worktree` checks, `local_config_keys`, `no_profile_yet`, `_commit_alone(data=)`, one-line `approver()` |
| The hook writes the core scaffold without a preview (R-2a) | Yes | missing files only, top of the work tree, quick Preflight; created and kept files listed |
| The agent prompts a session of its own | Accepted residual | the common fed forms are blocked; the rest is the same class (LOW); the MAJOR is a literal form |
| The agent asks the human to type the command | Yes | skill text; the notice states the proof; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | `parts=[]`; `list-installed` names the parts left out |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | only G-GATE-07 widened |

## Plan conformance
- **Steps:** all 20 are done and match the diff; r12's row matches `4b72255`.
- **Scope:** nothing ships outside it.
- **Open:** the manual `make dev` check of the typed command; `pr.md`'s stale ADR link.

## Test-first evidence
Every step and review fix records its red run (S14-S20, r4-r12). Code and tests share each fix commit.

## Fixes requested
1. **[MAJOR] shell options with a separate argument** (Security above).

## Other findings (non-blocking)
- [MINOR] `guards.py:377`: a bare name after a shell or `source` (`bash run prompt`) is read from the cwd first, so a
  link `run` → the plugin's script passes. → Skip bare names only as the command word itself.
- [MINOR] `setup.py:895`: kept files byte-equal to the template are labelled "NOT the plugin's version". → List only
  those that differ.
- [MINOR] `set_first_profile`'s `{why}` refusals (`scaffold_root_problem`'s `{root}`, `write_failure`'s OSError text)
  aren't escaped. → `_shown()` them.
- [MINOR] `cli.py` uses the private `setup._shown`. → A public name.
- [LOW] Known gaps class statement and the file-size check (Security above).
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 36 | Every AC met; the hook-only invariant behind a spec flag has a literal bypass |
| Security | 25 | 19 | The security reviewer's 22, less the HIGH-class literal bypass it missed |
| Test quality & test-first | 20 | 17 | No option-with-argument forms in the guard tests |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 4 | A private helper used across modules; two overlapping loops |
| **Total** | 100 | **86** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the HIGH-class MAJOR blocks |
